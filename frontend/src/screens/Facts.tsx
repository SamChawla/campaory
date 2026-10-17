// Confirm the facts (Facts.dc.html). Nothing is written until the required facts are
// confirmed; the server's BR01 answer is final.
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { FactRow } from "../components/FactRow";
import { LimitBanner } from "../components/LimitBanner";
import { ModelBadge } from "../components/ModelBadge";
import { ScreenHeader } from "../components/Title";
import { api, ApiError, errorMessage } from "../lib/api";
import { browserTimezone, isoDateIn, safeTimezone } from "../lib/dates";
import { confirmedFacts, displayBlockers, FACT_LABEL, FACT_ORDER, factByKey, factValue, GATE_KEYS } from "../lib/facts";
import { useStepPath } from "../lib/paths";
import type { FactKey, FactValue } from "../lib/types";
import { useCampaign } from "../store/campaign";
import { useUi } from "../store/ui";

const OPTIONAL = FACT_ORDER.filter((k) => !GATE_KEYS.includes(k));

export function Facts() {
  const doc = useCampaign((s) => s.doc)!;
  const warnings = useCampaign((s) => s.warnings);
  const { confirmFact, confirmAll, removeFact, setNoRegistration, changeFact } = useCampaign.getState();
  const noteError = useUi((s) => s.noteError);
  const navigate = useNavigate();
  const path = useStepPath();
  const [selected, setSelected] = useState<FactKey>(() => GATE_KEYS.find((k) => factByKey(doc.facts, k)?.status !== "confirmed") ?? "event_name");
  const [busyKey, setBusyKey] = useState<FactKey | null>(null);
  const [planning, setPlanning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const blockers = displayBlockers(doc.facts);
  const required = GATE_KEYS.length;
  const done = required - blockers.length;
  const reviewCount = doc.facts.filter((f) => f.status === "needs_review").length;
  const selectedFact = factByKey(doc.facts, selected);
  const hasPlan = doc.plan.length > 0;

  async function save(key: FactKey, value: FactValue) {
    setBusyKey(key);
    setError(null);
    try {
      const result = await changeFact(key, value);
      if (result === "impact") navigate(path("changes"));
    } catch (err) {
      noteError(err);
      setError(`Saved the new value, but could not check which posts it affects. ${errorMessage(err)}`);
    } finally {
      setBusyKey(null);
    }
  }

  async function buildPlan() {
    if (blockers.length) return;
    if (hasPlan) {
      navigate(path("plan"));
      return;
    }
    setPlanning(true);
    setError(null);
    const tz = safeTimezone(factValue(doc.facts, "timezone") || browserTimezone());
    try {
      const res = await api.propose({ facts: confirmedFacts(doc.facts), platforms: doc.platforms, today: isoDateIn(new Date(), tz), timezone: tz });
      useCampaign.getState().setPlan(res.items);
      navigate(path("plan"));
    } catch (err) {
      noteError(err);
      if (err instanceof ApiError && err.code === "blocked") {
        const missing = (err.details as { missing?: string[] }).missing ?? [];
        setError(`These facts need a valid, confirmed value first: ${missing.map((k) => FACT_LABEL[k as FactKey] ?? k).join(", ")}.`);
      } else setError(errorMessage(err));
    } finally {
      setPlanning(false);
    }
  }

  const row = (key: FactKey) => (
    <FactRow
      key={key}
      factKey={key}
      fact={factByKey(doc.facts, key)}
      selected={selected === key}
      onSelect={() => setSelected(key)}
      onSave={save}
      onConfirm={confirmFact}
      onRemove={removeFact}
      onNoRegistration={key === "registration_url" ? setNoRegistration : undefined}
      busy={busyKey === key}
    />
  );

  const optionalShown = OPTIONAL.filter((k) => factByKey(doc.facts, k) || ["venue", "start_time", "end_date", "registration_deadline", "event_mode", "city"].includes(k));
  const optionalHidden = OPTIONAL.filter((k) => !optionalShown.includes(k));

  return (
    <div className="screen">
      <ScreenHeader
        eyebrow={doc.name}
        title="Confirm the facts"
        lead="Every post will use only what is confirmed here. Check each line against its source, fix what is wrong, and confirm."
        aside={<ModelBadge />}
      />

      <div className={`gate${blockers.length ? "" : " is-done"}`} role="status">
        <p>
          <strong>
            {done} of {required} required facts confirmed.
          </strong>{" "}
          {blockers.length ? "The plan stays locked until the last one is." : "You can build the plan."}
        </p>
        <span className="gate-dots" aria-hidden="true">
          {GATE_KEYS.map((k) => (
            <span key={k} className={blockers.includes(k) ? "gate-dot open" : "gate-dot"} />
          ))}
        </span>
      </div>

      {warnings.length > 0 && (
        <ul className="warnings">
          {warnings.map((w) => (
            <li key={w} className="banner banner-warn">
              {w}
            </li>
          ))}
        </ul>
      )}

      <div className="facts-layout">
        <section aria-label="Facts" className="facts-card">
          <h2 className="fact-group">Required before planning</h2>
          {GATE_KEYS.map(row)}
          <h2 className="fact-group">Used when available</h2>
          {optionalShown.map(row)}
          {optionalHidden.length > 0 && (
            <details className="more-facts">
              <summary>More facts ({optionalHidden.length})</summary>
              {optionalHidden.map(row)}
            </details>
          )}
        </section>

        <aside aria-label="Source" className="source-card">
          <div className="source-kicker">Where this came from</div>
          <div className="source-title">{FACT_LABEL[selected]}</div>
          {doc.source.url && <div className="source-url">{doc.source.url}</div>}
          {selectedFact?.source_snippet ? (
            <p className="source-text">
              <mark>{selectedFact.source_snippet}</mark>
            </p>
          ) : (
            <p className="source-text">
              {selectedFact?.source_ref === "manual" ? "You added this yourself." : "This was not found in the source. Add it if you know it, or leave it out."}
            </p>
          )}
          {selected === "timezone" && (
            <p className="source-note">
              <strong>Every reminder date depends on the timezone.</strong> Confirm it or change it.
            </p>
          )}
        </aside>
      </div>

      <div className="screen-foot">
        <Link to="/" className="back-link">
          &larr; Back
        </Link>
        <div className="screen-foot-actions">
          {reviewCount > 0 && (
            <button type="button" className="btn btn-secondary" onClick={confirmAll}>
              Confirm all {reviewCount} to review
            </button>
          )}
          <span className="muted" id="gate-why">
            {blockers.length
              ? `${blockers.length} required ${blockers.length === 1 ? "fact" : "facts"} left: ${blockers.map((k) => FACT_LABEL[k]).join(", ")}`
              : "All required facts confirmed"}
          </span>
          <button
            type="button"
            className="btn btn-highlight btn-lg"
            aria-disabled={blockers.length > 0 || planning}
            aria-describedby="gate-why"
            onClick={buildPlan}
          >
            {planning ? "Making the plan..." : hasPlan ? "Go to the plan" : "Make the plan"}
          </button>
        </div>
      </div>
      {error && (
        <p role="alert" className="field-error">
          {error}
        </p>
      )}
      <LimitBanner />
    </div>
  );
}
