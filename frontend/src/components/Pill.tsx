import type { ReactNode } from "react";

type Tone = "ink" | "lime" | "mint" | "grey" | "peach" | "white" | "outline";

export function Pill({ tone = "white", children, className = "" }: { tone?: Tone; children: ReactNode; className?: string }) {
  return <span className={`pill pill-${tone} ${className}`}>{children}</span>;
}
