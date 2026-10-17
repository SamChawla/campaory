import { useEffect, useRef, useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { hasPendingSave, setPendingSave } from "../lib/storage";
import { useCampaign } from "../store/campaign";
import { importGuest } from "../store/importer";
import { useSession } from "../store/session";
import { useUi } from "../store/ui";
import { Nav } from "./Nav";
import { ConfirmDialog } from "./ConfirmDialog";
import { SignInSheet } from "./SignInSheet";
import { Toasts } from "./Toast";

/** Handles `/?auth=ok` and `/?auth=failed` after the OAuth redirect (LLD 8.4). */
function useAuthReturn(onFailed: () => void) {
  const location = useLocation();
  const navigate = useNavigate();
  const handled = useRef(false);

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const auth = params.get("auth");
    if (!auth || handled.current) return;
    handled.current = true;
    navigate(location.pathname, { replace: true });
    if (auth === "failed") {
      setPendingSave(false);
      onFailed();
      return;
    }
    if (auth !== "ok") return;
    void (async () => {
      const user = await useSession.getState().refreshMe();
      if (!user) return;
      const { doc, mode } = useCampaign.getState();
      if (hasPendingSave() && doc && mode === "guest") {
        const path = await importGuest();
        if (path) navigate(path, { replace: true });
      } else {
        setPendingSave(false);
        if (!doc || mode !== "guest") navigate("/saved", { replace: true });
      }
    })();
  }, [location.search, location.pathname, navigate, onFailed]);
}

export function Layout() {
  const [authFailed, setAuthFailed] = useState(false);
  const toast = useUi((s) => s.toast);
  const [booted, setBooted] = useState(false);

  useEffect(() => {
    useCampaign.getState().init();
    void useSession.getState().load();
    setBooted(true);
    const offline = () => toast("You are offline. Changes are kept on this device.");
    window.addEventListener("offline", offline);
    return () => window.removeEventListener("offline", offline);
  }, [toast]);

  useAuthReturn(useRef(() => setAuthFailed(true)).current);

  return (
    <>
      <a href="#main" className="skip-link">
        Skip to content
      </a>
      <Nav />
      <main id="main" className="page" tabIndex={-1}>
        {authFailed && (
          <div className="banner banner-warn" role="alert">
            <p>Sign-in did not finish. Your work is still here.</p>
            <button type="button" className="btn btn-text" onClick={() => setAuthFailed(false)}>
              Dismiss
            </button>
          </div>
        )}
        {booted && <Outlet />}
      </main>
      <SignInSheet />
      <ConfirmDialog />
      <Toasts />
    </>
  );
}
