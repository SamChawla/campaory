// Screen heading with the hand-drawn coral underline from the mockups.
import type { ReactNode } from "react";

export function Underline() {
  return (
    <svg className="scribble" aria-hidden="true" viewBox="0 0 240 14" preserveAspectRatio="none">
      <path d="M3 9C50 3 100 12 150 6S215 8 237 4" fill="none" stroke="currentColor" strokeWidth="6" strokeLinecap="round" />
    </svg>
  );
}

export function ScreenHeader({ eyebrow, title, lead, aside }: { eyebrow?: ReactNode; title: string; lead?: ReactNode; aside?: ReactNode }) {
  return (
    <header className="screen-head">
      <div className="screen-head-main">
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h1 className="screen-title">
          <span className="ul">
            {title}
            <Underline />
          </span>
        </h1>
        {lead && <p className="screen-lead">{lead}</p>}
      </div>
      {aside && <div className="screen-head-aside">{aside}</div>}
    </header>
  );
}
