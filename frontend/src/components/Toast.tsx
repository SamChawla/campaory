// Bottom-centre toasts, aria-live polite (UI_SPEC 3).
import { useUi } from "../store/ui";

export function Toasts() {
  const toasts = useUi((s) => s.toasts);
  const dismiss = useUi((s) => s.dismissToast);
  return (
    <div className="toasts" aria-live="polite" role="status">
      {toasts.map((t) => (
        <div key={t.id} className="toast">
          <span>{t.message}</span>
          {t.link && (
            <a href={t.link.href} target="_blank" rel="noopener noreferrer" className="toast-link">
              {t.link.label}
            </a>
          )}
          <button type="button" className="toast-close" onClick={() => dismiss(t.id)} aria-label="Dismiss">
            ×
          </button>
        </div>
      ))}
    </div>
  );
}
