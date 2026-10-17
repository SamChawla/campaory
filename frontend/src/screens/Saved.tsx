// Saved campaigns (UI_SPEC 7.4). Signed-in only; every row belongs to the current user.
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Dialog } from "../components/Dialog";
import { ScreenHeader } from "../components/Title";
import { api, errorMessage } from "../lib/api";
import type { CampaignSummary } from "../lib/types";
import { lastStep } from "../store/importer";
import { useCampaign } from "../store/campaign";
import { hasGoogle, useSession } from "../store/session";
import { useUi } from "../store/ui";

function edited(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "" : new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).format(d);
}

export function Saved() {
  const user = useSession((s) => s.user);
  const loaded = useSession((s) => s.loaded);
  const config = useSession((s) => s.config);
  const toast = useUi((s) => s.toast);
  const navigate = useNavigate();
  const [items, setItems] = useState<CampaignSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirm, setConfirm] = useState<CampaignSummary | null>(null);

  useEffect(() => {
    if (!user) return;
    api
      .listCampaigns()
      .then(setItems)
      .catch((err) => setError(errorMessage(err)));
  }, [user]);

  async function remove(c: CampaignSummary) {
    try {
      await api.deleteCampaign(c.id);
    } catch (err) {
      toast(errorMessage(err));
      return;
    }
    setItems((xs) => (xs ?? []).filter((x) => x.id !== c.id));
    const store = useCampaign.getState();
    if (store.mode === "saved" && store.doc?.id === c.id) store.reset();
    setConfirm(null);
    toast(`Deleted ${c.name}.`);
  }

  if (!loaded) return <p className="muted">Loading...</p>;
  if (!user) {
    return (
      <section className="empty">
        <h1>Saved campaigns</h1>
        <p>Sign in to see the campaigns saved in your account.</p>
        {hasGoogle(config) && (
          <a className="btn btn-primary" href="/api/auth/login/google">
            Continue with Google
          </a>
        )}
      </section>
    );
  }

  return (
    <div className="screen">
      <ScreenHeader eyebrow={user.email} title="Saved campaigns" />
      {error && (
        <p role="alert" className="field-error">
          {error}
        </p>
      )}
      {items === null && !error && <p className="muted">Loading...</p>}
      {items && items.length === 0 && (
        <section className="empty">
          <h2>Nothing saved yet</h2>
          <Link to="/" className="btn btn-primary">
            Start a campaign
          </Link>
        </section>
      )}
      {items && items.length > 0 && (
        <ul className="saved-grid">
          {items.map((c) => {
            const counts = c.post_counts ?? {};
            return (
              <li key={c.id} className="saved-card card">
                <h2 className="h3">{c.name}</h2>
                <p className="muted">
                  Last edited {edited(c.updated_at)}
                </p>
                <p className="saved-counts">
                  <span>{(counts.approved ?? 0) + (counts.scheduled ?? 0)} approved</span>
                  <span>{counts.needs_review ?? 0} need review</span>
                  <span>{counts.published ?? 0} published</span>
                </p>
                <div className="row-actions">
                  <button type="button" className="btn btn-primary" onClick={() => navigate(`/c/${c.id}/${lastStep()}`)}>
                    Open
                  </button>
                  <button type="button" className="btn btn-secondary" onClick={() => setConfirm(c)}>
                    Delete
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      )}
      {confirm && (
        <Dialog title={`Delete ${confirm.name}?`} onClose={() => setConfirm(null)}>
          <p>Deleting cannot be undone. The campaign, its plan and its posts are removed from your account.</p>
          <div className="dialog-actions">
            <button type="button" className="btn btn-danger" onClick={() => remove(confirm)}>
              Delete campaign
            </button>
            <button type="button" className="btn btn-secondary" onClick={() => setConfirm(null)} data-autofocus>
              Cancel
            </button>
          </div>
        </Dialog>
      )}
    </div>
  );
}
