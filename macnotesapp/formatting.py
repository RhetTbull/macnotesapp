"""Convert between plain text, Markdown, and the HTML used by Notes.app"""

from __future__ import annotations

import html
import re

# extra features to support for Markdown to HTML conversion with markdown2
MARKDOWN_EXTRAS = ["fenced-code-blocks", "footnotes", "tables"]

# HTML that does not survive a round trip through Markdown
_LOSSY_MARKDOWN_PATTERNS = {
    "tables": re.compile(r"<table\b", re.IGNORECASE),
    "images": re.compile(r"<img\b", re.IGNORECASE),
    "embedded objects": re.compile(r"<object\b", re.IGNORECASE),
    "underline or strikethrough": re.compile(r"<(u|s|strike)\b", re.IGNORECASE),
    "fonts, colors, or highlights": re.compile(
        r"<font\b|\bstyle=\"[^\"]*(color|font|background)", re.IGNORECASE
    ),
}


def text_to_html(text: str) -> str:
    """Convert plain text to Notes HTML, one <div> per line, escaping HTML characters"""
    return "".join(
        f"<div>{html.escape(line, quote=False) or '<br>'}</div>\n"
        for line in text.split("\n")
    )


def markdown_to_html(text: str) -> str:
    """Convert Markdown to HTML"""
    import markdown2

    return markdown2.markdown(text, extras=MARKDOWN_EXTRAS)


def html_to_markdown(text: str) -> str:
    """Convert HTML to Markdown"""
    # imported here because markdownify loads BeautifulSoup and lxml
    from markdownify import markdownify

    return markdownify(text)


def markdown_lossy_features(body: str) -> list[str]:
    """Return list of features in HTML body that would be lost by converting to Markdown and back"""
    return [
        feature
        for feature, pattern in _LOSSY_MARKDOWN_PATTERNS.items()
        if pattern.search(body)
    ]
