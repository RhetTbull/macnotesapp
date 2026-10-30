"""Get a cleaned/readable version of a webpage"""

import html
import re
from datetime import datetime
from typing import Tuple

import requests
from readability import Document

from macnotesapp import __version__

# seconds to wait for the server to respond
TIMEOUT = 30


def get_readable_html(url: str) -> Tuple[str, str]:
    """Downloads HTML from url and returns a 'readable' version suitable for storing in a Note

    Args:
        url: URL to download

    Returns:
        tuple of title, HTML

    Raises:
        requests.RequestException: if the URL can't be downloaded
    """

    response = requests.get(
        url,
        timeout=TIMEOUT,
        headers={"User-Agent": f"macnotesapp/{__version__}"},
    )
    response.raise_for_status()
    doc = Document(response.text)

    footer = (
        f'Original URL: <a href="{html.escape(url)}">{html.escape(url)}</a><br>'
        f"Accessed on: {datetime.now().isoformat()}"
        "</body>"
    )
    # use a function for the replacement so backslashes in the URL aren't treated as escapes
    html_text = re.sub("</body>", lambda _: footer, doc.summary())
    return doc.title(), html_text
