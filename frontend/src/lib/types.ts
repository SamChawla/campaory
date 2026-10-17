// The campaign document (LLD section 3) and API shapes (LLD section 5). Keep in sync with
// backend/app/domain/schemas.py. Unknown fields are rejected by the server on import.

export type Platform = "linkedin" | "instagram" | "whatsapp" | "x";
export const PLATFORMS: Platform[] = ["linkedin", "instagram", "whatsapp", "x"];
export type EventMode = "online" | "offline" | "hybrid";
export type Language = "en" | "hi" | "hinglish";
export type FactStatus = "confirmed" | "needs_review" | "missing" | "superseded";
export type PostStatus = "draft" | "needs_review" | "approved" | "scheduled" | "published";
export type Stage = "pre" | "event" | "post";
export type SourceKind = "url" | "text" | "sample" | "manual";

export type FactKey =
  | "event_name"
  | "event_type"
  | "short_description"
  | "start_date"
  | "end_date"
  | "start_time"
  | "end_time"
  | "timezone"
  | "venue"
  | "address"
  | "city"
  | "event_mode"
  | "registration_url"
  | "registration_status"
  | "capacity"
  | "registration_deadline"
  | "audience"
  | "speakers"
  | "judges"
  | "mentors"
  | "partners"
  | "hashtags"
  | "handles"
  | "language";

export interface Person {
  name: string;
  role: string;
  url?: string | null;
  handle?: string | null;
}

export type FactValue = string | Person[] | string[];

export interface Fact {
  id: string;
  key: FactKey;
  value: FactValue;
  status: FactStatus;
  critical: boolean;
  source_snippet: string | null;
  source_ref: string | null;
  not_applicable?: boolean;
}

export interface Source {
  kind: SourceKind;
  url: string | null;
  fetched_at: string | null;
  text_hash: string | null;
}

export interface PlanItem {
  id: string;
  title: string;
  purpose: string;
  stage: Stage;
  scheduled_for: string | null;
  position: number;
  fact_keys: FactKey[];
}

export interface GuardFlag {
  code: string;
  token: string;
  span: [number, number];
  blocking?: boolean;
}

export interface PostVersion {
  id: string;
  text: string;
  reason: string;
  created_at: string;
}

export interface Post {
  id: string;
  plan_item_id: string;
  platform: Platform;
  text: string;
  status: PostStatus;
  facts_used: FactKey[];
  guard_flags: GuardFlag[];
  placeholders: string[];
  reminder_at: string | null;
  published_url: string | null;
  published_at: string | null;
  change_reason: string | null;
  versions: PostVersion[];
}

export interface CampaignDoc {
  schema: 1;
  id: string;
  client_id: string;
  version: number;
  name: string;
  event_mode: EventMode;
  language: Language;
  tone: string;
  platforms: Platform[];
  source: Source;
  facts: Fact[];
  plan: PlanItem[];
  posts: Post[];
  created_at: string;
  updated_at: string;
}

// ---- API ----------------------------------------------------------------------------------

export interface Meta {
  provider: string;
  model?: string;
  prompt_version?: string;
  latency_ms?: number;
}

export type ExtractSource =
  | { kind: "url"; url: string }
  | { kind: "text"; text: string }
  | { kind: "sample" };

export type ExtractedFact = Omit<Fact, "id">;

export interface ExtractResponse {
  facts: ExtractedFact[];
  source: Source;
  warnings: string[];
  meta: Meta;
}

export interface ProposedItem {
  title: string;
  purpose: string;
  stage: Stage;
  scheduled_for: string;
  fact_keys: FactKey[];
  platforms?: Platform[];
}

export interface ProposeResponse {
  items: ProposedItem[];
  event_status: "upcoming" | "ongoing" | "past";
  notice: string | null;
}

export interface ValidationIssue {
  level: "error" | "warning";
  code: string;
  message: string;
}

export interface Validation {
  ok: boolean;
  length: number;
  limit: number;
  hashtags?: number;
  issues?: ValidationIssue[];
}

export interface GeneratedPost {
  plan_item_id: string;
  platform: Platform;
  text: string;
  facts_used: FactKey[];
  status: PostStatus;
  guard_flags: GuardFlag[];
  placeholders: string[];
  validation: Validation;
}

export interface GenerateItem {
  id: string;
  title: string;
  purpose: string;
  stage: Stage;
  fact_keys: FactKey[];
}

export interface GenerateResponse {
  posts: GeneratedPost[];
  failed: { plan_item_id: string; error: string }[];
  meta: Meta;
}

export type ReviseInstruction = "make_shorter" | "make_longer" | "warmer" | "more_formal" | "custom";

export interface ReviseResponse {
  text: string;
  facts_used: FactKey[];
  guard_flags: GuardFlag[];
  validation: Validation;
  status: PostStatus;
  meta?: Meta;
}

export interface ValidateResponse {
  validation: Validation;
  guard_flags: GuardFlag[];
  placeholders: string[];
}

export interface FactChange {
  key: FactKey;
  old: FactValue;
  new: FactValue;
}

export interface ImpactResponse {
  affected: { post_id: string; reason: string; detail: string }[];
  protected: { post_id: string; status: PostStatus; note: string }[];
  plan_changes: { plan_item_id: string; field: string; old: string | null; new: string | null }[];
}

export interface RedraftResponse {
  proposed_text: string;
  changed_spans: { from: number; to: number }[];
  reason: string;
  facts_used: FactKey[];
  guard_flags: GuardFlag[];
  validation: Validation;
  meta?: Meta;
}

export interface AppConfig {
  provider: string;
  model?: string;
  llm_is_mock: boolean;
  auth_providers: string[];
  limits?: Record<string, number>;
}

export interface User {
  id: string;
  email: string;
  name?: string | null;
  avatar_url?: string | null;
}

export interface CampaignSummary {
  id: string;
  name: string;
  version: number;
  updated_at: string;
  post_counts: Partial<Record<PostStatus, number>>;
}
