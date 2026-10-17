// Shape the plan (Plan.dc.html). Dates come from /plan/propose; the user can rename, move,
// reschedule, add and remove items.
import { useId, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { LimitBanner } from "../components/LimitBanner";
import { ModelBadge } from "../components/ModelBadge";
import { PlatformDot } from "../components/PlatformDot";
import { ScreenHeader } from "../components/Title";
import { api, errorMessage } from "../lib/api";
import { browserTimezone, formatDay, formatIsoDate, formatTime, isoDateIn, isoToLocalInput, localInputToIso, safeTimezone } from "../lib/dates";
import { confirmedFacts, FACT_LABEL, factByKey, factValue } from "../lib/facts";
import { useStepPath } from "../lib/paths";
import { PLATFORM_NAME } from "../lib/share";
import type { Fact, PlanItem, Stage } from "../lib/types";
import { orderedPlan, useCampaign } from "../store/campaign";
import { useGeneration } from "../store/generation";
import { useUi } from "../store/ui";

export const STAGE_LABEL: Record<Stage, string> = { pre: "Before the event", event: "On the day", post: "After" };
const STAGES: Stage[] = ["pre", "event", "post"];

/** Keeps a date on the right side of the event for its stage. */
function stageProblem(stage: Stage, local: string, facts: Fact[]): string | null {
  const day = local.slice(0, 10);
  const start = factValue(facts, "start_date");
  const end = factValue(facts, "end_date") || start;
  if (!/^\d{4}-\d{2}-\d{2}$/.test(start)) return null;
  if (stage === "pre" && day >= start) return `Before-the-event posts must be dated before ${formatIsoDate(start)}.`;
  if (stage === "event" && (day < start || day > end)) return `Event-day posts must be dated ${start === end ? `on ${formatIsoDate(start)}` : `between ${formatIsoDate(start)} and ${formatIsoDate(end)}`}.`;
  if (stage === "post" && day <= end) return `After-the-event posts must be dated after ${formatIsoDate(end)}.`;
  return null;
}

function ItemCard({ item, tz, first, last, hasPublished }: { item: PlanItem; tz: string; first: boolean; last: boolean; hasPublished: boolean }) {
  const doc = useCampaign((s) => s.doc)!;
  const { updatePlanItem, removePlanItem, movePlanItem } = useCampaign.getState();
  const id = useId();
  const [editing, setEditing] = useState(item.title === "New post" && !item.purpose);
  const [title, setTitle] = useState(item.title);
  const [purpose, setPurpose] = useState(item.purpose);
  const [when, setWhen] = useState(item.scheduled_for ? isoToLocalInput(item.scheduled_for, tz) : "");
  const [stage, setStage] = useState<Stage>(item.stage);
  const [error, setError] = useState<string | null>(null);

  function save() {
    if (!title.trim()) return setError("Give the item a title.");
    const iso = when ? localInputToIso(when, tz) : null;
    if (when && !iso) return setError("Enter a date and time.");
    if (!iso) return setError("Pick a date and time.");
    const problem = stageProblem(stage, when, doc.facts);
    if (problem) return setError(problem);
    updatePlanItem(item.id, { title, purpose, scheduled_for: iso, stage });
    setError(null);
    setEditing(false);
  }

  return (
    <article className="plan-item card" aria-labelledby={`${id}-t`}>
      <div className="plan-when">
        <div className="plan-day">{formatDay(item.scheduled_for, tz)}</div>
        <div className="plan-time">{formatTime(item.scheduled_for, tz)}</div>
      </div>
      <div className="plan-main">
        <h3 id={`${id}-t`} className="plan-title">
          {item.title}
        </h3>
        {item.purpose && <p className="plan-purpose">{item.purpose}</p>}
        {item.fact_keys.length > 0 && <p className="small muted">Uses: {item.fact_keys.map((k) => FACT_LABEL[k].toLowerCase()).join(", ")}</p>}
      </div>
      <ul className="plan-dots" aria-label="Platforms">
        {doc.platforms.map((p) => (
          <li key={p} title={PLATFORM_NAME[p]}>
            <PlatformDot platform={p} />
          </li>
        ))}
      </ul>
      <div className="plan-actions">
        <button type="button" className="link-btn" onClick={() => setEditing(!editing)} aria-expanded={editing}>
          Edit
        </button>
        <button type="button" className="link-btn" onClick={() => movePlanItem(item.id, -1)} disabled={first} aria-label={`Move ${item.title} up`}>
          Up
        </button>
        <button type="button" className="link-btn" onClick={() => movePlanItem(item.id, 1)} disabled={last} aria-label={`Move ${item.title} down`}>
          Down
        </button>
        <button
          type="button"
          className="link-btn muted"
          onClick={() => removePlanItem(item.id)}
          disabled={hasPublished}
          title={hasPublished ? "This item has a published post, so it stays." : undefined}
          aria-label={`Remove ${item.title}`}
        >
          Remove
        </button>
      </div>
      {editing && (
        <div className="plan-edit">
          <label htmlFor={`${id}-title`}>Title</label>
          <input id={`${id}-title`} value={title} maxLength={120} onChange={(e) => setTitle(e.target.value)} />
          <label htmlFor={`${id}-purpose`}>Purpose</label>
          <input id={`${id}-purpose`} value={purpose} onChange={(e) => setPurpose(e.target.value)} />
          <div className="plan-edit-row">
            <div>
              <label htmlFor={`${id}-when`}>Date and time ({tz})</label>
              <input id={`${id}-when`} type="datetime-local" value={when} onChange={(e) => setWhen(e.target.value)} aria-describedby={error ? `${id}-err` : undefined} />
            </div>
            <div>
              <label htmlFor={`${id}-stage`}>Stage</label>
              <select id={`${id}-stage`} value={stage} onChange={(e) => setStage(e.target.value as Stage)}>
                {STAGES.map((s) => (
                  <option key={s} value={s}>
                    {STAGE_LABEL[s]}
                  </option>
                ))}
              </select>
            </div>
          </div>
          {error && (
            <p id={`${id}-err`} role="alert" className="field-error">
              {error}
            </p>
          )}
          <div className="row-actions">
            <button type="button" className="btn btn-primary" onClick={save}>
              Save item
            </button>
            <button type="button" className="btn btn-text" onClick={() => setEditing(false)}>
              Cancel
            </button>
          </div>
        </div>
      )}
    </article>
  );
}

export function Plan() {
  const doc = useCampaign((s) => s.doc)!;
  const addPlanItem = useCampaign((s) => s.addPlanItem);
  const setPlan = useCampaign((s) => s.setPlan);
  const planNotice = useCampaign((s) => s.planNotice);
  const generation = useGeneration();
  const noteError = useUi((s) => s.noteError);
  const navigate = useNavigate();
  const path = useStepPath();
  const [error, setError] = useState<string | null>(null);
  const [proposing, setProposing] = useState(false);

  const tz = safeTimezone(factValue(doc.facts, "timezone") || browserTimezone());
  const plan = orderedPlan(doc);
  const total = plan.length * doc.platforms.length;
  const start = factValue(doc.facts, "start_date");
  const missing = (["venue", "start_time"] as const).filter((k) => factByKey(doc.facts, k)?.status !== "confirmed");
  const hasPosts = doc.posts.length > 0;
  const publishedItems = new Set(doc.posts.filter((p) => p.status === "published").map((p) => p.plan_item_id));

  async function propose() {
    setProposing(true);
    setError(null);
    try {
      const res = await api.propose({ facts: confirmedFacts(doc.facts), platforms: doc.platforms, today: isoDateIn(new Date(), tz), timezone: tz });
      setPlan(res.items, res.notice);
    } catch (err) {
      noteError(err);
      setError(errorMessage(err));
    } finally {
      setProposing(false);
    }
  }

  function write() {
    if (plan.length === 0 || generation.running) return;
    navigate(path("posts"));
    void generation.run();
  }

  function add(stage: Stage) {
    const ref = plan.filter((p) => p.stage === stage).at(-1)?.scheduled_for ?? null;
    addPlanItem(stage, ref);
  }

  return (
    <div className="screen">
      <ScreenHeader
        eyebrow={[doc.name, start ? formatIsoDate(start) : null, `all times ${tz}`].filter(Boolean).join(" · ")}
        title="Shape the plan"
        lead={
          plan.length
            ? `${plan.length} ${plan.length === 1 ? "item" : "items"} to post across the event. Rename, move or remove any of them before drafting.`
            : "There is no plan yet. Make one from your confirmed facts."
        }
      />

      {planNotice && (
        <p className="banner banner-warn" role="status">
          {planNotice}
        </p>
      )}

      <div className="split">
        <section aria-label="Campaign items" className="plan-list">
          {plan.length === 0 && (
            <button type="button" className="btn btn-primary btn-lg" onClick={propose} aria-disabled={proposing}>
              {proposing ? "Making the plan..." : "Make the plan"}
            </button>
          )}
          {plan.length > 0 &&
            STAGES.map((stage) => {
              const items = plan.filter((p) => p.stage === stage);
              return (
                <div key={stage} className="plan-stage">
                  <h2 className="stage-title">{STAGE_LABEL[stage]}</h2>
                  <div className="plan-grid">
                    {items.map((item) => (
                      <ItemCard
                        key={item.id}
                        item={item}
                        tz={tz}
                        first={plan[0].id === item.id}
                        last={plan.at(-1)!.id === item.id}
                        hasPublished={publishedItems.has(item.id)}
                      />
                    ))}
                    <button type="button" className="add-item" onClick={() => add(stage)}>
                      + Add an item
                    </button>
                  </div>
                </div>
              );
            })}
          {error && (
            <p role="alert" className="field-error">
              {error}
            </p>
          )}
        </section>

        <aside aria-label="Summary" className="summary-card">
          <div className="summary-kicker">{hasPosts ? "Drafted" : "Ready to draft"}</div>
          <div className="summary-number">{hasPosts ? doc.posts.length : total}</div>
          <div className="summary-sub">
            posts from {plan.length} {plan.length === 1 ? "item" : "items"}
          </div>
          <dl className="summary-counts">
            {doc.platforms.map((p) => (
              <div key={p}>
                <dt>{PLATFORM_NAME[p]}</dt>
                <dd>{plan.length}</dd>
              </div>
            ))}
          </dl>
          {missing.length > 0 && (
            <p className="summary-note">
              <strong>{missing.map((k) => FACT_LABEL[k]).join(" and ")} {missing.length === 1 ? "is" : "are"} not confirmed.</strong> Posts that need{" "}
              {missing.length === 1 ? "it" : "them"} will ask you to fill it in before approval.
            </p>
          )}
          <div className="summary-cta">
            {hasPosts ? (
              <Link to={path("posts")} className="btn btn-primary btn-lg btn-block">
                Review the posts
              </Link>
            ) : (
              <button type="button" className="btn btn-primary btn-lg btn-block" onClick={write} aria-disabled={plan.length === 0 || generation.running}>
                Write {total} posts
              </button>
            )}
            <ModelBadge />
          </div>
          <LimitBanner onRetry={hasPosts ? undefined : write} />
          <Link to={path("facts")} className="summary-back">
            Back to facts
          </Link>
        </aside>
      </div>
    </div>
  );
}
