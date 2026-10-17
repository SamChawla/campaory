// Status as text plus icon; colour is secondary (UI_SPEC 3, 6).
import type { FactStatus, PostStatus } from "../lib/types";

type Status = FactStatus | PostStatus;

const LABEL: Record<Status, string> = {
  confirmed: "Confirmed",
  needs_review: "Needs review",
  missing: "Missing",
  superseded: "Superseded",
  draft: "Draft",
  approved: "Approved",
  scheduled: "Scheduled",
  published: "Published",
};

function Icon({ status }: { status: Status }) {
  const common = { width: 12, height: 12, viewBox: "0 0 12 12", "aria-hidden": true, focusable: false } as const;
  switch (status) {
    case "confirmed":
    case "approved":
      return (
        <svg {...common}>
          <path d="M2 6.5 5 9.5 10.5 3" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" />
        </svg>
      );
    case "needs_review":
      return (
        <svg {...common}>
          <path d="M6 2v5M6 9.5v.5" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" />
        </svg>
      );
    case "missing":
      return (
        <svg {...common}>
          <circle cx="6" cy="6" r="4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeDasharray="2 2" />
        </svg>
      );
    case "scheduled":
      return (
        <svg {...common}>
          <circle cx="6" cy="6" r="4.5" fill="none" stroke="currentColor" strokeWidth="1.6" />
          <path d="M6 3.5V6l1.8 1.2" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
        </svg>
      );
    case "published":
      return (
        <svg width={11} height={12} viewBox="0 0 11 12" aria-hidden focusable={false}>
          <path d="M2.5 5V3.5a3 3 0 0 1 6 0V5M1.5 5h8v6h-8z" fill="none" stroke="currentColor" strokeWidth="1.6" />
        </svg>
      );
    case "draft":
      return (
        <svg {...common}>
          <path d="M2 10 3 7l5-5 2 2-5 5z" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
        </svg>
      );
    case "superseded":
      return (
        <svg {...common}>
          <path d="M2 6h8" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        </svg>
      );
  }
}

export function statusLabel(status: Status): string {
  return LABEL[status];
}

export function StatusChip({ status, label }: { status: Status; label?: string }) {
  return (
    <span className={`chip chip-${status}`}>
      <Icon status={status} />
      <span className={status === "superseded" ? "strike" : undefined}>{label ?? LABEL[status]}</span>
    </span>
  );
}
