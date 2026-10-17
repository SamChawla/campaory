import { useCampaign } from "../store/campaign";
import type { Step } from "../store/importer";

export const STEP_LABEL: Record<Step, string> = {
  facts: "Facts",
  plan: "Plan",
  posts: "Posts",
  changes: "Changes",
  upcoming: "Upcoming",
};

export const STEP_ORDER: Step[] = ["facts", "plan", "posts", "changes", "upcoming"];

export function stepPath(step: Step, mode: "guest" | "saved", id: string | undefined): string {
  return mode === "saved" && id ? `/c/${id}/${step}` : `/${step}`;
}

/** Path builder for the current campaign (guest or saved). */
export function useStepPath(): (step: Step) => string {
  const mode = useCampaign((s) => s.mode);
  const id = useCampaign((s) => s.doc?.id);
  return (step) => stepPath(step, mode, id);
}
