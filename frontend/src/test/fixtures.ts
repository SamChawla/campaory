import type { CampaignDoc, ExtractResponse, Fact, Post } from "../lib/types";

export const ITEM_ID = "11111111-1111-4111-8111-111111111111";
export const POST_ID = "22222222-2222-4222-8222-222222222222";

export function fact(key: Fact["key"], value: Fact["value"], status: Fact["status"] = "confirmed"): Fact {
  return { id: `f-${key}`, key, value, status, critical: true, source_snippet: null, source_ref: "manual" };
}

export function makePost(over: Partial<Post> = {}): Post {
  return {
    id: POST_ID,
    plan_item_id: ITEM_ID,
    platform: "x",
    text: "Riverside Hack Day on 24 Oct",
    status: "draft",
    facts_used: ["event_name"],
    guard_flags: [],
    placeholders: [],
    reminder_at: null,
    published_url: null,
    published_at: null,
    change_reason: null,
    versions: [],
    ...over,
  };
}

export function sampleDoc(over: Partial<CampaignDoc> = {}): CampaignDoc {
  return {
    schema: 1,
    id: "33333333-3333-4333-8333-333333333333",
    client_id: "33333333-3333-4333-8333-333333333333",
    version: 0,
    name: "Riverside Hack Day",
    event_mode: "offline",
    language: "en",
    tone: "friendly",
    platforms: ["linkedin", "instagram", "whatsapp", "x"],
    source: { kind: "sample", url: null, fetched_at: null, text_hash: null },
    facts: [
      fact("event_name", "Riverside Hack Day"),
      fact("start_date", "2026-10-24"),
      fact("timezone", "Asia/Kolkata"),
      fact("audience", "Students"),
      fact("language", "en"),
      fact("registration_url", "https://example.org/register"),
      fact("start_time", "10:00"),
    ],
    plan: [
      {
        id: ITEM_ID,
        title: "Announcement",
        purpose: "Say it is happening",
        stage: "pre",
        scheduled_for: "2026-10-18T09:00:00+05:30",
        position: 0,
        fact_keys: ["event_name", "start_date"],
      },
    ],
    posts: [makePost()],
    created_at: "2026-10-17T05:00:00.000Z",
    updated_at: "2026-10-17T05:00:00.000Z",
    ...over,
  };
}

export function extractResponse(): ExtractResponse {
  return {
    facts: [
      { key: "event_name", value: "Riverside Hack Day", status: "needs_review", critical: true, source_snippet: "Riverside Hack Day", source_ref: "sample" },
      { key: "start_date", value: "2026-10-24", status: "needs_review", critical: true, source_snippet: "24 October 2026", source_ref: "sample" },
      { key: "timezone", value: "", status: "missing", critical: true, source_snippet: null, source_ref: null },
      { key: "audience", value: "Students", status: "needs_review", critical: true, source_snippet: "students", source_ref: "sample" },
      { key: "registration_url", value: "https://example.org/register", status: "needs_review", critical: true, source_snippet: "https://example.org/register", source_ref: "sample" },
    ],
    source: { kind: "sample", url: null, fetched_at: null, text_hash: null },
    warnings: [],
    meta: { provider: "mock", model: "mock" },
  };
}
