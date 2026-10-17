// In-page replacement for window.confirm, opened through useUi().askConfirm (UI_SPEC 6).
import { useUi } from "../store/ui";
import { Dialog } from "./Dialog";

export function ConfirmDialog() {
  const request = useUi((s) => s.confirmRequest);
  const answer = useUi((s) => s.answerConfirm);
  if (!request) return null;
  return (
    <Dialog title={request.title} onClose={() => answer(false)}>
      <p>{request.message}</p>
      <div className="dialog-actions">
        <button type="button" className="btn btn-primary" data-autofocus onClick={() => answer(true)}>
          {request.confirmLabel}
        </button>
        <button type="button" className="btn btn-secondary" onClick={() => answer(false)}>
          {request.cancelLabel}
        </button>
      </div>
    </Dialog>
  );
}
