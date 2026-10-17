"""Pull the first JSON object out of model text.

Models wrap JSON in ```json fences, add prose around it, and leave trailing commas.
This finds the first balanced {...} (string-aware), drops trailing commas, and parses it.
"""

import json
import re
from typing import Any

_FENCE = re.compile(r"```[a-zA-Z]*\s*\n?(.*?)```", re.S)


class JSONExtractionError(ValueError):
    pass


def extract_json_object(text: str) -> dict[str, Any]:
    candidates = [m.group(1) for m in _FENCE.finditer(text)] + [text]
    last_error = "no JSON object found"
    for candidate in candidates:
        raw = _first_object(candidate)
        if raw is None:
            continue
        try:
            value = json.loads(_drop_trailing_commas(raw))
        except json.JSONDecodeError as exc:
            last_error = f"invalid JSON: {exc.msg} at position {exc.pos}"
            continue
        if isinstance(value, dict):
            return value
    raise JSONExtractionError(last_error)


def _first_object(text: str) -> str | None:
    start = text.find("{")
    while start != -1:
        end = _matching_brace(text, start)
        if end is not None:
            return text[start : end + 1]
        start = text.find("{", start + 1)
    return None


def _matching_brace(text: str, start: int) -> int | None:
    depth = 0
    in_string = False
    escaped = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
        elif ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i
    return None


def _drop_trailing_commas(raw: str) -> str:
    out: list[str] = []
    in_string = False
    escaped = False
    i = 0
    while i < len(raw):
        ch = raw[i]
        if in_string:
            out.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
        elif ch == '"':
            in_string = True
            out.append(ch)
        elif ch == ",":
            j = i + 1
            while j < len(raw) and raw[j].isspace():
                j += 1
            if j < len(raw) and raw[j] in "}]":
                i += 1
                continue
            out.append(ch)
        else:
            out.append(ch)
        i += 1
    return "".join(out)
