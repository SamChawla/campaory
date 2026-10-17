// Starting a campaign from the Start form or the "Try a sample event" buttons.
import { create } from "zustand";
import { api, ApiError, errorMessage } from "../lib/api";
import { loadGuest } from "../lib/storage";
import type { ExtractSource, Language, Platform } from "../lib/types";
import { PLATFORMS } from "../lib/types";
import { useCampaign } from "./campaign";
import { useUi } from "./ui";

interface StartState {
  platforms: Platform[];
  language: Language;
  tone: string;
  busy: null | "url" | "text" | "sample";
  error: string | null;
  errorCode: string | null;
  errorSource: ExtractSource["kind"] | null;
  setOptions(p: Partial<Pick<StartState, "platforms" | "language" | "tone">>): void;
  start(source: ExtractSource): Promise<boolean>;
}

export const useStart = create<StartState>()((set, get) => ({
  platforms: [...PLATFORMS],
  language: "en",
  tone: "friendly",
  busy: null,
  error: null,
  errorCode: null,
  errorSource: null,
  setOptions: (p) => set(p),

  async start(source) {
    if (get().busy) return false;
    if (loadGuest().status === "ok" && !window.confirm("Start a new campaign? The campaign on this device will be replaced.")) return false;
    set({ busy: source.kind, error: null, errorCode: null, errorSource: null });
    try {
      const res = await api.extract(source);
      const { platforms, language, tone } = get();
      useCampaign.getState().applyExtraction(res, { platforms, language, tone });
      set({ busy: null });
      return true;
    } catch (err) {
      useUi.getState().noteError(err);
      set({ busy: null, error: errorMessage(err), errorCode: err instanceof ApiError ? err.code : null, errorSource: source.kind });
      return false;
    }
  },
}));
