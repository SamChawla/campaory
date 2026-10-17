// Guest notice, import failures, saved-mode save errors and storage problems
// (UI_SPEC 7.1, 7.3, 7.7). Lives below the nav inside the workspace.
import { useNavigate } from "react-router-dom";
import { saveGuest } from "../lib/storage";
import { useCampaign } from "../store/campaign";
import { importGuest } from "../store/importer";
import { canSignIn, useSession } from "../store/session";
import { useUi } from "../store/ui";
import { Dialog } from "./Dialog";

const BROWSER_SAVE_FAILED = {
  quota: "Could not save on this device. The browser storage is full.",
  unavailable: "This browser blocks storage. Your work will be lost if you close the page.",
};

export function useSaveAction() {
  const navigate = useNavigate();
  const user = useSession((s) => s.user);
  const signInAvailable = useSession((s) => canSignIn(s.config));
  const openSignIn = useUi((s) => s.openSignIn);
  const toast = useUi((s) => s.toast);
  return async () => {
    if (!user && !signInAvailable) {
      const doc = useCampaign.getState().doc;
      if (!doc) return;
      const result = saveGuest(doc);
      toast(result === "ok" ? "Saved in this browser" : BROWSER_SAVE_FAILED[result]);
      return;
    }
    if (!user) {
      openSignIn();
      return;
    }
    const path = await importGuest();
    if (path) navigate(path, { replace: true });
  };
}

export function SaveBanner() {
  const mode = useCampaign((s) => s.mode);
  const doc = useCampaign((s) => s.doc);
  const saveError = useCampaign((s) => s.saveError);
  const storageError = useCampaign((s) => s.storageError);
  const storageNotice = useCampaign((s) => s.storageNotice);
  const dismissNotice = useCampaign((s) => s.dismissStorageNotice);
  const saveNow = useCampaign((s) => s.saveNow);
  const importState = useUi((s) => s.importState);
  const setImport = useUi((s) => s.setImport);
  const hidden = useUi((s) => s.guestBannerHidden);
  const hide = useUi((s) => s.hideGuestBanner);
  const save = useSaveAction();
  const signInAvailable = useSession((s) => canSignIn(s.config));
  const navigate = useNavigate();

  return (
    <div className="banners">
      {storageNotice === "reset" && (
        <div className="banner" role="status">
          <p>We could not read the campaign saved on this device, so we kept a copy and started fresh.</p>
          <button type="button" className="btn btn-text" onClick={dismissNotice}>
            Dismiss
          </button>
        </div>
      )}
      {storageError === "unavailable" && mode === "guest" && (
        <div className="banner banner-warn" role="alert">
          <p>This browser blocks storage. Your work will be lost if you close the page.</p>
        </div>
      )}
      {storageError === "quota" && mode === "guest" && (
        <div className="banner banner-warn" role="alert">
          <p>Could not save on this device. The browser storage is full.</p>
        </div>
      )}
      {importState.state === "failed" && (
        <div className="banner banner-warn" role="alert">
          <p>{importState.message}</p>
          <button type="button" className="btn btn-primary" onClick={save}>
            Retry
          </button>
        </div>
      )}
      {importState.state === "limit" && (
        <div className="banner banner-warn" role="alert">
          <p>{importState.message}</p>
          <div className="banner-actions">
            <button type="button" className="btn btn-primary" onClick={() => navigate("/saved")}>
              Open saved campaigns
            </button>
            <button type="button" className="btn btn-secondary" onClick={() => setImport({ state: "idle" })}>
              Keep working on this device
            </button>
          </div>
        </div>
      )}
      {mode === "saved" && saveError === "failed" && (
        <div className="banner banner-warn" role="alert">
          <p>Could not save. Your changes are still here.</p>
          <button type="button" className="btn btn-primary" onClick={() => void saveNow()}>
            Retry
          </button>
        </div>
      )}
      {mode === "guest" && doc && !hidden && importState.state === "idle" && (
        <div className="banner" role="region" aria-label="Guest notice">
          <p>
            {signInAvailable
              ? "Your work is saved on this device only. Sign in to keep it."
              : "Your work is saved in this browser. Clearing browser data removes it."}
          </p>
          <div className="banner-actions">
            <button type="button" className="btn btn-primary" onClick={save}>
              {signInAvailable ? "Save my campaign" : "Save now"}
            </button>
            <button type="button" className="btn btn-text" onClick={hide}>
              Hide
            </button>
          </div>
        </div>
      )}
      <ConflictDialog />
    </div>
  );
}

function ConflictDialog() {
  const saveError = useCampaign((s) => s.saveError);
  const conflictVersion = useCampaign((s) => s.conflictVersion);
  const saveNow = useCampaign((s) => s.saveNow);
  const loadLatest = useCampaign((s) => s.loadLatest);
  const toast = useUi((s) => s.toast);
  if (saveError !== "conflict") return null;
  const dismiss = () => useCampaign.setState({ saveError: "failed" });
  return (
    <Dialog title="This campaign changed in another tab." onClose={dismiss}>
      <p>Load the latest version, or keep what is on this screen and overwrite it.</p>
      <div className="dialog-actions">
        <button
          type="button"
          className="btn btn-primary"
          data-autofocus
          onClick={() => loadLatest().catch(() => toast("Could not load the latest version. Try again."))}
        >
          Load latest
        </button>
        <button type="button" className="btn btn-secondary" disabled={conflictVersion === null} onClick={() => void saveNow(conflictVersion ?? undefined)}>
          Keep mine and overwrite
        </button>
      </div>
    </Dialog>
  );
}
