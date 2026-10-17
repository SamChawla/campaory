// Typed API client (LLD 8.5). One error shape, 429 mapped to RateLimited, 60 s abort,
// batched generation with progress.
import type {
  AppConfig,
  CampaignDoc,
  CampaignSummary,
  ExtractResponse,
  ExtractSource,
  Fact,
  FactChange,
  GenerateItem,
  GenerateResponse,
  GeneratedPost,
  ImpactResponse,
  Language,
  Meta,
  Platform,
  PlanItem,
  Post,
  ProposeResponse,
  RedraftResponse,
  ReviseInstruction,
  ReviseResponse,
  User,
  ValidateResponse,
} from "./types";

export const TIMEOUT_MS = 60_000;
export const BATCH_SIZE = 4;
export const MAX_CONCURRENT = 3;

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, unknown>;

  constructor(status: number, code: string, message: string, details: Record<string, unknown> = {}) {
    super(message || code);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export class RateLimited extends ApiError {
  readonly retryAfterSeconds: number;

  constructor(message: string, retryAfterSeconds: number, details: Record<string, unknown> = {}) {
    super(429, "rate_limited", message, details);
    this.name = "RateLimited";
    this.retryAfterSeconds = retryAfterSeconds;
  }
}

interface RequestOptions {
  signal?: AbortSignal;
  timeoutMs?: number;
}

type Method = "GET" | "POST" | "PUT" | "DELETE";

function parseRetryAfter(header: string | null, body: unknown): number {
  const fromBody = (body as { error?: { retry_after_seconds?: unknown } } | null)?.error
    ?.retry_after_seconds;
  if (typeof fromBody === "number" && fromBody >= 0) return Math.ceil(fromBody);
  const n = header === null ? NaN : Number(header);
  return Number.isFinite(n) && n >= 0 ? Math.ceil(n) : 60;
}

export async function request<T>(
  method: Method,
  path: string,
  body?: unknown,
  { signal, timeoutMs = TIMEOUT_MS }: RequestOptions = {},
): Promise<T> {
  const controller = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);
  const onAbort = () => controller.abort();
  signal?.addEventListener("abort", onAbort);

  const headers: Record<string, string> = { Accept: "application/json" };
  if (method !== "GET") headers["X-Requested-With"] = "campaory";
  if (body !== undefined) headers["Content-Type"] = "application/json";

  let res: Response;
  try {
    res = await fetch(`/api${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      credentials: "same-origin",
      signal: controller.signal,
    });
  } catch (err) {
    if (timedOut) throw new ApiError(0, "timeout", "This is taking too long. Try again.");
    if (signal?.aborted) throw err;
    throw new ApiError(0, "network", "We could not reach Campaory. Check your connection.");
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", onAbort);
  }

  const text = await res.text();
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = null;
    }
  }
  if (res.ok) return data as T;

  const err = (data as { error?: { code?: string; message?: string; details?: Record<string, unknown> } } | null)
    ?.error;
  if (res.status === 429) {
    throw new RateLimited(
      err?.message ?? "",
      parseRetryAfter(res.headers.get("Retry-After"), data),
      err?.details ?? {},
    );
  }
  throw new ApiError(res.status, err?.code ?? "server_error", err?.message ?? "", err?.details ?? {});
}

// ---- endpoints ----------------------------------------------------------------------------

export const api = {
  config: () => request<AppConfig>("GET", "/config"),
  me: () => request<{ user: User | null }>("GET", "/me"),
  logout: () => request<unknown>("POST", "/auth/logout"),

  extract: (source: ExtractSource) => request<ExtractResponse>("POST", "/brief/extract", { source }),

  propose: (body: { facts: Fact[]; platforms: Platform[]; today: string; timezone: string }) =>
    request<ProposeResponse>("POST", "/plan/propose", body),

  generate: (body: {
    facts: Fact[];
    language: Language;
    tone: string;
    items: GenerateItem[];
    platforms: Platform[];
  }) => request<GenerateResponse>("POST", "/posts/generate", body),

  revise: (body: {
    facts: Fact[];
    post: Pick<Post, "platform" | "text" | "facts_used">;
    instruction: ReviseInstruction;
    custom_instruction?: string;
  }) => request<ReviseResponse>("POST", "/posts/revise", body),

  validate: (body: { platform: Platform; text: string; facts: Fact[] }, signal?: AbortSignal) =>
    request<ValidateResponse>("POST", "/posts/validate", body, { signal }),

  analyze: (body: { changed: FactChange; facts: Fact[]; posts: Post[]; plan: PlanItem[] }) =>
    request<ImpactResponse>("POST", "/impact/analyze", body),

  redraft: (body: { changed: FactChange; facts: Fact[]; post: Post }) =>
    request<RedraftResponse>("POST", "/impact/redraft", body),

  listCampaigns: async (): Promise<CampaignSummary[]> => {
    const data = await request<CampaignSummary[] | { campaigns: CampaignSummary[] }>("GET", "/campaigns");
    return Array.isArray(data) ? data : data.campaigns;
  },
  createCampaign: (doc: CampaignDoc) => request<{ id: string; version: number }>("POST", "/campaigns", doc),
  getCampaign: (id: string) => request<CampaignDoc>("GET", `/campaigns/${encodeURIComponent(id)}`),
  putCampaign: (id: string, expected_version: number, doc: CampaignDoc) =>
    request<{ version: number }>("PUT", `/campaigns/${encodeURIComponent(id)}`, { expected_version, doc }),
  deleteCampaign: (id: string) => request<unknown>("DELETE", `/campaigns/${encodeURIComponent(id)}`),
  deleteAccount: () => request<unknown>("DELETE", "/me"),
};

// ---- batched generation -------------------------------------------------------------------

export interface GenerateAllResult {
  posts: GeneratedPost[];
  failed: { plan_item_id: string; error: string }[];
  meta: Meta | null;
  rateLimited: RateLimited | null;
}

export async function generateAll(
  body: { facts: Fact[]; language: Language; tone: string; items: GenerateItem[]; platforms: Platform[] },
  onProgress?: (done: number, total: number) => void,
  call: typeof api.generate = api.generate,
): Promise<GenerateAllResult> {
  const batches: GenerateItem[][] = [];
  for (let i = 0; i < body.items.length; i += BATCH_SIZE) batches.push(body.items.slice(i, i + BATCH_SIZE));

  const result: GenerateAllResult = { posts: [], failed: [], meta: null, rateLimited: null };
  const total = body.items.length;
  let done = 0;
  let next = 0;
  onProgress?.(0, total);

  async function worker() {
    while (next < batches.length) {
      const batch = batches[next++];
      if (result.rateLimited) {
        result.failed.push(...batch.map((it) => ({ plan_item_id: it.id, error: "rate_limited" })));
      } else {
        try {
          const res = await call({ ...body, items: batch });
          result.posts.push(...res.posts);
          result.failed.push(...res.failed);
          result.meta = res.meta ?? result.meta;
        } catch (err) {
          if (err instanceof RateLimited) result.rateLimited = err;
          const code = err instanceof ApiError ? err.code : "server_error";
          result.failed.push(...batch.map((it) => ({ plan_item_id: it.id, error: code })));
        }
      }
      done += batch.length;
      onProgress?.(done, total);
    }
  }

  await Promise.all(Array.from({ length: Math.min(MAX_CONCURRENT, batches.length) }, worker));
  return result;
}

// ---- plain-words error messages (UI_SPEC 7.7) ---------------------------------------------

export function minutesText(seconds: number): string {
  const minutes = Math.max(1, Math.ceil(seconds / 60));
  return minutes === 1 ? "1 minute" : `${minutes} minutes`;
}

export function errorMessage(err: unknown): string {
  if (err instanceof RateLimited) {
    return `You have used your free AI requests for now. Try again in ${minutesText(err.retryAfterSeconds)}, or sign in for a higher limit.`;
  }
  if (err instanceof ApiError) {
    switch (err.code) {
      case "fetch_failed":
        return "We could not read that page. Paste the event text instead.";
      case "text_too_short":
        return "That text is too short to find event details. Add a few more lines.";
      case "llm_unavailable":
        return "The writing model is not answering right now. Try again in a moment.";
      case "llm_invalid_output":
        return "The writing model returned something we could not use. Try again.";
      case "blocked":
        return "Some required facts are not confirmed yet.";
      case "payload_too_large":
        return "This campaign is too large to send. Remove some posts and try again.";
      case "unauthorized":
        return "Your session ended. Sign in again to keep saving.";
      case "not_found":
        return "We could not find that campaign.";
      case "campaign_limit":
        return "Your free plan holds one saved campaign. Delete the old one to save this one, or keep working on this device.";
      case "published_post":
        return "This post is published and cannot change.";
      case "network":
      case "timeout":
        return err.message;
      default:
        return "Something went wrong on our side. Try again.";
    }
  }
  return "Something went wrong. Try again.";
}
