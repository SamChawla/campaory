// "Demo model" whenever the server runs the mock provider or a response came from it
// (UI_SPEC 7.6, CLAUDE rule 9). Never hidden.
import { useCampaign } from "../store/campaign";
import { isDemoModel, useSession } from "../store/session";

export function ModelBadge() {
  const config = useSession((s) => s.config);
  const meta = useCampaign((s) => s.lastMeta);
  if (!isDemoModel(config, meta)) return null;
  return (
    <span className="model-badge" title="Drafts come from a built-in demo writer, not the real model.">
      Demo model
    </span>
  );
}
