"""Readable text from HTML with the standard library parser only.

Keeps the title and meta description, drops scripts, styles and other non-content, and puts
block elements on their own lines. Absolute link targets are kept when the anchor text hides
them, because the registration link is often behind "Register here".
"""

import re
from dataclasses import dataclass
from html.parser import HTMLParser

_SKIP = frozenset({"script", "style", "noscript", "template", "svg", "head", "iframe", "object"})
_BLOCK = frozenset(
    {
        "address", "article", "aside", "blockquote", "br", "dd", "div", "dl", "dt", "fieldset",
        "figcaption", "figure", "footer", "form", "h1", "h2", "h3", "h4", "h5", "h6", "header",
        "hr", "li", "main", "nav", "ol", "p", "pre", "section", "table", "td", "th", "tr", "ul",
    }
)  # fmt: skip
_VOID = frozenset({"br", "hr", "img", "meta", "link", "input", "source", "wbr"})


@dataclass(frozen=True)
class ExtractedText:
    text: str
    title: str
    script_count: int


class _Reader(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip_depth = 0
        self.in_title = False
        self.title = ""
        self.description = ""
        self.script_count = 0
        self.links: list[tuple[str, int]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {k: v or "" for k, v in attrs}
        if tag == "script":
            self.script_count += 1
        if tag == "title":
            self.in_title = True
            return
        if tag == "meta" and attr.get("name", "").lower() in ("description", "og:description"):
            self.description = self.description or attr.get("content", "").strip()
        if tag == "meta" and attr.get("property", "").lower() == "og:description":
            self.description = self.description or attr.get("content", "").strip()
        if tag in _SKIP and tag not in _VOID:
            self.skip_depth += 1
            return
        if self.skip_depth:
            return
        if tag in _BLOCK:
            self.parts.append("\n")
        if tag == "a":
            self.links.append((attr.get("href", ""), len(self.parts)))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIP:
            return
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False
            return
        if tag in _SKIP:
            self.skip_depth = max(0, self.skip_depth - 1)
            return
        if self.skip_depth:
            return
        if tag == "a" and self.links:
            href, start = self.links.pop()
            anchor = "".join(self.parts[start:]).strip()
            if re.match(r"https?://", href) and href not in anchor:
                self.parts.append(f" ({href})")
        if tag in _BLOCK:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title += data
        elif not self.skip_depth:
            self.parts.append(data)


def extract_text(html: str) -> ExtractedText:
    reader = _Reader()
    reader.feed(html)
    reader.close()
    title = _clean_line(reader.title)
    lines = [title, _clean_line(reader.description)]
    lines += [_clean_line(line) for line in "".join(reader.parts).split("\n")]
    text = "\n".join(line for line in lines if line)
    return ExtractedText(text=text, title=title, script_count=reader.script_count)


def _clean_line(line: str) -> str:
    return re.sub(r"\s+", " ", line.replace("\xa0", " ")).strip()
