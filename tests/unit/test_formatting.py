"""Test conversion between text, Markdown, and Notes HTML"""

import pytest

from macnotesapp.formatting import (
    features_lost,
    markdown_lossy_features,
    markdown_to_html,
    normalize_format,
    text_to_html,
    title_from_line,
    to_html,
)
from macnotesapp.notesapp import title_html


def test_text_to_html_lines():
    assert (
        text_to_html("one\n\ntwo")
        == "<div>one</div>\n<div><br></div>\n<div>two</div>\n"
    )


def test_text_to_html_escapes():
    assert text_to_html('a < b & "c" <b>x</b>') == (
        '<div>a &lt; b &amp; "c" &lt;b&gt;x&lt;/b&gt;</div>\n'
    )


def test_title_html_escapes():
    assert title_html("Tom & Jerry <3") == "<div><h1>Tom &amp; Jerry &lt;3</h1></div>\n"


def test_markdown_to_html():
    assert "<strong>bold</strong>" in markdown_to_html("**bold**")


def test_markdown_lossy_features_plain():
    assert (
        markdown_lossy_features("<div><h1>Title</h1></div><div><b>bold</b> text</div>")
        == []
    )


def test_markdown_lossy_features_rich():
    body = (
        "<div><h1>Title</h1></div>\n"
        '<div><table><tr><td>x</td></tr></table><img src="data:,">'
        '<u>underline</u><span style="color: red">red</span></div>'
    )
    assert markdown_lossy_features(body) == [
        "tables",
        "images",
        "underline or strikethrough",
        "fonts, colors, or highlights",
    ]


def test_markdown_lossy_features_ignores_title():
    """Notes stores a title created from HTML as a bold, large font"""
    title = (
        '<div><b><font face=".AppleSystemUIFontBold">'
        '<span style="font-size: 24px">Title</span></font></b></div>'
    )
    assert markdown_lossy_features(f"{title}\n<div>plain</div>\n") == []
    assert markdown_lossy_features(title) == []
    assert markdown_lossy_features(f"{title}\n<div><u>x</u></div>") == [
        "underline or strikethrough"
    ]


def test_features_lost():
    """#75: what each kind of edit loses, from Note.content_features()"""
    features = ["bold or italic", "checklists", "colors", "links", "tables", "tags"]
    assert features_lost(features, "replace") == ["tables", "tags"]
    # rewriting the HTML keeps tables; colors haven't been checked
    assert features_lost(features, "html") == ["checklists", "colors", "tags"]
    assert features_lost(features, "markdown") == [
        "checklists",
        "colors",
        "tables",
        "tags",
    ]
    assert features_lost(["headings", "lists", "links"], "markdown") == []
    # dividers are objects in the text, so replacing the body loses them
    assert features_lost(["dividers", "links"], "replace") == ["dividers"]


def test_features_lost_append():
    """#51: appending rewrites the HTML, which keeps only what was checked to survive"""
    kept = [
        "bold or italic",
        "dividers",
        "fonts",
        "headings",
        "links",
        "lists",
        "monospaced",
        "tables",
        "underline or strikethrough",
    ]
    assert features_lost(kept, "append") == []
    lost = [
        "attachments",
        "block quotes",
        "checklists",
        "colors",
        "highlights",
        "inline objects",
        "link previews",
        "mentions",
        "tags",
    ]
    assert features_lost(lost, "append") == lost
    with pytest.raises(ValueError):
        features_lost([], "prepend")


@pytest.mark.parametrize(
    "format, expected",
    [
        ("text", "text"),
        ("plaintext", "text"),
        ("Markdown", "markdown"),
        ("HTML", "html"),
    ],
)
def test_normalize_format(format, expected):
    assert normalize_format(format) == expected


def test_normalize_format_unknown():
    with pytest.raises(ValueError, match="rtf"):
        normalize_format("rtf")


def test_to_html():
    """#39, #37: bodies can be text, Markdown, or HTML"""
    assert to_html("a\nb <c>", "text") == ("<div>a</div>\n<div>b &lt;c&gt;</div>\n")
    assert "<li>item</li>" in to_html("- item", "markdown")
    assert to_html("<p>x</p>", "html") == "<p>x</p>"


@pytest.mark.parametrize(
    "line, format, name",
    [
        ("# Title", "markdown", "Title"),
        ("## Title ##", "markdown", "Title"),
        ("   ###   Spaced", "markdown", "Spaced"),
        ("Issue #42", "markdown", "Issue #42"),
        ("#hashtag", "markdown", "#hashtag"),
        ("C# notes", "markdown", "C# notes"),
        ("<h1>Tom &amp; Jerry</h1>", "html", "Tom & Jerry"),
        ("<div><b>Bold</b> title</div>", "html", "Bold title"),
        ("# Not markdown", "text", "# Not markdown"),
        ("  padded  ", "text", "padded"),
    ],
)
def test_title_from_line(line, format, name):
    """#13: the name is plain text, without Markdown or HTML markup"""
    assert title_from_line(line, format) == name
