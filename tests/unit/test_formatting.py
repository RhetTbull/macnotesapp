"""Test conversion between text, Markdown, and Notes HTML"""

from macnotesapp.formatting import (
    features_lost,
    markdown_lossy_features,
    markdown_to_html,
    text_to_html,
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
    assert features_lost(features, "html") == ["checklists", "tables", "tags"]
    assert features_lost(features, "markdown") == [
        "checklists",
        "colors",
        "tables",
        "tags",
    ]
    assert features_lost(["headings", "lists", "links"], "markdown") == []
