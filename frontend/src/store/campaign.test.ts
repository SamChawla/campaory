import { GUEST_KEY, loadGuest } from "../lib/storage";
import { extractResponse, makePost, POST_ID, sampleDoc } from "../test/fixtures";
import { approvalBlockers, useCampaign } from "./campaign";

const opts = { platforms: ["linkedin", "x"] as const, language: "en" as const, tone: "friendly" };

beforeEach(() => {
  localStorage.clear();
  useCampaign.getState().reset();
  vi.useFakeTimers();
});
afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

test("applyExtraction builds a guest doc with ids and a confirmed language fact", () => {
  useCampaign.getState().applyExtraction(extractResponse(), { ...opts, platforms: [...opts.platforms] });
  const doc = useCampaign.getState().doc!;
  expect(doc.id).toBe(doc.client_id);
  expect(doc.name).toBe("Riverside Hack Day");
  expect(doc.platforms).toEqual(["linkedin", "x"]);
  expect(doc.facts.every((f) => typeof f.id === "string" && f.id.length > 10)).toBe(true);
  expect(doc.facts.find((f) => f.key === "language")).toMatchObject({ value: "en", status: "confirmed" });
  expect(doc.facts.find((f) => f.key === "event_name")?.status).toBe("needs_review");
});

test("guest changes are written to localStorage after 300 ms", () => {
  useCampaign.getState().applyExtraction(extractResponse(), { ...opts, platforms: [...opts.platforms] });
  vi.advanceTimersByTime(299);
  expect(localStorage.getItem(GUEST_KEY)).toBeNull();
  vi.advanceTimersByTime(1);
  const res = loadGuest();
  expect(res.status).toBe("ok");
  if (res.status === "ok") expect(res.doc).toEqual(useCampaign.getState().doc);
});

test("reload restores the guest doc", () => {
  useCampaign.getState().applyExtraction(extractResponse(), { ...opts, platforms: [...opts.platforms] });
  vi.advanceTimersByTime(300);
  const before = useCampaign.getState().doc;
  useCampaign.getState().reset();
  useCampaign.getState().init();
  expect(useCampaign.getState().doc).toEqual(before);
  expect(useCampaign.getState().mode).toBe("guest");
});

test("confirming and editing facts", () => {
  useCampaign.getState().applyExtraction(extractResponse(), { ...opts, platforms: [...opts.platforms] });
  const s = useCampaign.getState();
  s.confirmFact("event_name");
  s.setFact("timezone", "Asia/Kolkata");
  s.setFact("event_name", "Riverside Open Hack Day");
  const doc = useCampaign.getState().doc!;
  expect(doc.facts.find((f) => f.key === "event_name")).toMatchObject({ status: "confirmed", value: "Riverside Open Hack Day" });
  expect(doc.facts.find((f) => f.key === "timezone")).toMatchObject({ status: "confirmed", value: "Asia/Kolkata" });
  expect(doc.name).toBe("Riverside Open Hack Day");
});

test("no registration toggle stores confirmed empty value with not_applicable", () => {
  useCampaign.getState().applyExtraction(extractResponse(), { ...opts, platforms: [...opts.platforms] });
  useCampaign.getState().setNoRegistration(true);
  expect(useCampaign.getState().doc!.facts.find((f) => f.key === "registration_url")).toMatchObject({
    value: "",
    status: "confirmed",
    not_applicable: true,
  });
});

test("editing an approved post returns it to draft and keeps the old text", () => {
  useCampaign.getState().loadSaved(sampleDoc({ posts: [makePost({ status: "approved" })] }));
  useCampaign.getState().editPost(POST_ID, "New text");
  const p = useCampaign.getState().doc!.posts[0];
  expect(p.status).toBe("draft");
  expect(p.text).toBe("New text");
  expect(p.versions.at(-1)).toMatchObject({ text: "Riverside Hack Day on 24 Oct", reason: "edit" });
});

test("published posts are never modified (BR03)", () => {
  const published = makePost({ status: "published", published_at: "2026-10-17T05:00:00Z" });
  useCampaign.getState().loadSaved(sampleDoc({ posts: [published] }));
  const s = useCampaign.getState();
  s.editPost(POST_ID, "changed");
  s.applyRevision(POST_ID, { text: "x", facts_used: [], guard_flags: [], validation: { ok: true, length: 1, limit: 280 }, status: "draft" }, "make_shorter");
  s.applyImpact({ key: "start_time", old: "10:00", new: "09:30" }, { affected: [{ post_id: POST_ID, reason: "facts_used", detail: "d" }], protected: [], plan_changes: [] });
  s.approvePost(POST_ID);
  expect(useCampaign.getState().doc!.posts[0]).toEqual(published);
});

test("schedule needs approved and a future time; publish is manual", () => {
  vi.setSystemTime(new Date("2026-10-17T05:00:00Z"));
  useCampaign.getState().loadSaved(sampleDoc());
  const s = useCampaign.getState();
  s.schedulePost(POST_ID, "2026-10-20T05:00:00Z");
  expect(useCampaign.getState().doc!.posts[0].status).toBe("draft");
  s.approvePost(POST_ID);
  s.schedulePost(POST_ID, "2026-10-16T05:00:00Z");
  expect(useCampaign.getState().doc!.posts[0].status).toBe("approved");
  s.schedulePost(POST_ID, "2026-10-20T05:00:00Z");
  expect(useCampaign.getState().doc!.posts[0]).toMatchObject({ status: "scheduled", reminder_at: "2026-10-20T05:00:00Z" });
  s.markPublished(POST_ID, "https://x.com/p/1");
  expect(useCampaign.getState().doc!.posts[0]).toMatchObject({ status: "published", published_url: "https://x.com/p/1" });
});

