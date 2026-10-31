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


# Note.content_features() that aren't text, so are lost whenever the body is replaced
OBJECT_FEATURES = {
    "attachments",
    "link previews",
    "tables",
    "tags",
    "mentions",
    "inline objects",
}

# Note.content_features() that survive converting the body to Markdown and back
MARKDOWN_SAFE_FEATURES = {"headings", "monospaced", "lists", "bold or italic", "links"}


def features_lost(features: list[str], edit: str) -> list[str]:
    """Return the features of a note (from Note.content_features()) lost by an edit

    Args:
        features: the note's content features
        edit: "replace" to replace the body, "html" to edit the body's HTML,
            or "markdown" to convert the body to Markdown and back
    """
    if edit == "replace":
        lost = OBJECT_FEATURES
    elif edit == "html":
        # checklists come back as bulleted lists
        lost = OBJECT_FEATURES | {"checklists"}
    elif edit == "markdown":
        return [f for f in features if f not in MARKDOWN_SAFE_FEATURES]
    else:
        raise ValueError(f"Unknown edit: {edit}")
    return [f for f in features if f in lost]


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
    """Return list of features in HTML body that would be lost by converting to Markdown and back

    The first line, the note's title, is ignored: notes created from HTML (as macnotesapp
    does) have a title in a bold, large font, which survives Markdown as a heading.
    """
    rest = body.split("\n", 1)[1] if "\n" in body else ""
    return [
        feature
        for feature, pattern in _LOSSY_MARKDOWN_PATTERNS.items()
        if pattern.search(rest)
    ]
