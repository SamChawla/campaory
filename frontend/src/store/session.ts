// Who is signed in and how the server is configured (`/api/me`, `/api/config`).
import { create } from "zustand";
import { api } from "../lib/api";
import type { AppConfig, Meta, User } from "../lib/types";

interface SessionState {
  user: User | null;
  config: AppConfig | null;
  loaded: boolean;
  load(): Promise<void>;
  refreshMe(): Promise<User | null>;
  signOut(): Promise<void>;
}

export const useSession = create<SessionState>()((set) => ({
  user: null,
  config: null,
  loaded: false,

  async load() {
    const [config, me] = await Promise.allSettled([api.config(), api.me()]);
    set({
      config: config.status === "fulfilled" ? config.value : null,
      user: me.status === "fulfilled" ? me.value.user : null,
      loaded: true,
    });
  },

  async refreshMe() {
    try {
      const me = await api.me();
      set({ user: me.user });
      return me.user;
    } catch {
      return null;
    }
  },

  async signOut() {
    await api.logout();
    set({ user: null });
  },
}));

export function isDemoModel(config: AppConfig | null, meta: Meta | null | undefined): boolean {
  return Boolean(config?.llm_is_mock) || meta?.provider === "mock";
}

export function hasGoogle(config: AppConfig | null): boolean {
  return Boolean(config?.auth_providers?.includes("google"));
}

export function hasGithub(config: AppConfig | null): boolean {
  return Boolean(config?.auth_providers?.includes("github"));
}
