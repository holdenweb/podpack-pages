"""Locating content on disk, and preparing HTML pages for serving.

The app's data directory holds two trees, `md-pages/` and `html-pages/`,
seeded from the package on first install. Lookup presents them as a single
name space: `find_page("x")` tries `md-pages/x.md` before `html-pages/x.html`,
and assets resolve the same way. Which tree a file sits in is a storage
detail, not part of any page's address.

Everything here is shared between the apps in this distribution, and none of
it knows which app is asking: callers pass the root. This module raises and
never logs, so that a record lands in the log file of the app that was
serving rather than in whichever file a shared logger happens to feed.
"""

from __future__ import annotations

import mimetypes
import re
from collections.abc import Callable, Iterable
from pathlib import Path

MD_TREE = "md-pages"
HTML_TREE = "html-pages"

# Files served as stored -- images, stylesheets -- carry this; rendered pages
# carry nothing, so an edit on the host shows on the next request.
ASSET_CACHE_CONTROL = "public, max-age=3600"

_ABSOLUTE_PREFIXES = ("/", "http://", "https://", "data:", "#", "mailto:")


class ContentNotFound(LookupError):
    """The requested content does not exist."""


def check_relative(path: str) -> None:
    """Refuse anything that could step outside a content tree.

    Every path that reaches the disk goes through here, whether it came from a
    URL or from a file that lists paths (the blog's manifest). Only the
    segments are judged: "index.html" and ".html" are both legitimate names.
    """
    if not path or path.startswith("/"):
        raise ContentNotFound(path)
    for segment in path.split("/"):
        if segment in ("", "..", "."):
            raise ContentNotFound(path)


def find_page(root: Path, name: str) -> tuple[str, str]:
    """Resolve `name` in the unified space: Markdown first, then HTML.

    Returns `("markdown", text)` or `("html", text)`.
    """
    check_relative(name)
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


def is_page_dir(root: Path, name: str) -> bool:
    """True when `name` is a directory in either content tree."""
    try:
        check_relative(name)
    except ContentNotFound:
        return False
    return any((root / tree / name).is_dir() for tree in (MD_TREE, HTML_TREE))


def find_asset(
    root: Path, path: str, trees: Iterable[str] = (MD_TREE, HTML_TREE)
) -> tuple[bytes, str]:
    """Read a file to be served as stored, with its content type.

    Resolves the way pages resolve -- Markdown tree first -- unless the caller
    names the trees to search; the blog serves its export from one tree with
    the same guard and the same type guessing.
    """
    check_relative(path)
    for tree in trees:
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
    the view passes `url_for(".asset", ...)` so the result follows the app
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
