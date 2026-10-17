// Batched post generation with progress and per-item retry (T3.6).
import { create } from "zustand";
import { generateAll } from "../lib/api";
import { confirmedFacts } from "../lib/facts";
import { orderedPlan, useCampaign } from "./campaign";
import { useUi } from "./ui";

interface GenerationState {
  running: boolean;
  done: number;
  total: number;
  failed: { plan_item_id: string; error: string }[];
  run(itemIds?: string[]): Promise<void>;
}

export const useGeneration = create<GenerationState>()((set, get) => ({
  running: false,
  done: 0,
  total: 0,
  failed: [],

  async run(itemIds) {
    const doc = useCampaign.getState().doc;
    if (!doc || get().running) return;
    const plan = orderedPlan(doc).filter((p) => !itemIds || itemIds.includes(p.id));
    if (plan.length === 0) return;
    set({ running: true, done: 0, total: plan.length, failed: get().failed.filter((f) => !plan.some((p) => p.id === f.plan_item_id)) });
    const res = await generateAll(
      {
        facts: confirmedFacts(doc.facts),
        language: doc.language,
        tone: doc.tone,
        platforms: doc.platforms,
        items: plan.map((p) => ({ id: p.id, title: p.title, purpose: p.purpose, stage: p.stage, fact_keys: p.fact_keys })),
      },
      (done, total) => set({ done, total }),
    );
    useCampaign.getState().applyGeneration(res.posts);
    useCampaign.getState().setMeta(res.meta);
    if (res.rateLimited) useUi.getState().noteError(res.rateLimited);
    set((s) => ({ running: false, failed: [...s.failed, ...res.failed] }));
  },
}));
