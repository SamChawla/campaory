// The campaign store (LLD 8.2). Holds the document and mirrors user intent as actions.
// Persistence: guest â†’ localStorage (300 ms debounce); saved â†’ PUT (1.5 s debounce) with the
// optimistic version. A failed PUT keeps local state and raises a retry banner.
import { create } from "zustand";
import { api, ApiError } from "../lib/api";
import { confirmedFacts, FACT_LABEL, factByKey, sameValue } from "../lib/facts";
import { uuid } from "../lib/ids";
import { clearGuest, loadGuest, saveGuest } from "../lib/storage";
import type {
  CampaignDoc,
  EventMode,
  ExtractResponse,
  Fact,
  FactChange,
  FactKey,
  FactStatus,
  FactValue,
  GeneratedPost,
  ImpactResponse,
  Language,
  Meta,
  Platform,
  PlanItem,
  Post,
  PostStatus,
  ProposedItem,
  RedraftResponse,
  ReviseResponse,
  Stage,
  ValidateResponse,
} from "../lib/types";

export const GUEST_DEBOUNCE_MS = 300;
export const SAVED_DEBOUNCE_MS = 1500;

export type SaveError = null | "failed" | "conflict";
export type StorageError = null | "quota" | "unavailable";

export interface ValidationEntry {
  text: string;
  result: ValidateResponse;
}

export interface Proposal {
  state: "loading" | "ready" | "error";
  result?: RedraftResponse;
  error?: unknown;
}

export interface LastChange {
  changed: FactChange;
  impact: ImpactResponse;
}

export interface StartOptions {
  platforms: Platform[];
  language: Language;
  tone: string;
}

interface CampaignState {
  doc: CampaignDoc | null;
  mode: "guest" | "saved";
  dirty: boolean;
  saving: boolean;
  lastSavedAt: string | null;
  saveError: SaveError;
  conflictVersion: number | null;
  storageError: StorageError;
  storageNotice: null | "reset";
  warnings: string[];
  /** Server notice from /plan/propose, e.g. the event has already passed. Not persisted. */
  planNotice: string | null;
  lastMeta: Meta | null;
  validations: Record<string, ValidationEntry>;
  proposals: Record<string, Proposal>;
  lastChange: LastChange | null;

  init(): void;
  reset(): void;
  dismissStorageNotice(): void;
  setMeta(meta: Meta | null | undefined): void;

  applyExtraction(res: ExtractResponse, opts: StartOptions): void;
  setSettings(patch: Partial<Pick<CampaignDoc, "name" | "event_mode" | "tone" | "platforms">>): void;
  setFact(key: FactKey, value: FactValue, status?: FactStatus): void;
  confirmFact(key: FactKey): void;
  confirmAll(): void;
  removeFact(key: FactKey): void;
  setNoRegistration(on: boolean): void;
  changeFact(key: FactKey, value: FactValue): Promise<"no_impact" | "impact">;

  setPlan(items: ProposedItem[], notice?: string | null): void;
  updatePlanItem(id: string, patch: Partial<Pick<PlanItem, "title" | "purpose" | "scheduled_for" | "stage">>): void;
  addPlanItem(stage: Stage, scheduledFor: string | null): string;
  removePlanItem(id: string): void;
  movePlanItem(id: string, delta: -1 | 1): void;

  applyGeneration(posts: GeneratedPost[]): void;
  setValidation(postId: string, text: string, result: ValidateResponse): void;
  editPost(id: string, text: string): void;
  applyRevision(id: string, res: ReviseResponse, instruction: string): void;
  restoreVersion(id: string, versionId: string): void;
  approvePost(id: string): void;
  unapprovePost(id: string): void;
  schedulePost(id: string, reminderAt: string): void;
  clearReminder(id: string): void;
  markPublished(id: string, url: string | null): void;

  applyImpact(changed: FactChange, impact: ImpactResponse): void;
  requestRedraft(postId: string): Promise<void>;
  acceptProposal(postId: string): void;
  keepCurrent(postId: string): void;

  loadSaved(doc: CampaignDoc): void;
  openSaved(id: string): Promise<void>;
  saveNow(overwriteVersion?: number): Promise<void>;
  loadLatest(): Promise<void>;
  becameGuestCopy(): void;
}

const nowIso = () => new Date().toISOString();

