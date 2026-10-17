import { api, ApiError, errorMessage, generateAll, RateLimited, request } from "./api";
import type { GenerateItem, GenerateResponse } from "./types";

function jsonResponse(status: number, body: unknown, headers: Record<string, string> = {}) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json", ...headers } });
}

async function failure(p: Promise<unknown>): Promise<RateLimited> {
  try {
    await p;
  } catch (e) {
    return e as RateLimited;
  }
  throw new Error("expected the request to fail");
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.useRealTimers();
});

test("mutating calls send X-Requested-With and JSON to /api", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(200, { ok: 1 }));
  await request("POST", "/posts/validate", { a: 1 });
  const [url, init] = fetchMock.mock.calls[0];
  expect(url).toBe("/api/posts/validate");
  const headers = init!.headers as Record<string, string>;
  expect(headers["X-Requested-With"]).toBe("campaory");
  expect(headers["Content-Type"]).toBe("application/json");
  expect(init!.body).toBe('{"a":1}');
});

test("GET does not send the CSRF header", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(200, { user: null }));
  await api.me();
  const headers = fetchMock.mock.calls[0][1]!.headers as Record<string, string>;
  expect(headers["X-Requested-With"]).toBeUndefined();
});

test("error shape is parsed into ApiError", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    jsonResponse(422, { error: { code: "blocked", message: "x", details: { missing: ["timezone"] } } }),
  );
  const err = await failure(request("POST", "/plan/propose", {}));
  expect(err).toBeInstanceOf(ApiError);
  expect(err.code).toBe("blocked");
  expect(err.status).toBe(422);
  expect(err.details).toEqual({ missing: ["timezone"] });
});

test("429 maps to RateLimited with retryAfterSeconds from the body", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    jsonResponse(429, { error: { code: "rate_limited", message: "Try again in 12 minutes.", retry_after_seconds: 720 } }, { "Retry-After": "720" }),
  );
  const err = await failure(request("POST", "/brief/extract", {}));
  expect(err).toBeInstanceOf(RateLimited);
  expect(err.retryAfterSeconds).toBe(720);
  expect(errorMessage(err)).toMatch(/Try again in 12 minutes, or sign in/);
});

test("429 falls back to the Retry-After header", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("", { status: 429, headers: { "Retry-After": "90" } }));
  const err = await failure(request("GET", "/config"));
  expect(err.retryAfterSeconds).toBe(90);
});

test("requests abort after the timeout", async () => {
  vi.useFakeTimers();
  vi.spyOn(globalThis, "fetch").mockImplementation(
    (_url, init) =>
      new Promise((_resolve, reject) => {
        init!.signal!.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
      }),
  );
  const pending = failure(request("POST", "/posts/generate", {}, { timeoutMs: 60_000 }));
  await vi.advanceTimersByTimeAsync(60_000);
  const err = await pending;
  expect(err).toBeInstanceOf(ApiError);
  expect(err.code).toBe("timeout");
});

test("network failure gives a plain message", async () => {
  vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("Failed to fetch"));
  const err = await failure(request("GET", "/config"));
  expect(err.code).toBe("network");
  expect(errorMessage(err)).toMatch(/could not reach/i);
});

test("fetch_failed reads as plain words", () => {
  expect(errorMessage(new ApiError(422, "fetch_failed", ""))).toBe(
    "We could not read that page. Paste the event text instead.",
  );
});

function items(n: number): GenerateItem[] {
  return Array.from({ length: n }, (_, i) => ({ id: `i${i}`, title: `T${i}`, purpose: "", stage: "pre", fact_keys: [] }));
}

const body = (n: number) => ({ facts: [], language: "en" as const, tone: "", items: items(n), platforms: ["x" as const] });

test("generation is batched by 4 with at most 3 in flight and reports progress", async () => {
  let inFlight = 0;
  let peak = 0;
  const sizes: number[] = [];
  const call = vi.fn(async (b: { items: GenerateItem[] }): Promise<GenerateResponse> => {
    inFlight++;
    peak = Math.max(peak, inFlight);
    sizes.push(b.items.length);
    await new Promise((r) => setTimeout(r, 5));
    inFlight--;
    return {
      posts: b.items.map((it) => ({
        plan_item_id: it.id,
        platform: "x",
        text: "t",
        facts_used: [],
        status: "draft",
        guard_flags: [],
        placeholders: [],
        validation: { ok: true, length: 1, limit: 280 },
      })),
      failed: [],
      meta: { provider: "mock" },
    };
  });
  const progress: number[] = [];
  const res = await generateAll(body(18), (done) => progress.push(done), call as never);
  expect(sizes.sort()).toEqual([2, 4, 4, 4, 4]);
  expect(peak).toBeLessThanOrEqual(3);
  expect(res.posts).toHaveLength(18);
  expect(progress[0]).toBe(0);
  expect(progress.at(-1)).toBe(18);
  expect(res.meta?.provider).toBe("mock");
});

test("a failed batch marks only its items as failed", async () => {
  const call = vi.fn(async (b: { items: GenerateItem[] }): Promise<GenerateResponse> => {
    if (b.items[0].id === "i4") throw new ApiError(502, "llm_unavailable", "");
    return { posts: [], failed: [], meta: { provider: "euri" } };
  });
  const res = await generateAll(body(8), undefined, call as never);
  expect(res.failed.map((f) => f.plan_item_id)).toEqual(["i4", "i5", "i6", "i7"]);
  expect(res.failed[0].error).toBe("llm_unavailable");
});

test("rate limit stops further batches", async () => {
  const call = vi.fn(async (): Promise<GenerateResponse> => {
    throw new RateLimited("", 60);
  });
  const res = await generateAll(body(16), undefined, call as never);
  expect(res.rateLimited).toBeInstanceOf(RateLimited);
  expect(res.failed).toHaveLength(16);
  expect(call.mock.calls.length).toBeLessThanOrEqual(3);
});
