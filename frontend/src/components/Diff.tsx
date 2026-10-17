// Current and proposed text side by side. Removed words are struck through in peach, added
// words are highlighted in lime, and a text legend says so (UI_SPEC 3).
import { useMemo } from "react";
import { wordDiff } from "../lib/worddiff";

export function Diff({ oldText, newText }: { oldText: string; newText: string }) {
  const segments = useMemo(() => wordDiff(oldText, newText), [oldText, newText]);
  return (
    <div className="diff">
      <p className="diff-legend small muted">Struck-through text is removed. Highlighted text is new. Nothing changes until you accept.</p>
      <div className="diff-cols">
        <div className="diff-col diff-old">
          <div className="diff-label">Current</div>
          <p className="post-text">
            {segments
              .filter((s) => s.kind !== "added")
              .map((s, i) =>
                s.kind === "removed" ? (
                  <del key={i}>
                    <span className="sr-only">removed: </span>
                    {s.text}
                  </del>
                ) : (
                  <span key={i}>{s.text}</span>
                ),
              )}
          </p>
        </div>
        <div className="diff-col diff-new">
          <div className="diff-label">Proposed</div>
          <p className="post-text">
            {segments
              .filter((s) => s.kind !== "removed")
              .map((s, i) =>
                s.kind === "added" ? (
                  <ins key={i}>
                    <span className="sr-only">added: </span>
                    {s.text}
                  </ins>
                ) : (
                  <span key={i}>{s.text}</span>
                ),
              )}
          </p>
        </div>
      </div>
    </div>
  );
}
