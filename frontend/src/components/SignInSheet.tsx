// Sign-in sheet (UI_SPEC 7.2). Opened only by the explicit Save action.
import { useState } from "react";
import { Link } from "react-router-dom";
import { saveGuest, setPendingSave } from "../lib/storage";
import { useCampaign } from "../store/campaign";
import { hasGithub, hasGoogle, useSession } from "../store/session";
import { useUi } from "../store/ui";
import { Dialog } from "./Dialog";

function GoogleMark() {
  return (
    <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden="true" focusable="false">
      <path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.9 1.2 8 3.1l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z" />
      <path fill="#FF3D00" d="m6.3 14.7 6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.9 1.2 8 3.1l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z" />
      <path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-8l-6.5 5C9.5 39.6 16.2 44 24 44z" />
      <path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.4-.4-3.5z" />
    </svg>
  );
}

export function SignInSheet() {
  const open = useUi((s) => s.signInOpen);
  const close = useUi((s) => s.closeSignIn);
  const config = useSession((s) => s.config);
  const [redirecting, setRedirecting] = useState<null | "google" | "github">(null);

  if (!open) return null;

  function go(provider: "google" | "github") {
    const doc = useCampaign.getState().doc;
    if (doc && useCampaign.getState().mode === "guest") saveGuest(doc);
    setPendingSave(true);
    setRedirecting(provider);
    window.location.assign(`/api/auth/login/${provider}`);
  }

  const google = hasGoogle(config);
  const github = hasGithub(config);

  return (
    <Dialog title="Save your campaign" onClose={close} className="sheet">
      <p>Sign in to keep this campaign and come back to it. Your current work comes with you.</p>
      <div className="sheet-actions">
        {google && (
          <button type="button" className="btn btn-primary btn-block" disabled={redirecting !== null} onClick={() => go("google")} data-autofocus>
            <span className="google-mark">
              <GoogleMark />
            </span>
            {redirecting === "google" ? "Opening Google..." : "Continue with Google"}
          </button>
        )}
        {github && (
          <button type="button" className="btn btn-primary btn-block" disabled={redirecting !== null} onClick={() => go("github")}>
            {redirecting === "github" ? "Opening GitHub..." : "Continue with GitHub"}
          </button>
        )}
        {!google && !github && <p role="alert">Sign-in is not set up on this server, so saving to an account is not available. Your work stays on this device.</p>}
        <button type="button" className="btn btn-text" onClick={close}>
          Not now
        </button>
      </div>
      <p className="small muted">
        We store your name, email and your campaigns. No passwords.{" "}
        <Link to="/privacy" onClick={close}>
          Privacy note
        </Link>
      </p>
    </Dialog>
  );
}