function blankDoc(opts: StartOptions): CampaignDoc {
  const id = uuid();
  const at = nowIso();
  return {
    schema: 1,
    id,
    client_id: id,
    version: 0,
    name: "Untitled event",
    event_mode: "offline",
    language: opts.language,
    tone: opts.tone,
    platforms: opts.platforms,
    source: { kind: "manual", url: null, fetched_at: null, text_hash: null },
    facts: [],
    plan: [],
    posts: [],
    created_at: at,
    updated_at: at,
  };
}

const MODES: EventMode[] = ["online", "offline", "hybrid"];
const LANG_FACT = (language: Language): Fact => ({
  id: uuid(),
  key: "language",
  value: language,
  status: "confirmed",
  critical: true,
  source_snippet: null,
  source_ref: "manual",
});

function versionOf(text: string, reason: string) {
  return { id: uuid(), text, reason, created_at: nowIso() };
}

let guestTimer: ReturnType<typeof setTimeout> | undefined;
let savedTimer: ReturnType<typeof setTimeout> | undefined;

export const useCampaign = create<CampaignState>()((set, get) => {
  /** Apply a change to the document, stamp it, and schedule persistence. */
  function commit(mutate: (doc: CampaignDoc) => void) {
    const current = get().doc;
    if (!current) return;
    const next = structuredClone(current);
    mutate(next);
    next.updated_at = nowIso();
    set({ doc: next, dirty: true });
    schedulePersist();
  }

  function schedulePersist() {
    const { mode } = get();
    if (mode === "guest") {
      clearTimeout(guestTimer);
      guestTimer = setTimeout(writeGuest, GUEST_DEBOUNCE_MS);
    } else {
      clearTimeout(savedTimer);
      savedTimer = setTimeout(() => void get().saveNow(), SAVED_DEBOUNCE_MS);
    }
  }

  function writeGuest() {
    const { doc, mode } = get();
    if (!doc || mode !== "guest") return;
    const result = saveGuest(doc);
    if (result === "ok") set({ dirty: false, storageError: null, lastSavedAt: nowIso() });
    else set({ storageError: result });
  }

  function post(doc: CampaignDoc, id: string): Post | undefined {
    return doc.posts.find((p) => p.id === id);
  }

  function editable(p: Post | undefined): p is Post {
    return !!p && p.status !== "published";
  }

  return {
    doc: null,
    mode: "guest",
    dirty: false,
    saving: false,
    lastSavedAt: null,
    saveError: null,
    conflictVersion: null,
    storageError: null,
    storageNotice: null,
    warnings: [],
    planNotice: null,
    lastMeta: null,
    validations: {},
    proposals: {},
    lastChange: null,

    init() {
      if (get().doc) return;
      const res = loadGuest();
      if (res.status === "ok") set({ doc: res.doc, mode: "guest", lastSavedAt: res.savedAt || null });
      else if (res.status === "reset") set({ storageNotice: "reset" });
      else if (res.status === "unavailable") set({ storageError: "unavailable" });
    },

    reset() {
      clearTimeout(guestTimer);
      clearTimeout(savedTimer);
      set({
        doc: null,
        mode: "guest",
        dirty: false,
        saving: false,
        saveError: null,
        conflictVersion: null,
        warnings: [],
        planNotice: null,
        validations: {},
        proposals: {},
        lastChange: null,
        lastSavedAt: null,
      });
    },

    dismissStorageNotice: () => set({ storageNotice: null }),
    setMeta: (meta) => {
      if (meta) set({ lastMeta: meta });
    },

    // ---- facts ------------------------------------------------------------------------

    applyExtraction(res, opts) {
      const doc = blankDoc(opts);
      doc.source = res.source;
      const facts: Fact[] = res.facts
        .filter((f) => f.key !== "language")
        .map((f) => ({ ...f, id: uuid() }));
      facts.push(LANG_FACT(opts.language));
      doc.facts = facts;
      const name = factByKey(facts, "event_name");
      if (name && typeof name.value === "string" && name.value.trim()) doc.name = name.value.trim().slice(0, 200);
      const mode = factByKey(facts, "event_mode");
      if (mode && MODES.includes(mode.value as EventMode)) doc.event_mode = mode.value as EventMode;
      clearTimeout(savedTimer);
      set({
        doc,
        mode: "guest",
        dirty: true,
        warnings: res.warnings ?? [],
        validations: {},
        proposals: {},
        lastChange: null,
        saveError: null,
      });
      get().setMeta(res.meta);
      schedulePersist();
    },

    setSettings(patch) {
      commit((doc) => {
        if (patch.name !== undefined) doc.name = patch.name.trim().slice(0, 200) || doc.name;
        if (patch.event_mode) doc.event_mode = patch.event_mode;
        if (patch.tone !== undefined) doc.tone = patch.tone.slice(0, 40);
        if (patch.platforms && patch.platforms.length) doc.platforms = patch.platforms;
      });
    },

    setFact(key, value, status = "confirmed") {
      commit((doc) => {
        const f = doc.facts.find((x) => x.key === key && x.status !== "superseded");
        if (f) {
          f.value = value;
          f.status = status;
          if (key === "registration_url") f.not_applicable = false;
        } else {
          doc.facts.push({
            id: uuid(),
            key,
            value,
            status,
            critical: ["event_name", "start_date", "timezone", "event_mode", "registration_url", "audience", "language"].includes(key),
            source_snippet: null,
            source_ref: "manual",
          });
        }
        if (key === "event_name" && typeof value === "string" && value.trim()) doc.name = value.trim().slice(0, 200);
        if (key === "event_mode" && MODES.includes(value as EventMode)) doc.event_mode = value as EventMode;
        if (key === "language" && (value === "en" || value === "hi" || value === "hinglish")) doc.language = value;
      });
    },

    confirmFact(key) {
      commit((doc) => {
        const f = doc.facts.find((x) => x.key === key && x.status !== "superseded");
        if (f && f.status === "needs_review") f.status = "confirmed";
      });
    },

    confirmAll() {
      commit((doc) => {
        for (const f of doc.facts) if (f.status === "needs_review") f.status = "confirmed";
      });
    },

    removeFact(key) {
      commit((doc) => {
        const f = doc.facts.find((x) => x.key === key && x.status !== "superseded");
        if (f) {
          f.value = Array.isArray(f.value) ? [] : "";
          f.status = "missing";
          f.not_applicable = false;
        }
      });
    },

    setNoRegistration(on) {
      commit((doc) => {
        let f = doc.facts.find((x) => x.key === "registration_url" && x.status !== "superseded");
        if (!f) {
          f = { id: uuid(), key: "registration_url", value: "", status: "missing", critical: true, source_snippet: null, source_ref: "manual" };
          doc.facts.push(f);
        }
        if (on) {
          f.value = "";
          f.status = "confirmed";
          f.not_applicable = true;
        } else {
          f.not_applicable = false;
          f.status = "missing";
        }
      });
    },

    async changeFact(key, value) {
      const before = get().doc;
      if (!before) return "no_impact";
      const old = factByKey(before.facts, key);
      const wasConfirmed = old?.status === "confirmed";
      get().setFact(key, value, "confirmed");
      const doc = get().doc!;
      if (!wasConfirmed || !old || sameValue(old.value, value) || doc.posts.length === 0) return "no_impact";
      const changed: FactChange = { key, old: old.value, new: value };
      const impact = await api.analyze({ changed, facts: doc.facts, posts: doc.posts, plan: doc.plan });
      get().applyImpact(changed, impact);
      await Promise.all(impact.affected.map((a) => get().requestRedraft(a.post_id)));
      return "impact";
    },

    // ---- plan -------------------------------------------------------------------------

    setPlan(items, notice = null) {
      set({ planNotice: notice });
      commit((doc) => {
        doc.plan = items.map((it, i) => ({
          id: uuid(),
          title: it.title.slice(0, 120),
          purpose: it.purpose ?? "",
          stage: it.stage,
          scheduled_for: it.scheduled_for ?? null,
          position: i,
          fact_keys: it.fact_keys ?? [],
        }));
        const keep = new Set(doc.plan.map((p) => p.id));
        doc.posts = doc.posts.filter((p) => keep.has(p.plan_item_id));
      });
    },

    updatePlanItem(id, patch) {
      commit((doc) => {
        const item = doc.plan.find((p) => p.id === id);
        if (!item) return;
        if (patch.title !== undefined && patch.title.trim()) item.title = patch.title.trim().slice(0, 120);
        if (patch.purpose !== undefined) item.purpose = patch.purpose;
        if (patch.scheduled_for !== undefined) item.scheduled_for = patch.scheduled_for;
        if (patch.stage) item.stage = patch.stage;
      });
    },

    addPlanItem(stage, scheduledFor) {
      const id = uuid();
      commit((doc) => {
        doc.plan.push({
          id,
          title: "New post",
          purpose: "",
          stage,
          scheduled_for: scheduledFor,
          position: doc.plan.length,
          fact_keys: [],
        });
      });
      return id;
    },

    removePlanItem(id) {
      commit((doc) => {
        if (doc.posts.some((p) => p.plan_item_id === id && p.status === "published")) return;
        doc.plan = doc.plan.filter((p) => p.id !== id);
        doc.plan.sort((a, b) => a.position - b.position).forEach((p, i) => (p.position = i));
        doc.posts = doc.posts.filter((p) => p.plan_item_id !== id);
      });
    },

    movePlanItem(id, delta) {
      commit((doc) => {
        const ordered = [...doc.plan].sort((a, b) => a.position - b.position);
        const i = ordered.findIndex((p) => p.id === id);
        const j = i + delta;
        if (i < 0 || j < 0 || j >= ordered.length) return;
        [ordered[i], ordered[j]] = [ordered[j], ordered[i]];
        ordered.forEach((p, k) => (p.position = k));
        doc.plan = ordered;
      });
    },

    // ---- posts ------------------------------------------------------------------------

    applyGeneration(generated) {
      const validations = { ...get().validations };
      commit((doc) => {
        for (const g of generated) {
          if (!doc.plan.some((p) => p.id === g.plan_item_id)) continue;
          const existing = doc.posts.find((p) => p.plan_item_id === g.plan_item_id && p.platform === g.platform);
          if (existing?.status === "published") continue;
          const status: PostStatus = g.status === "needs_review" ? "needs_review" : "draft";
          if (existing) {
            existing.versions.push(versionOf(existing.text, "regenerate"));
            Object.assign(existing, {
              text: g.text,
              status,
              facts_used: g.facts_used,
              guard_flags: g.guard_flags,
              placeholders: g.placeholders,
              reminder_at: null,
              change_reason: null,
            });
            validations[existing.id] = { text: g.text, result: { validation: g.validation, guard_flags: g.guard_flags, placeholders: g.placeholders } };
          } else {
            const id = uuid();
            doc.posts.push({
              id,
              plan_item_id: g.plan_item_id,
              platform: g.platform,
              text: g.text,
              status,
              facts_used: g.facts_used,
              guard_flags: g.guard_flags,
              placeholders: g.placeholders,
              reminder_at: null,
              published_url: null,
              published_at: null,
              change_reason: null,
              versions: [versionOf(g.text, "generated")],
            });
            validations[id] = { text: g.text, result: { validation: g.validation, guard_flags: g.guard_flags, placeholders: g.placeholders } };
          }
        }
      });
      set({ validations });
    },

    setValidation(postId, text, result) {
      set((s) => ({ validations: { ...s.validations, [postId]: { text, result } } }));
      const current = get().doc;
      const p = current ? post(current, postId) : undefined;
      if (!editable(p) || p.text !== text) return;
      if (sameValue(p.guard_flags as never, result.guard_flags as never) && sameValue(p.placeholders, result.placeholders)) return;
      commit((doc) => {
        const q = post(doc, postId)!;
        q.guard_flags = result.guard_flags;
        q.placeholders = result.placeholders;
      });
    },

    editPost(id, text) {
      commit((doc) => {
        const p = post(doc, id);
        if (!editable(p) || p.text === text) return;
        p.versions.push(versionOf(p.text, "edit"));
        p.text = text;
        if (p.status === "approved" || p.status === "scheduled") {
          p.status = "draft";
          p.reminder_at = null;
        }
      });
    },

    applyRevision(id, res, instruction) {
      commit((doc) => {
        const p = post(doc, id);
        if (!editable(p)) return;
        p.versions.push(versionOf(p.text, `revise:${instruction}`));
        p.text = res.text;
        p.facts_used = res.facts_used;
        p.guard_flags = res.guard_flags;
        p.status = res.status === "needs_review" ? "needs_review" : "draft";
        p.reminder_at = null;
      });
      set((s) => ({
        validations: {
          ...s.validations,
          [id]: { text: res.text, result: { validation: res.validation, guard_flags: res.guard_flags, placeholders: s.doc ? post(s.doc, id)?.placeholders ?? [] : [] } },
        },
      }));
      get().setMeta(res.meta);
    },

    restoreVersion(id, versionId) {
      commit((doc) => {
        const p = post(doc, id);
        if (!editable(p)) return;
        const v = p.versions.find((x) => x.id === versionId);
        if (!v || v.text === p.text) return;
        p.versions.push(versionOf(p.text, "restore"));
        p.text = v.text;
        if (p.status === "approved" || p.status === "scheduled") {
          p.status = "draft";
          p.reminder_at = null;
        }
      });
    },

    approvePost(id) {
      commit((doc) => {
        const p = post(doc, id);
        if (!editable(p) || p.status === "approved" || p.status === "scheduled") return;
        p.status = "approved";
        p.change_reason = null;
      });
    },

    unapprovePost(id) {
      commit((doc) => {
        const p = post(doc, id);
        if (!editable(p) || (p.status !== "approved" && p.status !== "scheduled")) return;
        p.status = "draft";
        p.reminder_at = null;
      });
    },

    schedulePost(id, reminderAt) {
      commit((doc) => {
        const p = post(doc, id);
        if (!p || (p.status !== "approved" && p.status !== "scheduled")) return;
        if (new Date(reminderAt).getTime() <= Date.now()) return;
        p.status = "scheduled";
        p.reminder_at = reminderAt;
      });
    },

    clearReminder(id) {
      commit((doc) => {
        const p = post(doc, id);
        if (!p || p.status !== "scheduled") return;
        p.status = "approved";
        p.reminder_at = null;
      });
    },

    markPublished(id, url) {
      commit((doc) => {
        const p = post(doc, id);
        if (!p || (p.status !== "approved" && p.status !== "scheduled")) return;
        p.status = "published";
        p.published_at = nowIso();
        p.published_url = url && url.trim() ? url.trim() : null;
        p.reminder_at = null;
      });
    },

    // ---- change impact ----------------------------------------------------------------

    applyImpact(changed, impact) {
      commit((doc) => {
        for (const a of impact.affected) {
          const p = post(doc, a.post_id);
          if (!editable(p)) continue;
          p.status = "needs_review";
          p.reminder_at = null;
          p.change_reason = a.detail.slice(0, 300);
        }
        for (const c of impact.plan_changes) {
          const item = doc.plan.find((x) => x.id === c.plan_item_id);
          if (item && c.field === "scheduled_for") item.scheduled_for = c.new;
        }
      });
      set({ lastChange: { changed, impact }, proposals: {} });
    },

    async requestRedraft(postId) {
      const { doc, lastChange } = get();
      const p = doc ? post(doc, postId) : undefined;
      if (!doc || !lastChange || !editable(p)) return;
      set((s) => ({ proposals: { ...s.proposals, [postId]: { state: "loading" } } }));
      try {
        const result = await api.redraft({ changed: lastChange.changed, facts: confirmedFacts(doc.facts), post: p });
        set((s) => ({ proposals: { ...s.proposals, [postId]: { state: "ready", result } } }));
        get().setMeta(result.meta);
      } catch (error) {
        set((s) => ({ proposals: { ...s.proposals, [postId]: { state: "error", error } } }));
      }
    },

    acceptProposal(postId) {
      const proposal = get().proposals[postId]?.result;
      if (!proposal) return;
      commit((doc) => {
        const p = post(doc, postId);
        if (!editable(p)) return;
        p.versions.push(versionOf(p.text, "redraft"));
        p.text = proposal.proposed_text;
        p.facts_used = proposal.facts_used;
        p.guard_flags = proposal.guard_flags;
        p.status = "needs_review";
        p.change_reason = null;
      });
      set((s) => {
        const proposals = { ...s.proposals };
        delete proposals[postId];
        return {
          proposals,
          validations: {
            ...s.validations,
            [postId]: { text: proposal.proposed_text, result: { validation: proposal.validation, guard_flags: proposal.guard_flags, placeholders: [] } },
          },
        };
      });
    },

    keepCurrent(postId) {
      commit((doc) => {
        const p = post(doc, postId);
        if (!editable(p)) return;
        p.change_reason = null;
      });
      set((s) => {
        const proposals = { ...s.proposals };
        delete proposals[postId];
        return { proposals };
      });
    },

    // ---- saved mode -------------------------------------------------------------------

    loadSaved(doc) {
      clearTimeout(guestTimer);
      clearTimeout(savedTimer);
      set({ doc, mode: "saved", dirty: false, saving: false, saveError: null, conflictVersion: null, validations: {}, proposals: {}, lastChange: null, lastSavedAt: doc.updated_at, warnings: [] });
    },

    async openSaved(id) {
      const doc = await api.getCampaign(id);
      get().loadSaved(doc);
    },

    async saveNow(overwriteVersion) {
      const { doc, mode, saving } = get();
      if (!doc || mode !== "saved" || saving) return;
      clearTimeout(savedTimer);
      const sentAt = doc.updated_at;
      set({ saving: true });
      try {
        const res = await api.putCampaign(doc.id, overwriteVersion ?? doc.version, doc);
        set((s) => ({
          doc: s.doc && s.doc.id === doc.id ? { ...s.doc, version: res.version } : s.doc,
          saving: false,
          dirty: s.doc?.updated_at !== sentAt,
          saveError: null,
          conflictVersion: null,
          lastSavedAt: nowIso(),
        }));
        if (get().dirty) schedulePersist();
      } catch (err) {
        if (err instanceof ApiError && err.code === "version_conflict") {
          const current = Number((err.details as { current_version?: unknown }).current_version);
          set({ saving: false, saveError: "conflict", conflictVersion: Number.isFinite(current) ? current : null });
        } else {
          set({ saving: false, saveError: "failed" });
        }
      }
    },

    async loadLatest() {
      const doc = get().doc;
      if (!doc) return;
      const latest = await api.getCampaign(doc.id);
      get().loadSaved(latest);
    },

    becameGuestCopy() {
      // Used only when the user chooses to keep working on this device after an import failed.
      clearGuest();
      const doc = get().doc;
      if (doc) {
        set({ mode: "guest" });
        schedulePersist();
      }
    },
  };
});