test("impact puts affected posts back in review with the reason", () => {
  useCampaign.getState().loadSaved(sampleDoc({ posts: [makePost({ status: "approved" })] }));
  useCampaign.getState().applyImpact(
    { key: "start_time", old: "10:00", new: "09:30" },
    { affected: [{ post_id: POST_ID, reason: "facts_used", detail: "start_time changed from 10:00 to 09:30" }], protected: [], plan_changes: [] },
  );
  expect(useCampaign.getState().doc!.posts[0]).toMatchObject({ status: "needs_review", change_reason: "start_time changed from 10:00 to 09:30" });
});

test("approval waits for the server validation of the current text", () => {
  const doc = sampleDoc();
  const p = doc.posts[0];
  expect(approvalBlockers(p, undefined, doc.facts)).toBeNull();
  const ok = { text: p.text, result: { validation: { ok: true, length: 10, limit: 280 }, guard_flags: [], placeholders: [] } };
  expect(approvalBlockers(p, ok, doc.facts)).toEqual([]);
  expect(approvalBlockers(p, { ...ok, text: "stale" }, doc.facts)).toBeNull();
  const bad = { text: p.text, result: { validation: { ok: false, length: 300, limit: 280, issues: [{ level: "error" as const, code: "too_long", message: "X allows 280 characters; this is 300." }] }, guard_flags: [{ code: "UNKNOWN_DATE", token: "25 Oct", span: [0, 6] as [number, number], blocking: true }], placeholders: ["[ADD: venue]"] } };
  expect(approvalBlockers(p, bad, doc.facts)).toEqual([
    "X allows 280 characters; this is 300.",
    "Check these details, they are not in your facts: 25 Oct",
    "Fill in: [ADD: venue]",
  ]);
  const info = { text: p.text, result: { ...ok.result, guard_flags: [{ code: "RELATIVE_DATE", token: "tomorrow", span: [0, 8] as [number, number], blocking: false }] } };
  expect(approvalBlockers(p, info, doc.facts)).toEqual([]);
});

describe("saved mode", () => {
  test("PUT after 1.5 s with expected_version, then version is bumped", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ version: 4 }), { status: 200 }));
    useCampaign.getState().loadSaved(sampleDoc({ version: 3 }));
    useCampaign.getState().setSettings({ tone: "warm" });
    await vi.advanceTimersByTimeAsync(1499);
    expect(fetchMock).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/campaigns/33333333-3333-4333-8333-333333333333");
    expect(init!.method).toBe("PUT");
    const sent = JSON.parse(init!.body as string);
    expect(sent.expected_version).toBe(3);
    expect(sent.doc.tone).toBe("warm");
    expect(useCampaign.getState().doc!.version).toBe(4);
    expect(useCampaign.getState().saveError).toBeNull();
    expect(localStorage.getItem(GUEST_KEY)).toBeNull();
  });

  test("failed PUT keeps local state and flags a retry", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ error: { code: "server_error" } }), { status: 500 }));
    useCampaign.getState().loadSaved(sampleDoc({ version: 3 }));
    useCampaign.getState().setSettings({ tone: "warm" });
    await vi.advanceTimersByTimeAsync(1500);
    expect(useCampaign.getState().saveError).toBe("failed");
    expect(useCampaign.getState().doc!.tone).toBe("warm");
    expect(useCampaign.getState().doc!.version).toBe(3);
  });

  test("version conflict is surfaced with the current version", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ error: { code: "version_conflict", message: "", details: { current_version: 7 } } }), { status: 409 }),
    );
    useCampaign.getState().loadSaved(sampleDoc({ version: 3 }));
    useCampaign.getState().setSettings({ tone: "warm" });
    await vi.advanceTimersByTimeAsync(1500);
    expect(useCampaign.getState().saveError).toBe("conflict");
    expect(useCampaign.getState().conflictVersion).toBe(7);
  });
});

test("changeFact calls analyze then redraft for affected posts", async () => {
  vi.useRealTimers();
  const calls: string[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (url) => {
    calls.push(String(url));
    if (String(url).endsWith("/impact/analyze")) {
      return new Response(JSON.stringify({ affected: [{ post_id: POST_ID, reason: "facts_used", detail: "start_time changed" }], protected: [], plan_changes: [] }));
    }
    return new Response(JSON.stringify({ proposed_text: "new", changed_spans: [], reason: "r", facts_used: ["start_time"], guard_flags: [], validation: { ok: true, length: 3, limit: 280 } }));
  });
  useCampaign.getState().loadSaved(sampleDoc());
  const res = await useCampaign.getState().changeFact("start_time", "09:30");
  expect(res).toBe("impact");
  expect(calls).toEqual(["/api/impact/analyze", "/api/impact/redraft"]);
  expect(useCampaign.getState().proposals[POST_ID].state).toBe("ready");
  useCampaign.getState().acceptProposal(POST_ID);
  const p = useCampaign.getState().doc!.posts[0];
  expect(p.text).toBe("new");
  expect(p.versions.at(-1)?.reason).toBe("redraft");
  useCampaign.getState().reset();
});
