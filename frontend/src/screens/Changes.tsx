// A fact changed (Change.dc.html): what changed, the affected posts with proposed edits, and
// published posts that stay exactly as they are (BR03, BR04).
import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Diff } from "../components/Diff";
import { LimitBanner } from "../components/LimitBanner";
import { ModelBadge } from "../components/ModelBadge";
import { PlatformDot } from "../components/PlatformDot";
import { StatusChip } from "../components/StatusChip";
import { ScreenHeader } from "../components/Title";
import { errorMessage } from "../lib/api";
import { browserTimezone, formatDateTime, safeTimezone } from "../lib/dates";
import { FACT_LABEL, FACT_ORDER, factByKey, factText, factValue, isFilled, parseFactInput } from "../lib/facts";
import { useStepPath } from "../lib/paths";
import { PLATFORM_NAME } from "../lib/share";
import type { FactKey, FactValue, Post } from "../lib/types";
import { useCampaign } from "../store/campaign";
import { useUi } from "../store/ui";

function show(key: FactKey, value: FactValue): string {
  return factText({ key, value }) || "(empty)";
}

function ChangeForm() {
  const doc = useCampaign((s) => s.doc)!;
  const changeFact = useCampaign((s) => s.changeFact);
  const noteError = useUi((s) => s.noteError);
  const toast = useUi((s) => s.toast);
  const editable = FACT_ORDER.filter((k) => factByKey(doc.facts, k)?.status === "confirmed" && k !== "language");
  const [key, setKey] = useState<FactKey>(editable[0] ?? "start_time");
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const current = factByKey(doc.facts, key);

  async function submit(e: FormEvent) {
    e.preventDefault();
    const parsed = parseFactInput(key, value);
    if (!isFilled(parsed)) return setError("Enter the new value.");
    setBusy(true);
    setError(null);
    try {
      const res = await changeFact(key, parsed);
      setValue("");
      if (res === "no_impact") toast("Saved. No posts use this fact.");
    } catch (err) {
      noteError(err);
      setError(`The new value is saved, but we could not check which posts it affects. ${errorMessage(err)}`);
    } finally {
      setBusy(false);
    }
  }

  if (editable.length === 0) return <p className="muted">Confirm facts first. Then you can change one here and see what it affects.</p>;

  return (
    <form className="change-form card-flat" onSubmit={submit}>
      <h2 className="h3">Change a fact</h2>
      <div className="change-fields">
        <div>
          <label htmlFor="change-key">Fact</label>
          <select id="change-key" value={key} onChange={(e) => setKey(e.target.value as FactKey)}>
            {editable.map((k) => (
              <option key={k} value={k}>
                {FACT_LABEL[k]}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="change-value">New value</label>
          <input id="change-value" value={value} onChange={(e) => setValue(e.target.value)} aria-describedby="change-current" aria-invalid={!!error} />
          <p id="change-current" className="small muted">
            Now: {current ? show(key, current.value) : "not set"}
          </p>
        </div>
      </div>
      {error && (
        <p role="alert" className="field-error">
          {error}
        </p>
      )}
      <button type="submit" className="btn btn-primary" aria-disabled={busy}>
        {busy ? "Checking..." : "Check what this affects"}
      </button>
    </form>
  );
}

function ProposalCard({ post, title, reason }: { post: Post; title: string; reason: string }) {
  const proposal = useCampaign((s) => s.proposals[post.id]);
  const { acceptProposal, keepCurrent, requestRedraft } = useCampaign.getState();
  const path = useStepPath();
  return (
    <article className="change-card card">
      <header className="change-head">
        <div className="post-name">
          <PlatformDot platform={post.platform} />
          <h3>
            {PLATFORM_NAME[post.platform]} <span className="muted-name">· {title}</span>
          </h3>
        </div>
        <StatusChip status={post.status} />
      </header>
      {proposal?.state === "ready" && proposal.result ? (
        <>
          <Diff oldText={post.text} newText={proposal.result.proposed_text} />
          <footer className="change-foot">
            <span className="muted">Why: {proposal.result.reason || reason}</span>
            <div className="row-actions">
              <button type="button" className="btn btn-primary" onClick={() => acceptProposal(post.id)}>
                Update this post
              </button>
              <button type="button" className="btn btn-secondary" onClick={() => keepCurrent(post.id)}>
                Keep current
              </button>
              <Link to={`${path("posts")}?item=${post.plan_item_id}`}>Edit</Link>
            </div>
          </footer>
        </>
      ) : proposal?.state === "loading" ? (
        <p className="muted" role="status">
          Writing a proposed fix...
        </p>
      ) : proposal?.state === "error" ? (
        <div className="row-actions">
          <p role="alert" className="field-error">
            {errorMessage(proposal.error)}
          </p>
          <button type="button" className="btn btn-secondary" onClick={() => void requestRedraft(post.id)}>
            Try again
          </button>
        </div>
      ) : (
        <div className="change-foot">
          <span className="muted">Why: {reason}</span>
          <div className="row-actions">
            <button type="button" className="btn btn-secondary" onClick={() => void requestRedraft(post.id)}>
              Show the change
            </button>
            <button type="button" className="btn btn-text" onClick={() => keepCurrent(post.id)}>
              Keep current
            </button>
          </div>
        </div>
      )}
    </article>
  );
}

export function Changes() {
  const doc = useCampaign((s) => s.doc)!;
  const lastChange = useCampaign((s) => s.lastChange);
  const navigate = useNavigate();
  const path = useStepPath();
  const tz = safeTimezone(factValue(doc.facts, "timezone") || browserTimezone());
  const titleOf = (id: string) => doc.plan.find((p) => p.id === id)?.title ?? "";

  const reviewing = doc.posts.filter((p) => p.change_reason && p.status !== "published");
  const protectedPosts = lastChange
    ? lastChange.impact.protected.map((x) => ({ ...x, post: doc.posts.find((p) => p.id === x.post_id) })).filter((x) => x.post)
    : [];
  const changed = lastChange?.changed;
  const label = changed ? FACT_LABEL[changed.key] : "";

  return (
    <div className="screen">
      <ScreenHeader
        eyebrow={doc.name}
        title={changed ? `The ${label.toLowerCase()} changed` : "Changes"}
        lead={
          changed
            ? `${reviewing.length} ${reviewing.length === 1 ? "post uses" : "posts use"} it and ${reviewing.length === 1 ? "is" : "are"} back in review.${protectedPosts.length ? ` ${protectedPosts.length} published ${protectedPosts.length === 1 ? "post stays" : "posts stay"} exactly as ${protectedPosts.length === 1 ? "it is" : "they are"}.` : ""}`
            : "Change a confirmed fact to see which posts it affects. Published posts are never rewritten."
        }
        aside={<ModelBadge />}
      />

      {changed && (
        <section aria-label="What changed" className="changed-box">
          <div className="changed-kicker">{label}, edited by you</div>
          <div className="changed-values">
            <span className="changed-old">
              <span className="sr-only">Old value: </span>
              {show(changed.key, changed.old)}
            </span>
            <svg width="32" height="14" viewBox="0 0 32 14" aria-hidden="true">
              <path d="M0 7h29M23 1l7 6-7 6" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
            </svg>
            <span className="changed-new">
              <span className="sr-only">New value: </span>
              {show(changed.key, changed.new)}
            </span>
          </div>
          {lastChange.impact.plan_changes.length > 0 && (
            <p className="small">
              {lastChange.impact.plan_changes.length} plan {lastChange.impact.plan_changes.length === 1 ? "date was" : "dates were"} moved to match.
            </p>
          )}
        </section>
      )}

      <LimitBanner />

      {reviewing.length > 0 && (
        <>
          <h2 className="section-sub">Proposed updates</h2>
          <div className="change-list">
            {reviewing.map((p) => (
              <ProposalCard key={p.id} post={p} title={titleOf(p.plan_item_id)} reason={p.change_reason ?? ""} />
            ))}
          </div>
        </>
      )}

      {protectedPosts.length > 0 && (
        <>
          <h2 className="section-sub">Already public</h2>
          <div className="change-list">
            {protectedPosts.map(({ post, note }) => (
              <article key={post!.id} className="protected-card">
                <div className="change-head">
                  <div className="post-name">
                    <PlatformDot platform={post!.platform} />
                    <h3>
                      {PLATFORM_NAME[post!.platform]} <span className="muted-name">· {titleOf(post!.plan_item_id)}</span>
                    </h3>
                  </div>
                  <StatusChip status="published" label={`Published ${post!.published_at ? formatDateTime(post!.published_at, tz) : ""}. Left as is.`} />
                </div>
                <p>{note || "Published posts are a record, so Campaory will not rewrite it. If the old value is already out there, post a correction yourself."}</p>
              </article>
            ))}
          </div>
        </>
      )}

      {changed && reviewing.length === 0 && <p className="muted">Nothing left to review for this change.</p>}

      <ChangeForm />

      <div className="screen-foot">
        <button type="button" className="back-link link-btn" onClick={() => navigate(path("posts"))}>
          &larr; Back to posts
        </button>
        {reviewing.length > 0 && (
          <span className="muted">
            {reviewing.length} {reviewing.length === 1 ? "post" : "posts"} to review. Their approvals were cleared.
          </span>
        )}
      </div>
    </div>
  );
}
