// Upcoming and status dashboard (T3.8): counts by status, next reminders, what needs review.
import { Link } from "react-router-dom";
import { PlatformDot } from "../components/PlatformDot";
import { statusLabel, StatusChip } from "../components/StatusChip";
import { ScreenHeader } from "../components/Title";
import { browserTimezone, formatDateTime, safeTimezone } from "../lib/dates";
import { factValue } from "../lib/facts";
import { useStepPath } from "../lib/paths";
import { PLATFORM_NAME } from "../lib/share";
import type { Post, PostStatus } from "../lib/types";
import { orderedPlan, postCounts, upcomingReminders, useCampaign } from "../store/campaign";

const ORDER: PostStatus[] = ["needs_review", "draft", "approved", "scheduled", "published"];

export function Upcoming() {
  const doc = useCampaign((s) => s.doc)!;
  const path = useStepPath();
  const tz = safeTimezone(factValue(doc.facts, "timezone") || browserTimezone());
  const counts = postCounts(doc);
  const reminders = upcomingReminders(doc);
  const review = doc.posts.filter((p) => p.status === "needs_review");
  const titleOf = (id: string) => doc.plan.find((p) => p.id === id)?.title ?? "";
  const now = Date.now();
  const nextItems = orderedPlan(doc)
    .filter((p) => p.scheduled_for && new Date(p.scheduled_for).getTime() >= now)
    .sort((a, b) => (a.scheduled_for! < b.scheduled_for! ? -1 : 1))
    .slice(0, 6);

  const row = (p: Post, when: string | null) => (
    <li key={p.id} className="up-row">
      <PlatformDot platform={p.platform} />
      <div className="up-main">
        <Link to={`${path("posts")}?item=${p.plan_item_id}`} className="up-title">
          {titleOf(p.plan_item_id)} · {PLATFORM_NAME[p.platform]}
        </Link>
        {when && <span className="small muted">{when}</span>}
        {p.change_reason && <span className="small muted">Changed fact: {p.change_reason}</span>}
      </div>
      <StatusChip status={p.status} />
    </li>
  );

  return (
    <div className="screen">
      <ScreenHeader eyebrow={doc.name} title="What is next" lead="Reminders you set, posts waiting for you, and what is coming up in the plan." />

      <dl className="tiles">
        {ORDER.map((s) => (
          <div key={s} className={`tile tile-${s}`}>
            <dt>{statusLabel(s)}</dt>
            <dd>{counts[s]}</dd>
          </div>
        ))}
      </dl>

      <div className="up-grid">
        <section className="card-flat" aria-labelledby="up-rem">
          <h2 id="up-rem" className="h3">
            Next reminders
          </h2>
          {reminders.length ? (
            <ol className="up-list">{reminders.map((p) => row(p, `Remind at ${formatDateTime(p.reminder_at, tz)}`))}</ol>
          ) : (
            <p className="muted">No reminders yet. Approve a post, then set a reminder on it.</p>
          )}
        </section>

        <section className="card-flat" aria-labelledby="up-rev">
          <h2 id="up-rev" className="h3">
            Needs review
          </h2>
          {review.length ? <ol className="up-list">{review.map((p) => row(p, null))}</ol> : <p className="muted">Nothing waiting for review.</p>}
        </section>

        <section className="card-flat" aria-labelledby="up-plan">
          <h2 id="up-plan" className="h3">
            Coming up in the plan
          </h2>
          {nextItems.length ? (
            <ol className="up-list">
              {nextItems.map((item) => {
                const posts = doc.posts.filter((p) => p.plan_item_id === item.id);
                const ready = posts.filter((p) => p.status === "approved" || p.status === "scheduled" || p.status === "published").length;
                return (
                  <li key={item.id} className="up-row">
                    <div className="up-main">
                      <Link to={`${path("posts")}?item=${item.id}`} className="up-title">
                        {item.title}
                      </Link>
                      <span className="small muted">{formatDateTime(item.scheduled_for, tz)}</span>
                    </div>
                    <span className="pill pill-white">
                      {ready} of {posts.length} approved
                    </span>
                  </li>
                );
              })}
            </ol>
          ) : (
            <p className="muted">Nothing left in the plan.</p>
          )}
        </section>
      </div>
    </div>
  );
}
