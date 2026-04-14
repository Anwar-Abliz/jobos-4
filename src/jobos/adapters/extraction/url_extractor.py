"""URL content extraction using trafilatura + httpx."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Domains known to require authentication — content will be a login/shell page
AUTH_WALL_DOMAINS = (
    "teams.microsoft.com",
    "login.microsoftonline.com",
    "login.live.com",
    "sharepoint.com",
    "docs.google.com",
    "drive.google.com",
    "notion.so",
    "app.slack.com",
    "app.asana.com",
    "app.clickup.com",
    "app.monday.com",
    "figma.com",
    "miro.com",
    "confluence.atlassian.com",
)

# Minimum meaningful text length after extraction
MIN_USEFUL_TEXT_LENGTH = 50


@dataclass
class ExtractedContent:
    text: str
    title: str = ""
    source: str = ""
    metadata: dict[str, str] = field(default_factory=dict)


class AuthWallError(Exception):
    """Raised when the URL returns a login/app shell instead of content."""


async def extract_from_url(url: str) -> ExtractedContent:
    """Fetch URL with httpx and extract main text with trafilatura."""
    import httpx
    import trafilatura

    # Check for known auth-wall domains before fetching
    url_lower = url.lower()
    for domain in AUTH_WALL_DOMAINS:
        if domain in url_lower:
            raise AuthWallError(
                f"This URL ({domain}) requires authentication and cannot be "
                "fetched directly. Copy the page content and paste it in the "
                "Text tab instead."
            )

    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    downloaded = resp.text
    extracted = trafilatura.extract(
        downloaded,
        include_comments=False,
        include_tables=True,
        favor_precision=True,
    )
    metadata_json = trafilatura.extract(
        downloaded,
        output_format="json",
        include_comments=False,
    )

    title = ""
    meta_dict: dict[str, str] = {}
    if metadata_json:
        import json

        try:
            parsed = json.loads(metadata_json)
            title = parsed.get("title", "")
            meta_dict = {
                k: str(v)
                for k, v in parsed.items()
                if k in ("title", "author", "date", "sitename", "description")
                and v
            }
        except (json.JSONDecodeError, TypeError):
            pass

    # Check if we got meaningful content
    text = extracted or ""
    if len(text.strip()) < MIN_USEFUL_TEXT_LENGTH:
        # trafilatura couldn't extract real content — likely a JS app shell or login page
        if _looks_like_app_shell(downloaded):
            raise AuthWallError(
                "The URL returned a login page or JavaScript application shell "
                "with no readable content. This usually means the page requires "
                "authentication. Copy the page content and paste it in the "
                "Text tab instead."
            )
        # Fall back to raw HTML truncated
        text = downloaded[:5000]

    return ExtractedContent(
        text=text,
        title=title,
        source=url,
        metadata=meta_dict,
    )


def _looks_like_app_shell(html: str) -> bool:
    """Heuristic: detect login pages and JS-only app shells."""
    lower = html.lower()
    # Very little visible text relative to HTML size
    visible_text = re.sub(r"<[^>]+>", "", html).strip()
    if len(html) > 1000 and len(visible_text) < 200:
        return True
    # Common auth-wall indicators
    auth_markers = [
        "login.microsoftonline",
        "sign in",
        "signin",
        "auth/authorize",
        "id_token",
        "access_token",
        "noscript",
        "__next",  # Next.js shell with no SSR content
    ]
    marker_count = sum(1 for m in auth_markers if m in lower)
    return marker_count >= 2
