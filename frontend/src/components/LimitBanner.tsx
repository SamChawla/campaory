// Limit reached (UI_SPEC 7.5): inline, never a full-page error. Retry is disabled with a
// countdown; the campaign on screen stays editable.
import { useEffect, useState } from "react";
import { minutesText } from "../lib/api";
import { useUi } from "../store/ui";

function clock(ms: number): string {
  const total = Math.max(0, Math.ceil(ms / 1000));
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

export function LimitBanner({ onRetry }: { onRetry?: () => void }) {
  const until = useUi((s) => s.limitUntil);
  const clear = useUi((s) => s.clearLimit);
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (!until) return;
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, [until]);

  if (!until) return null;
  const left = until - now;
  const ready = left <= 0;
  return (
    <div className="banner banner-limit" role="alert">
      <p>
        {ready
          ? "You can try again now."
          : `You have used your free AI requests for now. Try again in ${minutesText(left / 1000)}, or sign in for a higher limit.`}
      </p>
      {onRetry && (
        <button
          type="button"
          className="btn btn-secondary"
          aria-disabled={!ready}
          onClick={() => {
            if (!ready) return;
            clear();
            onRetry();
          }}
        >
          {ready ? "Retry" : `Retry in ${clock(left)}`}
        </button>
      )}
    </div>
  );
}
