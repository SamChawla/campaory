// One platform variant: text, live counter from /posts/validate, validation messages, status,
// and the actions allowed for that status. Approval follows the server's answer (BR02);
// published posts are read-only (BR03); opening a platform never marks published (BR05).
import { useEffect, useId, useState } from "react";
import { api, errorMessage } from "../lib/api";
import { formatDateTime, isoToLocalInput, localInputToIso } from "../lib/dates";
import { confirmedFacts, FACT_LABEL, factValue } from "../lib/facts";
import { copyFor, openPlatform, PLATFORM_NAME } from "../lib/share";
import type { Post, ReviseInstruction, Validation, ValidateResponse } from "../lib/types";
import { approvalBlockers, useCampaign } from "../store/campaign";
import { useUi } from "../store/ui";
import { PlatformDot } from "./PlatformDot";
import { StatusChip } from "./StatusChip";

const VALIDATE_DEBOUNCE_MS = 350;

/** Debounced server validation of `text`. Returns the latest answer for exactly that text. */
export function useServerValidation(post: Post, text: string, enabled: boolean): { result: ValidateResponse | null; error: boolean } {
  const [state, setState] = useState<{ text: string; result: ValidateResponse | null; error: boolean }>({ text: "", result: null, error: false });
  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      const doc = useCampaign.getState().doc;
      if (!doc) return;
      try {
        const result = await api.validate({ platform: post.platform, text, facts: confirmedFacts(doc.facts) }, controller.signal);
        setState({ text, result, error: false });
      } catch {
        if (!controller.signal.aborted) setState({ text, result: null, error: true });
      }
    }, VALIDATE_DEBOUNCE_MS);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [post.platform, text, enabled]);
  return state.text === text ? { result: state.result, error: state.error } : { result: null, error: false };
}

function counterText(platform: Post["platform"], v: Validation | undefined): string {
  if (!v) return "Counting...";
  const base = `${v.length.toLocaleString("en-GB")} of ${v.limit.toLocaleString("en-GB")} characters`;
  const tags = platform === "instagram" && typeof v.hashtags === "number" ? ` ${v.hashtags} of 30 hashtags.` : "";
  const link = platform === "x" ? " Links count as 23." : "";
  return `${base}.${tags}${link}`;
}

function PostText({ text, placeholders }: { text: string; placeholders: string[] }) {
  if (!placeholders.length) return <p className="post-text">{text}</p>;
  const pattern = new RegExp(`(${placeholders.map((p) => p.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})`, "g");
  return (
    <p className="post-text">
      {text.split(pattern).map((part, i) => (placeholders.includes(part) ? <mark key={i}>{part}</mark> : <span key={i}>{part}</span>))}
    </p>
  );
}

const MORE: { id: ReviseInstruction; label: string }[] = [
  { id: "make_longer", label: "Make longer" },
  { id: "warmer", label: "Warmer" },
  { id: "more_formal", label: "More formal" },
];

