// Word-level diff for display only (UI_SPEC 3 "Diff"). Tokens keep their whitespace so the
// joined segments reproduce each text exactly.

export interface Segment {
  text: string;
  kind: "same" | "removed" | "added";
}

function tokens(text: string): string[] {
  return text.match(/\s+|[^\s]+/g) ?? [];
}

export function wordDiff(oldText: string, newText: string): Segment[] {
  const a = tokens(oldText);
  const b = tokens(newText);
  const n = a.length;
  const m = b.length;
  // LCS table; post texts are short (a few hundred tokens at most).
  const dp: Uint16Array[] = Array.from({ length: n + 1 }, () => new Uint16Array(m + 1));
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
    }
  }
  const out: Segment[] = [];
  const push = (text: string, kind: Segment["kind"]) => {
    const last = out[out.length - 1];
    if (last && last.kind === kind) last.text += text;
    else out.push({ text, kind });
  };
  let i = 0;
  let j = 0;
  while (i < n && j < m) {
    if (a[i] === b[j]) {
      push(a[i], "same");
      i++;
      j++;
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      push(a[i++], "removed");
    } else {
      push(b[j++], "added");
    }
  }
  while (i < n) push(a[i++], "removed");
  while (j < m) push(b[j++], "added");
  return out;
}
