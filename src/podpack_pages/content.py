"""Locating content on disk, and preparing HTML pages for serving.

The app's data directory holds two trees, `md-pages/` and `html-pages/`,
seeded from the package on first install. Lookup presents them as a single
name space: `find_page("x")` tries `md-pages/x.md` before `html-pages/x.html`,
and assets resolve the same way. Which tree a file sits in is a storage
detail, not part of any page's address.
"""

from __future__ import annotations

import mimetypes
import re
from collections.abc import Callable
from pathlib import Path

MD_TREE = "md-pages"
HTML_TREE = "html-pages"

_ABSOLUTE_PREFIXES = ("/", "http://", "https://", "data:", "#", "mailto:")


class ContentNotFound(LookupError):
    """The requested content does not exist."""


def _check_relative(path: str) -> None:
    """Refuse anything that could step outside the content trees."""
    if not path or path.startswith("/"):
        raise ContentNotFound(path)
    for segment in path.split("/"):
        if segment in ("", "..", "."):
            raise ContentNotFound(path)


def find_page(root: Path, name: str) -> tuple[str, str]:
    """Resolve `name` in the unified space: Markdown first, then HTML.

    Returns `("markdown", text)` or `("html", text)`.
    """
    _check_relative(name)
    candidates = (
        ("markdown", root / MD_TREE / f"{name}.md"),
        ("html", root / HTML_TREE / f"{name}.html"),
    )
    for kind, path in candidates:
        try:
            return kind, path.read_text()
        except OSError:
            continue
    raise ContentNotFound(name)


def find_asset(root: Path, path: str) -> tuple[bytes, str]:
    """Resolve an asset the same way pages resolve: Markdown tree first."""
    _check_relative(path)
    for tree in (MD_TREE, HTML_TREE):
        fpath = root / tree / path
        try:
            body = fpath.read_bytes()
        except OSError:
            continue
        ctype, _ = mimetypes.guess_type(str(fpath))
        return body, ctype or "application/octet-stream"
    raise ContentNotFound(path)


# src="…" / href="…" with either quoting style. Non-greedy value match so
# multiple attributes on the same tag don't get swallowed together.
_ATTR_RE = re.compile(
    r'(?P<attr>src|href)\s*=\s*(?P<q>["\'])(?P<val>[^"\']*)(?P=q)',
    re.IGNORECASE,
)


def rewrite_asset_urls(html: str, page_dir: str, asset_url: Callable[[str], str]) -> str:
    """Rewrite relative `src`/`href` values through `asset_url`.

    `asset_url` maps a path relative to the content trees to a servable URL --
    the view passes `url_for("pages.asset", ...)` so the result follows the app
    wherever the site mounts it. Absolute URLs, anchors, `mailto:` and `data:`
    URIs pass through unchanged. `page_dir` is the directory the page lives in
    relative to its tree, empty at the root.
    """

    def _replace(m: re.Match[str]) -> str:
        val = m.group("val")
        lowered = val.lower()
        if any(lowered.startswith(p) for p in _ABSOLUTE_PREFIXES):
            return m.group(0)
        target = f"{page_dir}/{val}" if page_dir else val
        return f'{m.group("attr")}={m.group("q")}{asset_url(target)}{m.group("q")}'

    return _ATTR_RE.sub(_replace, html)
