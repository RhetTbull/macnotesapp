""""Remove rich markup from the given text.
The CLI docstrings use rich markup for pretty-printing help text but this needs to be stripped for serving the docs.
"""
import re

import mkdocs.plugins

mkdocs.plugins.event_priority(-50)


def on_page_content(html, page, config, files, **kwargs):
    html = re.sub(r"\[[ib\/][ib]?\]", r"", html)
    return html
