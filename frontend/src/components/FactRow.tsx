// One fact: label, value (editable inline), status chip, source line, confirm (UI_SPEC 3).
import { useId, useState } from "react";
import { FACT_HINT, FACT_LABEL, factText, isFilled, LANGUAGE_LABEL, LIST_KEYS, parseFactInput } from "../lib/facts";
import type { Fact, FactKey, FactValue, Language } from "../lib/types";
import { StatusChip } from "./StatusChip";

const TIMEZONES = ["Asia/Kolkata", "Asia/Dubai", "Asia/Singapore", "Europe/London", "Europe/Berlin", "America/New_York", "America/Los_Angeles", "UTC"];

function sourceLine(fact: Fact | undefined): string {
  if (!fact) return "Not on the page. Add it if you know it.";
  if (fact.key === "registration_url" && fact.not_applicable) return "You said there is no registration.";
  if (fact.source_snippet) return `Found in: "${fact.source_snippet}"`;
  if (fact.source_ref === "manual") return isFilled(fact.value) ? "Added by you" : "Not added yet";
  return "Searched the page, nothing found";
}

interface Props {
  factKey: FactKey;
  fact: Fact | undefined;
  selected: boolean;
  onSelect: () => void;
  onSave: (key: FactKey, value: FactValue) => Promise<void> | void;
  onConfirm: (key: FactKey) => void;
  onRemove: (key: FactKey) => void;
  onNoRegistration?: (on: boolean) => void;
  busy?: boolean;
}

export function FactRow({ factKey, fact, selected, onSelect, onSave, onConfirm, onRemove, onNoRegistration, busy }: Props) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);
  const id = useId();
  const label = FACT_LABEL[factKey];
  const status = fact?.status ?? "missing";
  const filled = fact ? isFilled(fact.value) : false;
  const na = factKey === "registration_url" && fact?.not_applicable;
  const isList = LIST_KEYS.includes(factKey);

  function startEdit() {
    if (!fact) setDraft(factKey === "language" ? "en" : "");
    else if (typeof fact.value === "string" && (factKey === "language" || factKey === "event_mode")) setDraft(fact.value);
    else setDraft(factText(fact));
    setError(null);
    setEditing(true);
    onSelect();
  }

  async function save() {
    const value = parseFactInput(factKey, draft);
    if (!isFilled(value)) {
      setError(`Enter the ${label.toLowerCase()}, or press Cancel.`);
      return;
    }
    await onSave(factKey, value);
    setEditing(false);
  }

  const inputId = `${id}-input`;
  const hintId = `${id}-hint`;
  const errId = `${id}-err`;
  const describedBy = [FACT_HINT[factKey] ? hintId : null, error ? errId : null].filter(Boolean).join(" ") || undefined;

  let control;
  if (factKey === "language") {
    control = (
      <select id={inputId} value={draft} onChange={(e) => setDraft(e.target.value)} aria-describedby={describedBy}>
        {(Object.keys(LANGUAGE_LABEL) as Language[]).map((l) => (
          <option key={l} value={l}>
            {LANGUAGE_LABEL[l]}
          </option>
        ))}
      </select>
    );
  } else if (factKey === "event_mode") {
    control = (
      <select id={inputId} value={draft} onChange={(e) => setDraft(e.target.value)} aria-describedby={describedBy}>
        <option value="">Choose</option>
        <option value="offline">In person</option>
        <option value="online">Online</option>
        <option value="hybrid">Hybrid</option>
      </select>
    );
  } else if (isList || factKey === "short_description" || factKey === "audience") {
    control = <textarea id={inputId} rows={isList ? 4 : 2} value={draft} onChange={(e) => setDraft(e.target.value)} aria-describedby={describedBy} aria-invalid={!!error} />;
  } else {
    const type =
      factKey === "start_date" || factKey === "end_date" || factKey === "registration_deadline"
        ? "date"
        : factKey === "start_time" || factKey === "end_time"
          ? "time"
          : factKey === "registration_url"
            ? "url"
            : "text";
    control = (
      <input
        id={inputId}
        type={type}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        aria-describedby={describedBy}
        aria-invalid={!!error}
        list={factKey === "timezone" ? `${id}-tz` : undefined}
      />
    );
  }

  return (
    <div className={`fact-row${selected ? " is-selected" : ""}`} data-fact={factKey}>
      <div className="fact-label">{label}</div>
      <div className="fact-body">
        {na ? (
          <div className="fact-value">No registration</div>
        ) : filled && fact ? (
          <div className="fact-value">{factText(fact)}</div>
        ) : (
          <div className="fact-value muted">Not found on the page</div>
        )}
        <button type="button" className="fact-source" onClick={onSelect} aria-pressed={selected}>
          {sourceLine(fact)}
        </button>
        {editing && (
          <div className="fact-edit">
            <label htmlFor={inputId}>{label}</label>
            {control}
            {factKey === "timezone" && (
              <datalist id={`${id}-tz`}>
                {TIMEZONES.map((tz) => (
                  <option key={tz} value={tz} />
                ))}
              </datalist>
            )}
            {FACT_HINT[factKey] && (
              <p id={hintId} className="small muted">
                {FACT_HINT[factKey]}
              </p>
            )}
            {error && (
              <p id={errId} role="alert" className="field-error">
                {error}
              </p>
            )}
            <div className="row-actions">
              <button type="button" className="btn btn-primary" onClick={save} disabled={busy}>
                {busy ? "Checking..." : `Confirm ${label.toLowerCase()}`}
              </button>
              <button type="button" className="btn btn-secondary" onClick={() => setEditing(false)}>
                Cancel
              </button>
              {fact && filled && !fact.critical && (
                <button
                  type="button"
                  className="btn btn-text"
                  onClick={() => {
                    onRemove(factKey);
                    setEditing(false);
                  }}
                >
                  Remove
                </button>
              )}
            </div>
          </div>
        )}
        {factKey === "registration_url" && onNoRegistration && !editing && (
          <label className="check">
            <input type="checkbox" checked={!!na} onChange={(e) => onNoRegistration(e.target.checked)} />
            No registration for this event
          </label>
        )}
      </div>
      <div className="fact-status">
        <StatusChip status={na ? "confirmed" : status} />
      </div>
      <div className="fact-actions">
        {!editing && status === "needs_review" && filled && (
          <button type="button" className="btn btn-small btn-primary" onClick={() => onConfirm(factKey)} aria-label={`Confirm ${label.toLowerCase()}`}>
            Confirm
          </button>
        )}
        {!editing && !na && (
          <button type="button" className="link-btn" onClick={startEdit} aria-label={`${filled ? "Edit" : "Add"} ${label.toLowerCase()}`}>
            {filled ? "Edit" : "Add"}
          </button>
        )}
      </div>
    </div>
  );
}
