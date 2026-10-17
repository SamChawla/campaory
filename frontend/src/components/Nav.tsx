import { useEffect, useRef, useState } from "react";
import { Link, NavLink, useLocation, useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { clockTime } from "../lib/dates";
import { STEP_LABEL, STEP_ORDER, useStepPath } from "../lib/paths";
import { useCampaign } from "../store/campaign";
import { useSession } from "../store/session";
import { useStart } from "../store/startSample";
import { useUi } from "../store/ui";
import { Dialog } from "./Dialog";
import { useSaveAction } from "./SaveBanner";

export function SampleButton({ className = "", children = "Try a sample event" }: { className?: string; children?: string }) {
  const start = useStart((s) => s.start);
  const busy = useStart((s) => s.busy);
  const navigate = useNavigate();
  return (
    <button
      type="button"
      className={className}
      aria-disabled={busy !== null}
      onClick={async () => {
        if (busy) return;
        if (await start({ kind: "sample" })) navigate("/facts");
        else if (useStart.getState().error) navigate("/#start");
      }}
    >
      {busy === "sample" ? "Reading the sample..." : children}
    </button>
  );
}

function SaveStatus() {
  const mode = useCampaign((s) => s.mode);
  const saving = useCampaign((s) => s.saving);
  const saveError = useCampaign((s) => s.saveError);
  const lastSavedAt = useCampaign((s) => s.lastSavedAt);
  const saveNow = useCampaign((s) => s.saveNow);
  const importState = useUi((s) => s.importState);
  const save = useSaveAction();

  if (mode === "guest") {
    return (
      <button type="button" className="btn btn-highlight nav-save" onClick={save} aria-disabled={importState.state === "saving"}>
        {importState.state === "saving" ? "Saving..." : "Save"}
      </button>
    );
  }
  if (saving) return <span className="nav-status" role="status">Saving...</span>;
  if (saveError) {
    return (
      <button type="button" className="nav-status nav-status-error" onClick={() => void saveNow()}>
        Could not save. Retry
      </button>
    );
  }
  return (
    <span className="nav-status" role="status">
      <span className="chip chip-approved">Saved</span>
      {lastSavedAt ? ` ${clockTime(lastSavedAt)}` : ""}
    </span>
  );
}

function AccountMenu() {
  const user = useSession((s) => s.user)!;
  const signOut = useSession((s) => s.signOut);
  const reset = useCampaign((s) => s.reset);
  const mode = useCampaign((s) => s.mode);
  const toast = useUi((s) => s.toast);
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [typed, setTyped] = useState("");
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  async function doSignOut() {
    setOpen(false);
    try {
      await signOut();
    } catch {
      toast("Could not sign out. Try again.");
      return;
    }
    if (mode === "saved") reset();
    useCampaign.getState().init();
    navigate("/");
  }

  async function doDelete() {
    try {
      await api.deleteAccount();
    } catch {
      toast("Could not delete the account. Try again.");
      return;
    }
    setDeleting(false);
    useSession.setState({ user: null });
    if (mode === "saved") reset();
    navigate("/");
    toast("Your account and saved campaigns are deleted.");
  }

  const initial = (user.name || user.email || "?").trim().charAt(0).toUpperCase();
  return (
    <div className="account" ref={ref}>
      <button type="button" className="avatar" aria-haspopup="true" aria-expanded={open} onClick={() => setOpen(!open)} aria-label={`Account: ${user.email}`}>
        {user.avatar_url ? <img src={user.avatar_url} alt="" /> : <span aria-hidden="true">{initial}</span>}
      </button>
      {open && (
        <div className="account-menu">
          <p className="small muted account-email">{user.email}</p>
          <Link to="/saved" onClick={() => setOpen(false)}>
            Saved campaigns
          </Link>
          <button type="button" className="link-btn" onClick={doSignOut}>
            Sign out
          </button>
          <button
            type="button"
            className="link-btn danger"
            onClick={() => {
              setOpen(false);
              setTyped("");
              setDeleting(true);
            }}
          >
            Delete account
          </button>
        </div>
      )}
      {deleting && (
        <Dialog title="Delete your account?" onClose={() => setDeleting(false)}>
          <p>This deletes your account and every saved campaign. It cannot be undone. Work on this device stays.</p>
          <label htmlFor="confirm-delete">Type DELETE to confirm</label>
          <input id="confirm-delete" value={typed} onChange={(e) => setTyped(e.target.value)} autoComplete="off" />
          <div className="dialog-actions">
            <button type="button" className="btn btn-danger" disabled={typed !== "DELETE"} onClick={doDelete}>
              Delete account
            </button>
            <button type="button" className="btn btn-secondary" onClick={() => setDeleting(false)}>
              Cancel
            </button>
          </div>
        </Dialog>
      )}
    </div>
  );
}

export function Nav() {
  const doc = useCampaign((s) => s.doc);
  const user = useSession((s) => s.user);
  const path = useStepPath();
  const location = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);
  const onStart = location.pathname === "/";

  useEffect(() => setMenuOpen(false), [location.pathname]);

  return (
    <header className="nav-wrap">
      <nav className="nav" aria-label="Main">
        <Link to="/" className="nav-logo" aria-label="Campaory home">
          <span className="nav-mark" aria-hidden="true" />
          Campaory
        </Link>
        {doc && (
          <>
            <button type="button" className="nav-menu-btn" aria-expanded={menuOpen} aria-controls="nav-steps" onClick={() => setMenuOpen(!menuOpen)}>
              {menuOpen ? "Close" : "Menu"}
            </button>
            <ol id="nav-steps" className={`nav-steps${menuOpen ? " is-open" : ""}`} aria-label="Campaign steps">
              {STEP_ORDER.map((step) => (
                <li key={step}>
                  <NavLink to={path(step)} className="nav-step">
                    {STEP_LABEL[step]}
                  </NavLink>
                </li>
              ))}
            </ol>
          </>
        )}
        <div className="nav-right">
          {onStart || !doc ? <SampleButton className="btn btn-highlight nav-cta" /> : <SaveStatus />}
          {!onStart && doc && (
            <Link to="/" className="btn btn-on-ink nav-new">
              New campaign
            </Link>
          )}
          {user && <AccountMenu />}
        </div>
      </nav>
    </header>
  );
}
