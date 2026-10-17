// Guest → account import (LLD 8.4). The local copy is cleared only after a 2xx response, so a
// failed save never loses work (BR11).
import { api, ApiError, errorMessage } from "../lib/api";
import { clearGuest, readUi, setPendingSave, writeUi } from "../lib/storage";
import { useCampaign } from "./campaign";
import { useUi } from "./ui";

export type Step = "facts" | "plan" | "posts" | "changes" | "upcoming";
const STEPS: Step[] = ["facts", "plan", "posts", "changes", "upcoming"];

export function rememberStep(step: Step) {
  writeUi({ ...readUi<{ lastStep?: Step }>({}), lastStep: step });
}

export function lastStep(): Step {
  const step = readUi<{ lastStep?: Step }>({}).lastStep;
  return step && STEPS.includes(step) ? step : "posts";
}

/** POST the guest doc. Returns the saved campaign path, or null when it did not save. */
export async function importGuest(): Promise<string | null> {
  const { doc, mode } = useCampaign.getState();
  const ui = useUi.getState();
  if (!doc || mode !== "guest") return null;
  ui.setImport({ state: "saving" });
  try {
    const res = await api.createCampaign(doc);
    clearGuest();
    setPendingSave(false);
    const current = useCampaign.getState().doc ?? doc;
    useCampaign.getState().loadSaved({ ...current, version: res.version });
    if (current.updated_at !== doc.updated_at) void useCampaign.getState().saveNow();
    ui.setImport({ state: "idle" });
    ui.toast("Saved. Your campaign is in your account.");
    return `/c/${res.id}/${lastStep()}`;
  } catch (err) {
    setPendingSave(false);
    if (err instanceof ApiError && err.code === "campaign_limit") {
      ui.setImport({ state: "limit", message: errorMessage(err) });
    } else {
      ui.setImport({ state: "failed", message: "We could not save yet. Your work is still on this device." });
    }
    ui.noteError(err);
    return null;
  }
}
