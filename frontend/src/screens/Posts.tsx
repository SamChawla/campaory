// Review the posts (Posts.dc.html, Mobile.dc.html): items on the left, four platform cards
// per item. On phones one card at a time with platform tabs.
import { useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { LimitBanner } from "../components/LimitBanner";
import { ModelBadge } from "../components/ModelBadge";
import { PostCard } from "../components/PostCard";
import { statusLabel } from "../components/StatusChip";
import { ScreenHeader } from "../components/Title";
import { api, errorMessage } from "../lib/api";
import { browserTimezone, formatDateTime, formatDay, safeTimezone } from "../lib/dates";
import { confirmedFacts, factValue } from "../lib/facts";
import { PLATFORM_NAME } from "../lib/share";
import type { Platform } from "../lib/types";
import { orderedPlan, useCampaign } from "../store/campaign";
import { useGeneration } from "../store/generation";
import { useUi } from "../store/ui";

const APPROVED = new Set(["approved", "scheduled", "published"]);

export function Posts() {
  const doc = useCampaign((s) => s.doc)!;
  const applyRevision = useCampaign((s) => s.applyRevision);
  const generation = useGeneration();
  const noteError = useUi((s) => s.noteError);
  const [params, setParams] = useSearchParams();
  const [tab, setTab] = useState<Platform>(doc.platforms[0]);
  const [instruction, setInstruction] = useState("");
  const [rewriting, setRewriting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const tz = safeTimezone(factValue(doc.facts, "timezone") || browserTimezone());
  const plan = orderedPlan(doc);
  const selectedId = plan.some((p) => p.id === params.get("item")) ? params.get("item")! : plan[0]?.id;
  const item = plan.find((p) => p.id === selectedId);
  const approved = doc.posts.filter((p) => APPROVED.has(p.status)).length;
  const itemPosts = doc.platforms.map((pl) => ({ platform: pl, post: doc.posts.find((p) => p.plan_item_id === selectedId && p.platform === pl) }));
  const failedTitles = generation.failed.map((f) => plan.find((p) => p.id === f.plan_item_id)?.title).filter(Boolean);
  const activeTab = doc.platforms.includes(tab) ? tab : doc.platforms[0];

  function select(id: string) {
    setParams({ item: id }, { replace: true });
  }

  async function rewriteAll(e: FormEvent) {
    e.preventDefault();
    const text = instruction.trim().slice(0, 200);
    if (!text || !item || rewriting) return;
    setRewriting(true);
    setError(null);
    const targets = itemPosts.map((x) => x.post).filter((p) => p && p.status !== "published");
    try {
      for (const p of targets) {
        const res = await api.revise({ facts: confirmedFacts(doc.facts), post: { platform: p!.platform, text: p!.text, facts_used: p!.facts_used }, instruction: "custom", custom_instruction: text });
        applyRevision(p!.id, res, "custom");
      }
      setInstruction("");
    } catch (err) {
      noteError(err);
      setError(errorMessage(err));
    } finally {
      setRewriting(false);
    }
  }

  async function regenerate() {
    if (!item) return;
    const hasApproved = itemPosts.some((x) => x.post && (x.post.status === "approved" || x.post.status === "scheduled"));
    if (
      hasApproved &&
      !(await useUi.getState().askConfirm({
        title: "Write this item again?",
        message: "Approved drafts go back to draft. Published posts stay as they are.",
        confirmLabel: "Write again",
        cancelLabel: "Keep drafts",
      }))
    )
      return;
    void generation.run([item.id]);
  }

  const retryFailed = () => void generation.run(generation.failed.map((f) => f.plan_item_id));

  return (
    <div className="screen">
      <ScreenHeader
        eyebrow={doc.name}
        title="Review the posts"
        aside={
          <div className="head-pills">
            <span className="pill pill-white">
              <strong>
                {approved} of {doc.posts.length}
              </strong>
              &nbsp;approved
            </span>
            <ModelBadge />
          </div>
        }
      />

      {generation.running && (
        <div className="progress" role="status">
          <p>
            Writing posts: {generation.done} of {generation.total} items
          </p>
          <div className="progress-bar" role="progressbar" aria-label="Writing posts" aria-valuemin={0} aria-valuemax={generation.total} aria-valuenow={generation.done}>
            <span style={{ width: `${generation.total ? (generation.done / generation.total) * 100 : 0}%` }} />
          </div>
        </div>
      )}
      {!generation.running && failedTitles.length > 0 && (
        <div className="banner banner-warn" role="alert">
          <p>These items could not be written: {failedTitles.join(", ")}.</p>
          <button type="button" className="btn btn-primary" onClick={retryFailed}>
            Retry these
          </button>
        </div>
      )}
      <LimitBanner onRetry={generation.failed.length ? retryFailed : undefined} />

      {plan.length === 0 ? (
        <section className="empty">
          <h2>No plan yet</h2>
          <p>Make the plan first, then write the posts.</p>
        </section>
      ) : doc.posts.length === 0 && !generation.running ? (
        <section className="empty">
          <h2>No posts yet</h2>
          <p>
            Write {plan.length * doc.platforms.length} posts from your {plan.length} plan items.
          </p>
          <button type="button" className="btn btn-primary btn-lg" onClick={() => void generation.run()}>
            Write the posts
          </button>
        </section>
      ) : (
        <div className="posts-layout">
          <nav aria-label="Campaign items" className="items-nav">
            <ol>
              {plan.map((p) => {
                const posts = doc.posts.filter((x) => x.plan_item_id === p.id);
                const ok = posts.filter((x) => APPROVED.has(x.status)).length;
                return (
                  <li key={p.id}>
                    <button type="button" className="item-link" aria-current={p.id === selectedId ? "true" : undefined} onClick={() => select(p.id)}>
                      <span className="item-title">{p.title}</span>
                      <span className="item-meta">
                        {formatDay(p.scheduled_for, tz)} · {ok} of {posts.length}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ol>
          </nav>

          {item && (
            <section className="item-section" aria-labelledby="item-h">
              <div className="item-head">
                <h2 id="item-h">{item.title}</h2>
                <span className="item-when">{formatDateTime(item.scheduled_for, tz)} {tz}</span>
              </div>
              {item.purpose && <p className="item-purpose">{item.purpose}</p>}

              <form className="rewrite" onSubmit={rewriteAll}>
                <label htmlFor="rewrite-all" className="sr-only">
                  Change all drafts for this item at once
                </label>
                <input
                  id="rewrite-all"
                  value={instruction}
                  maxLength={200}
                  onChange={(e) => setInstruction(e.target.value)}
                  placeholder="Change all drafts at once, e.g. sound less formal"
                />
                <button type="submit" className="btn btn-highlight" aria-disabled={rewriting || !instruction.trim()}>
                  {rewriting ? "Rewriting..." : "Rewrite drafts"}
                </button>
              </form>
              <div className="item-tools">
                <button type="button" className="link-btn" onClick={() => void regenerate()} disabled={generation.running}>
                  Write this item again
                </button>
              </div>
              {error && (
                <p role="alert" className="field-error">
                  {error}
                </p>
              )}

              <div role="tablist" aria-label="Platform" className="platform-tabs">
                {itemPosts.map(({ platform, post }) => (
                  <button
                    key={platform}
                    type="button"
                    role="tab"
                    id={`tab-${platform}`}
                    aria-selected={activeTab === platform}
                    aria-controls={`panel-${platform}`}
                    className="platform-tab"
                    onClick={() => setTab(platform)}
                  >
                    {PLATFORM_NAME[platform]}
                    <span className="tab-state">{post ? statusLabel(post.status) : "None"}</span>
                  </button>
                ))}
              </div>

              <div className="post-grid">
                {itemPosts.map(({ platform, post }) => (
                  <div key={platform} id={`panel-${platform}`} role="tabpanel" aria-labelledby={`tab-${platform}`} className={`post-slot${activeTab === platform ? " is-active" : ""}`}>
                    {post ? (
                      <PostCard post={post} tz={tz} active={activeTab === platform} />
                    ) : (
                      <article className="post-card post-empty">
                        <h3>{PLATFORM_NAME[platform]}</h3>
                        <p className="muted">{generation.running ? "Writing..." : "No draft yet."}</p>
                        {!generation.running && (
                          <button type="button" className="btn btn-secondary" onClick={() => void generation.run([item.id])}>
                            Write this item
                          </button>
                        )}
                      </article>
                    )}
                  </div>
                ))}
              </div>
              <p className="small muted posts-foot">After you approve, you can copy the text and open the platform. You press post yourself.</p>
            </section>
          )}
        </div>
      )}
    </div>
  );
}
