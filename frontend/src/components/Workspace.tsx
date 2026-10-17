// Route wrappers: the same screens serve the guest doc (`/facts`) and a saved campaign
// (`/c/:id/facts`). The store knows which one is loaded.
import { useEffect, useState, type ReactNode } from "react";
import { Link, Navigate, useParams } from "react-router-dom";
import { ApiError, errorMessage } from "../lib/api";
import { useCampaign } from "../store/campaign";
import { rememberStep, type Step } from "../store/importer";
import { hasGoogle, useSession } from "../store/session";
import { SaveBanner } from "./SaveBanner";

function Remember({ step }: { step: Step }) {
  useEffect(() => rememberStep(step), [step]);
  return null;
}

export function GuestWorkspace({ step, children }: { step: Step; children: ReactNode }) {
  const doc = useCampaign((s) => s.doc);
  const mode = useCampaign((s) => s.mode);
  if (!doc) return <Navigate to="/" replace />;
  if (mode === "saved") return <Navigate to={`/c/${doc.id}/${step}`} replace />;
  return (
    <>
      <Remember step={step} />
      <SaveBanner />
      {children}
    </>
  );
}

export function SavedWorkspace({ step, children }: { step: Step; children: ReactNode }) {
  const { id = "" } = useParams();
  const user = useSession((s) => s.user);
  const loaded = useSession((s) => s.loaded);
  const config = useSession((s) => s.config);
  const doc = useCampaign((s) => s.doc);
  const mode = useCampaign((s) => s.mode);
  const openSaved = useCampaign((s) => s.openSaved);
  const [error, setError] = useState<unknown>(null);
  const ready = doc?.id === id && mode === "saved";

  useEffect(() => {
    if (!user || ready) return;
    let live = true;
    setError(null);
    openSaved(id).catch((err) => live && setError(err));
    return () => {
      live = false;
    };
  }, [user, id, ready, openSaved]);

  if (!loaded) return <p className="muted">Loading...</p>;
  if (!user) {
    return (
      <section className="empty">
        <h1>Sign in to open this campaign</h1>
        <p>Saved campaigns live in your account.</p>
        {hasGoogle(config) && (
          <a className="btn btn-primary" href="/api/auth/login/google">
            Continue with Google
          </a>
        )}
      </section>
    );
  }
  if (error) {
    const notFound = error instanceof ApiError && error.status === 404;
    return (
      <section className="empty">
        <h1>{notFound ? "Campaign not found" : "Could not open the campaign"}</h1>
        <p>{notFound ? "We could not find that campaign in your account." : errorMessage(error)}</p>
        <Link className="btn btn-primary" to="/saved">
          Saved campaigns
        </Link>
      </section>
    );
  }
  if (!ready) return <p className="muted">Opening the campaign...</p>;
  return (
    <>
      <Remember step={step} />
      <SaveBanner />
      {children}
    </>
  );
}