// ---- selectors ----------------------------------------------------------------------------

export function postCounts(doc: CampaignDoc | null): Record<PostStatus, number> {
  const counts: Record<PostStatus, number> = { draft: 0, needs_review: 0, approved: 0, scheduled: 0, published: 0 };
  for (const p of doc?.posts ?? []) counts[p.status] += 1;
  return counts;
}

export function orderedPlan(doc: CampaignDoc | null): PlanItem[] {
  return [...(doc?.plan ?? [])].sort((a, b) => a.position - b.position);
}

export function upcomingReminders(doc: CampaignDoc | null, now: Date = new Date()): Post[] {
  return (doc?.posts ?? [])
    .filter((p) => p.status === "scheduled" && p.reminder_at && new Date(p.reminder_at) > now)
    .sort((a, b) => (a.reminder_at! < b.reminder_at! ? -1 : 1));
}

/** Approval is allowed only on the server's validate answer for the current text (BR02). */
export function approvalBlockers(p: Post, entry: ValidationEntry | undefined, facts: Fact[]): string[] | null {
  if (p.status === "published") return ["This post is published and cannot change."];
  if (!entry || entry.text !== p.text) return null;
  const reasons: string[] = [];
  const { validation, guard_flags, placeholders } = entry.result;
  if (!validation.ok) {
    const errors = (validation.issues ?? []).filter((i) => i.level === "error").map((i) => i.message);
    reasons.push(...(errors.length ? errors : ["Fix the platform limits first."]));
  }
  const blocking = guard_flags.filter((f) => f.blocking !== false);
  if (blocking.length) reasons.push(`Check these details, they are not in your facts: ${blocking.map((f) => f.token).join(", ")}`);
  if (placeholders.length) reasons.push(`Fill in: ${placeholders.join(", ")}`);
  const confirmed = new Set(confirmedFacts(facts).map((f) => f.key));
  const unconfirmed = p.facts_used.filter((k) => !confirmed.has(k));
  if (unconfirmed.length) reasons.push(`Confirm these facts first: ${unconfirmed.map((k) => FACT_LABEL[k]).join(", ")}`);
  return reasons;
}
