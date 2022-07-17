"""Get a cleaned/readable version of a webpage"""

import re
from datetime import datetime
from typing import Tuple

import requests
from readability import Document


def get_readable_html(url: str) -> Tuple[str, str]:
    """Downloads HTML from url and returns a 'readable' version suitable for storing in a Note

    Args:
        url: URL to download

    Returns:
        tuple of title, HTML
    """

    response = requests.get(url)
    doc = Document(response.text)

    re_body_endtag = re.compile("</body>")
    html_text = re.sub(
        re_body_endtag,
        f"Original URL: <a href={url}>{url}</a><br>"
        f"Accessed on: {datetime.now().isoformat()}"
        "</body>",
        doc.summary(),
    )
    return doc.title(), html_text
