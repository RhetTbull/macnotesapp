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


# formats for note bodies; "plaintext" is accepted for "text"
FORMATS = ("text", "markdown", "html")


# Note.content_features() that aren't text, so are lost whenever the body is replaced
OBJECT_FEATURES = {
    "attachments",
    "dividers",
    "link previews",
    "tables",
    "tags",
    "mentions",
    "inline objects",
}

# Note.content_features() that survive reading the body's HTML and writing it back,
# as when editing the HTML or appending to a note, checked on macOS 27.
# Headings become bold text in a larger font, and tables are recreated. Anything not
# listed, such as checklists (which become bulleted lists), block quotes, attachments,
# and tags, is lost or hasn't been checked, so is treated as lost.
HTML_SAFE_FEATURES = {
    "bold or italic",
    "dividers",
    "fonts",
    "headings",
    "links",
    "lists",
    "monospaced",
    "tables",
    "underline or strikethrough",
}

# Note.content_features() that survive converting the body to Markdown and back
MARKDOWN_SAFE_FEATURES = {"headings", "monospaced", "lists", "bold or italic", "links"}

# kinds of edit for features_lost()
EDITS = ("replace", "html", "append", "markdown")


def features_lost(features: list[str], edit: str) -> list[str]:
    """Return the features of a note (from Note.content_features()) lost by an edit

    Args:
        features: the note's content features
        edit: "replace" to replace the body, "html" to edit the body's HTML,
            "append" to add to the end of the body (which rewrites its HTML),
            or "markdown" to convert the body to Markdown and back
    """
    if edit == "replace":
        return [f for f in features if f in OBJECT_FEATURES]
    if edit in ("html", "append"):
        return [f for f in features if f not in HTML_SAFE_FEATURES]
    if edit == "markdown":
        return [f for f in features if f not in MARKDOWN_SAFE_FEATURES]
    raise ValueError(f"Unknown edit: {edit}; expected one of {', '.join(EDITS)}")


def normalize_format(format: str) -> str:
    """Return format as one of FORMATS, ignoring case

    Raises:
        ValueError: if format isn't a known format
    """
    normalized = format.lower()
    if normalized == "plaintext":
        normalized = "text"
    if normalized not in FORMATS:
        raise ValueError(
            f"Unknown format: {format}; expected one of {', '.join(FORMATS)}"
        )
    return normalized


def to_html(body: str, format: str) -> str:
    """Convert a body in format ("text", "markdown", or "html") to Notes HTML"""
    format = normalize_format(format)
    if format == "text":
        return text_to_html(body)
    if format == "markdown":
        return markdown_to_html(body)
    return body


def title_from_line(line: str, format: str) -> str:
    """Return a note's name from the first line of text in format

    Notes.app can't give a note's first line the Title style through scripting (#13),
    so formatting in that line is dropped: Markdown heading markers ("# Title") and
    HTML tags are removed.
    """
    format = normalize_format(format)
    if format == "markdown":
        if heading := re.match(r"\s{0,3}#{1,6}(\s+|$)(.*)", line):
            # an ATX heading may also end with #s
            line = re.sub(r"(^|\s+)#+\s*$", "", heading[2])
    elif format == "html":
        line = html.unescape(re.sub(r"<[^>]*>", "", line))
    return line.strip()


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
