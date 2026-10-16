"""Word-level diff used by the change screen and redraft proposals."""

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Literal

_PIECES = re.compile(r"\s+|[^\s]+")


@dataclass(frozen=True)
class DiffOp:
    op: Literal["equal", "delete", "insert"]
    text: str


def word_diff(old: str, new: str) -> list[DiffOp]:
    a, b = _PIECES.findall(old), _PIECES.findall(new)
    ops: list[DiffOp] = []

    def emit(op: Literal["equal", "delete", "insert"], text: str) -> None:
        if not text:
            return
        if ops and ops[-1].op == op:
            ops[-1] = DiffOp(op, ops[-1].text + text)
        else:
            ops.append(DiffOp(op, text))

    for tag, i1, i2, j1, j2 in SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == "equal":
            emit("equal", "".join(a[i1:i2]))
        else:
            emit("delete", "".join(a[i1:i2]))
            emit("insert", "".join(b[j1:j2]))
    return ops


def changed_spans(old: str, new: str) -> list[tuple[str, str]]:
    """Pairs of (removed text, added text) for each changed region."""
    spans: list[tuple[str, str]] = []
    removed, added = "", ""
    for op in word_diff(old, new):
        if op.op == "equal":
            if removed or added:
                spans.append((removed, added))
            removed, added = "", ""
        elif op.op == "delete":
            removed += op.text
        else:
            added += op.text
    if removed or added:
        spans.append((removed, added))
    return spans
