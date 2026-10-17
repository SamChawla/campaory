// Transient UI state: toasts, the rate-limit banner, the sign-in sheet, the import status.
import { create } from "zustand";
import { RateLimited } from "../lib/api";

export interface Toast {
  id: number;
  message: string;
  link?: { href: string; label: string };
}

export type ImportState =
  | { state: "idle" }
  | { state: "saving" }
  | { state: "failed"; message: string }
  | { state: "limit"; message: string };

interface UiState {
  toasts: Toast[];
  limitUntil: number | null;
  signInOpen: boolean;
  importState: ImportState;
  guestBannerHidden: boolean;
  toast(message: string, link?: Toast["link"]): void;
  dismissToast(id: number): void;
  noteError(err: unknown): void;
  clearLimit(): void;
  openSignIn(): void;
  closeSignIn(): void;
  setImport(s: ImportState): void;
  hideGuestBanner(): void;
}

export const TOAST_MS = 3000;
const BANNER_KEY = "campaory.guestBannerHidden";
let nextId = 1;

function bannerHidden(): boolean {
  try {
    return window.sessionStorage.getItem(BANNER_KEY) === "1";
  } catch {
    return false;
  }
}

export const useUi = create<UiState>()((set, get) => ({
  toasts: [],
  limitUntil: null,
  signInOpen: false,
  importState: { state: "idle" },
  guestBannerHidden: bannerHidden(),

  toast(message, link) {
    const id = nextId++;
    set((s) => ({ toasts: [...s.toasts, { id, message, link }] }));
    setTimeout(() => get().dismissToast(id), link ? TOAST_MS * 2 : TOAST_MS);
  },
  dismissToast: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),

  noteError(err) {
    if (err instanceof RateLimited) set({ limitUntil: Date.now() + err.retryAfterSeconds * 1000 });
  },
  clearLimit: () => set({ limitUntil: null }),

  openSignIn: () => set({ signInOpen: true }),
  closeSignIn: () => set({ signInOpen: false }),
  setImport: (importState) => set({ importState }),

  hideGuestBanner() {
    try {
      window.sessionStorage.setItem(BANNER_KEY, "1");
    } catch {
      // Hidden for this page view only.
    }
    set({ guestBannerHidden: true });
  },
}));
