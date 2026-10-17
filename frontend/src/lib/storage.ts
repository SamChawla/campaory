// Guest persistence in localStorage (LLD 8.3). Never throws: failures are returned so the UI
// can tell the user in plain words.
import type { CampaignDoc } from "./types";

export const GUEST_KEY = "campaory.guest.v1";
export const BACKUP_KEY = "campaory.guest.backup";
export const UI_KEY = "campaory.ui";
export const PENDING_SAVE_KEY = "campaory.pendingSave";
export const SCHEMA = 1;

export type LoadResult =
  | { status: "empty" }
  | { status: "ok"; doc: CampaignDoc; savedAt: string }
  | { status: "reset"; reason: "invalid" | "newer" }
  | { status: "unavailable" };

export type WriteResult = "ok" | "quota" | "unavailable";

function local(): Storage | null {
  try {
    const s = window.localStorage;
    const probe = "campaory.probe";
    s.setItem(probe, "1");
    s.removeItem(probe);
    return s;
  } catch {
    return null;
  }
}

export function storageAvailable(): boolean {
  return local() !== null;
}

function looksLikeDoc(doc: unknown): doc is CampaignDoc {
  if (!doc || typeof doc !== "object") return false;
  const d = doc as Record<string, unknown>;
  return (
    d.schema === SCHEMA &&
    typeof d.id === "string" &&
    typeof d.name === "string" &&
    Array.isArray(d.facts) &&
    Array.isArray(d.plan) &&
    Array.isArray(d.posts) &&
    Array.isArray(d.platforms)
  );
}

export function loadGuest(): LoadResult {
  const s = local();
  if (!s) return { status: "unavailable" };
  let raw: string | null;
  try {
    raw = s.getItem(GUEST_KEY);
  } catch {
    return { status: "unavailable" };
  }
  if (raw === null) return { status: "empty" };

  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    parsed = undefined;
  }
  const wrap = parsed as { schema?: unknown; savedAt?: unknown; doc?: unknown } | undefined;
  if (wrap && typeof wrap.schema === "number" && wrap.schema > SCHEMA) {
    backup(s, raw);
    return { status: "reset", reason: "newer" };
  }
  if (!wrap || wrap.schema !== SCHEMA || !looksLikeDoc(wrap.doc)) {
    backup(s, raw);
    return { status: "reset", reason: "invalid" };
  }
  return { status: "ok", doc: wrap.doc, savedAt: typeof wrap.savedAt === "string" ? wrap.savedAt : "" };
}

function backup(s: Storage, raw: string) {
  try {
    s.setItem(BACKUP_KEY, raw);
    s.removeItem(GUEST_KEY);
  } catch {
    // Backup is best effort; the original stays in place if we cannot copy it.
  }
}

function isQuota(err: unknown): boolean {
  return (
    err instanceof DOMException &&
    (err.name === "QuotaExceededError" || err.name === "NS_ERROR_DOM_QUOTA_REACHED" || err.code === 22)
  );
}

export function saveGuest(doc: CampaignDoc, now: Date = new Date()): WriteResult {
  const s = local();
  if (!s) return "unavailable";
  try {
    s.setItem(GUEST_KEY, JSON.stringify({ schema: SCHEMA, savedAt: now.toISOString(), doc }));
    return "ok";
  } catch (err) {
    return isQuota(err) ? "quota" : "unavailable";
  }
}

export function clearGuest(): void {
  try {
    window.localStorage.removeItem(GUEST_KEY);
  } catch {
    // Nothing to clear if storage is blocked.
  }
}

export function readUi<T extends object>(fallback: T): T {
  try {
    const raw = window.localStorage.getItem(UI_KEY);
    return raw ? { ...fallback, ...(JSON.parse(raw) as Partial<T>) } : fallback;
  } catch {
    return fallback;
  }
}

export function writeUi(value: object): void {
  try {
    window.localStorage.setItem(UI_KEY, JSON.stringify(value));
  } catch {
    // UI state is a convenience only.
  }
}

export function session(): Storage | null {
  try {
    return window.sessionStorage;
  } catch {
    return null;
  }
}

export function setPendingSave(on: boolean): void {
  const s = session();
  if (!s) return;
  try {
    if (on) s.setItem(PENDING_SAVE_KEY, "1");
    else s.removeItem(PENDING_SAVE_KEY);
  } catch {
    // Without sessionStorage the user can press Save again after signing in.
  }
}

export function hasPendingSave(): boolean {
  try {
    return session()?.getItem(PENDING_SAVE_KEY) === "1";
  } catch {
    return false;
  }
}
