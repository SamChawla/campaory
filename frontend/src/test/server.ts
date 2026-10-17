// A tiny fetch mock keyed by "METHOD /path". Handlers get the parsed JSON body.
type Reply = { status?: number; body?: unknown; headers?: Record<string, string> };
export type Handler = (body: unknown, init: RequestInit) => Reply | Promise<Reply>;

export const calls: { key: string; body: unknown; headers: Record<string, string> }[] = [];

const defaults: Record<string, Handler> = {
  "GET /api/config": () => ({ body: { provider: "mock", model: "mock", llm_is_mock: true, auth_providers: ["google"] } }),
  "GET /api/me": () => ({ body: { user: null } }),
};

export function mockApi(handlers: Record<string, Handler> = {}) {
  calls.length = 0;
  const all = { ...defaults, ...handlers };
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init = {}) => {
    const url = String(input).split("?")[0];
    const key = `${init.method ?? "GET"} ${url}`;
    const body = typeof init.body === "string" ? JSON.parse(init.body) : undefined;
    calls.push({ key, body, headers: (init.headers ?? {}) as Record<string, string> });
    const handler = all[key];
    const reply = handler ? await handler(body, init) : { status: 404, body: { error: { code: "not_found", message: "" } } };
    return new Response(reply.body === undefined ? null : JSON.stringify(reply.body), {
      status: reply.status ?? 200,
      headers: { "Content-Type": "application/json", ...(reply.headers ?? {}) },
    });
  });
}