export function PostCard({ post, tz, active = true }: { post: Post; tz: string; active?: boolean }) {
  const id = useId();
  const doc = useCampaign((s) => s.doc)!;
  const entry = useCampaign((s) => s.validations[post.id]);
  const setValidation = useCampaign((s) => s.setValidation);
  const editPost = useCampaign((s) => s.editPost);
  const applyRevision = useCampaign((s) => s.applyRevision);
  const approvePost = useCampaign((s) => s.approvePost);
  const schedulePost = useCampaign((s) => s.schedulePost);
  const clearReminder = useCampaign((s) => s.clearReminder);
  const markPublished = useCampaign((s) => s.markPublished);
  const restoreVersion = useCampaign((s) => s.restoreVersion);
  const toast = useUi((s) => s.toast);
  const noteError = useUi((s) => s.noteError);

  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(post.text);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [panel, setPanel] = useState<null | "schedule" | "publish">(null);
  const [when, setWhen] = useState("");
  const [publishedUrl, setPublishedUrl] = useState("");

  const published = post.status === "published";
  const name = PLATFORM_NAME[post.platform];

  // Keep the stored validation in step with the stored text.
  const storedFresh = entry?.text === post.text;
  const stored = useServerValidation(post, post.text, !published && !storedFresh);
  useEffect(() => {
    if (stored.result) setValidation(post.id, post.text, stored.result);
  }, [stored.result, post.id, post.text, setValidation]);

  // Live counter while editing.
  const live = useServerValidation(post, draft, editing);

  const shown = editing ? live.result : storedFresh ? entry.result : null;
  const blockers = approvalBlockers(post, entry, doc.facts);
  const canApprove = blockers !== null && blockers.length === 0;
  const issues = shown?.validation.issues ?? [];
  const seen = new Set<string>([post.text]);
  const earlier = [...post.versions].reverse().filter((v) => !seen.has(v.text) && seen.add(v.text));

  async function revise(instruction: ReviseInstruction) {
    setBusy(instruction);
    setError(null);
    try {
      const res = await api.revise({ facts: confirmedFacts(doc.facts), post: { platform: post.platform, text: post.text, facts_used: post.facts_used }, instruction });
      applyRevision(post.id, res, instruction);
    } catch (err) {
      noteError(err);
      setError(errorMessage(err));
    } finally {
      setBusy(null);
    }
  }

  function saveEdit() {
    editPost(post.id, draft);
    if (live.result) setValidation(post.id, draft, live.result);
    setEditing(false);
  }

  async function copy() {
    const res = await copyFor(post.platform, post.text);
    toast(res.message);
  }

  async function open() {
    const res = await openPlatform(post.platform, post.text, factValue(doc.facts, "registration_url") || null);
    if (res.blockedUrl) toast(`${res.message}. The new tab was blocked.`, { href: res.blockedUrl, label: `Open ${name}` });
    else toast(res.message);
  }

  function setReminder() {
    const iso = localInputToIso(when, tz);
    if (!iso || new Date(iso).getTime() <= Date.now()) {
      setError("Pick a reminder time in the future.");
      return;
    }
    setError(null);
    schedulePost(post.id, iso);
    setPanel(null);
    toast(`Reminder set for ${formatDateTime(iso, tz)}`);
  }

  const textId = `${id}-text`;
  const counterId = `${id}-counter`;
  const errId = `${id}-err`;

  return (
    <article className={`post-card${active ? " is-active" : ""}${published ? " is-published" : ""}`} aria-labelledby={`${id}-h`} data-platform={post.platform}>
      <header className="post-head">
        <div className="post-name">
          <PlatformDot platform={post.platform} />
          <h3 id={`${id}-h`}>{name}</h3>
        </div>
        <StatusChip status={post.status} />
      </header>

      {editing ? (
        <div className="post-edit">
          <label htmlFor={textId}>Text for {name}</label>
          <textarea id={textId} value={draft} rows={8} onChange={(e) => setDraft(e.target.value)} aria-describedby={counterId} />
        </div>
      ) : (
        <div className="post-body">
          <PostText text={post.text} placeholders={post.placeholders} />
        </div>
      )}

      {post.change_reason && !published && <p className="post-note note-lime">Changed fact: {post.change_reason}</p>}
      {issues.map((i) => (
        <p key={i.code} className={`post-note ${i.level === "error" ? "note-peach" : "note-plain"}`}>
          {i.level === "error" ? "Blocks approval: " : "Note: "}
          {i.message}
        </p>
      ))}
      {!editing && blockers && blockers.length > 0 && !published && (
        <ul id={`${id}-why`} className="post-blockers" aria-label="Why this cannot be approved yet">
          {blockers
            .filter((b) => !issues.some((i) => i.message === b))
            .map((b) => (
              <li key={b} className="post-note note-peach">
                {b}
              </li>
            ))}
        </ul>
      )}

      <p className="post-meta small">Uses: {post.facts_used.length ? post.facts_used.map((k) => FACT_LABEL[k].toLowerCase()).join(", ") : "no facts"}</p>
      <p id={counterId} className="post-meta small" aria-live={editing ? "polite" : undefined}>
        {editing && live.error ? "Could not check the length. Try again." : counterText(post.platform, shown?.validation)}
      </p>
      {post.status === "scheduled" && post.reminder_at && <p className="post-meta small">Reminder: {formatDateTime(post.reminder_at, tz)}</p>}
      {published && (
        <p className="post-locked">
          <StatusChip status="published" label={`Published ${post.published_at ? formatDateTime(post.published_at, tz) : ""}. Left as is.`} />
          {post.published_url && (
            <a href={post.published_url} target="_blank" rel="noopener noreferrer">
              View post
            </a>
          )}
        </p>
      )}
      {error && (
        <p id={errId} role="alert" className="field-error">
          {error}
        </p>
      )}

      {editing ? (
        <div className="post-actions">
          <button type="button" className="btn btn-primary" onClick={saveEdit}>
            Save text
          </button>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => {
              setDraft(post.text);
              setEditing(false);
            }}
          >
            Cancel
          </button>
          {(post.status === "approved" || post.status === "scheduled") && <span className="small muted">Saving an edit sends this post back to draft.</span>}
        </div>
      ) : (
        <div className="post-actions">
          {(post.status === "draft" || post.status === "needs_review") && (
            <button
              type="button"
              className="btn btn-primary post-primary"
              aria-disabled={!canApprove}
              aria-describedby={!canApprove && blockers?.length ? `${id}-why` : undefined}
              onClick={() => canApprove && approvePost(post.id)}
            >
              {blockers === null ? "Checking..." : "Approve"}
            </button>
          )}
          {(post.status === "approved" || post.status === "scheduled" || published) && (
            <>
              <button type="button" className="btn btn-secondary post-primary" onClick={copy}>
                Copy text
              </button>
              {post.platform !== "instagram" && (
                <button type="button" className="btn btn-secondary" onClick={open}>
                  Open {name}
                </button>
              )}
            </>
          )}
          {!published && (
            <>
              <button
                type="button"
                className="link-btn"
                onClick={() => {
                  setDraft(post.text);
                  setEditing(true);
                }}
              >
                Edit
              </button>
              <button type="button" className="link-btn" onClick={() => revise("make_shorter")} disabled={busy !== null}>
                {busy === "make_shorter" ? "Shortening..." : "Make shorter"}
              </button>
              <details className="more">
                <summary className="link-btn">More changes</summary>
                <div className="more-menu">
                  {MORE.map((m) => (
                    <button key={m.id} type="button" className="link-btn" onClick={() => revise(m.id)} disabled={busy !== null}>
                      {busy === m.id ? "Rewriting..." : m.label}
                    </button>
                  ))}
                </div>
              </details>
            </>
          )}
          {post.status === "approved" && (
            <button
              type="button"
              className="link-btn"
              onClick={() => {
                setWhen(post.reminder_at ? isoToLocalInput(post.reminder_at, tz) : "");
                setPanel(panel === "schedule" ? null : "schedule");
              }}
              aria-expanded={panel === "schedule"}
            >
              Set reminder
            </button>
          )}
          {post.status === "scheduled" && (
            <button type="button" className="link-btn" onClick={() => clearReminder(post.id)}>
              Clear reminder
            </button>
          )}
          {(post.status === "approved" || post.status === "scheduled") && (
            <button type="button" className="link-btn" onClick={() => setPanel(panel === "publish" ? null : "publish")} aria-expanded={panel === "publish"}>
              Mark published
            </button>
          )}
        </div>
      )}

      {panel === "schedule" && (
        <div className="post-panel">
          <label htmlFor={`${id}-when`}>Remind me to post at ({tz})</label>
          <input id={`${id}-when`} type="datetime-local" value={when} onChange={(e) => setWhen(e.target.value)} />
          <div className="row-actions">
            <button type="button" className="btn btn-primary" onClick={setReminder}>
              Set reminder
            </button>
            <button type="button" className="btn btn-text" onClick={() => setPanel(null)}>
              Cancel
            </button>
          </div>
        </div>
      )}
      {panel === "publish" && (
        <div className="post-panel">
          <p className="small">Only mark it once you have posted it yourself. Published posts are never changed.</p>
          <label htmlFor={`${id}-url`}>Link to the post (optional)</label>
          <input id={`${id}-url`} type="url" value={publishedUrl} onChange={(e) => setPublishedUrl(e.target.value)} />
          <div className="row-actions">
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => {
                markPublished(post.id, publishedUrl);
                setPanel(null);
              }}
            >
              Mark published
            </button>
            <button type="button" className="btn btn-text" onClick={() => setPanel(null)}>
              Cancel
            </button>
          </div>
        </div>
      )}

      {earlier.length > 0 && !published && (
        <details className="versions">
          <summary className="small">Earlier versions ({earlier.length})</summary>
          <ol>
            {earlier.map((v) => (
              <li key={v.id}>
                <p className="post-text small">{v.text}</p>
                <button type="button" className="link-btn small" onClick={() => restoreVersion(post.id, v.id)}>
                  Use this text
                </button>
              </li>
            ))}
          </ol>
        </details>
      )}
    </article>
  );
}
