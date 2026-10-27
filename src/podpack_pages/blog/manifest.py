"""The export tree on disk, and the manifest that says what is in it.

sitescraper's export (`python -m blogscraper export`) is copied verbatim into
this app's `export/` directory: `manifest.json`, `posts/YYYY/MM/slug.html`
with each post's comment pages beside it as `slug.comments/N.html`, and
`images/`. The manifest is the contract (sitescraper ADR-0007): a request for
a path it lists -- a post, or one of the `comment_pages` listed under a post
(sitescraper ADR-0014) -- is decorated with the site's chrome; anything else
in the tree is served exactly as stored. It is read on every request, so a
fresh copy is live the moment it lands and nothing here can be stale.

Everything that can be wrong with a manifest is a `ManifestError` naming the
file and the reason, and it is raised for the whole file: a tree that cannot
be trusted is refused, not served in part.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from ..content import ContentNotFound, check_relative
from .publish import ROOT_PLACEHOLDER

EXPORT_TREE = "export"
MANIFEST = "manifest.json"


class ManifestError(Exception):
    """The manifest is missing or cannot be trusted; the message says why."""


@dataclass(frozen=True)
class Post:
    """One manifest entry: what the index and a post's dateline need."""

    path: str
    title: str
    published: str | None
    updated: str | None
    categories: tuple[str, ...]
    original_url: str | None

    @property
    def published_date(self) -> date | None:
        return datetime.fromisoformat(self.published).date() if self.published else None

    @property
    def year(self) -> str:
        """The year the index groups this post under: its own date, else the
        YYYY segment of its mirrored `posts/YYYY/MM/slug.html` path."""
        if self.published:
            return self.published[:4]
        parts = self.path.split("/")
        return parts[1] if len(parts) > 2 and parts[0] == "posts" else ""


@dataclass(frozen=True)
class CommentPage:
    """One page of a post's comments, listed under the post in the manifest.

    It is decorated as its post is and titled from it, but it is never an index
    entry: it belongs to the post, whose fragment links to it. `number` is its
    place in the post's list, which the export writes in page order.
    """

    path: str
    post: Post
    number: int
    pages: int


@dataclass(frozen=True)
class Manifest:
    path: Path
    generated_at: str | None
    posts: tuple[Post, ...]
    by_path: dict[str, Post]
    comment_pages: dict[str, CommentPage]


def load_manifest(root: Path, untitled: str) -> Manifest:
    """Read and validate `<root>/export/manifest.json`.

    Empty titles (Blogger exported sixteen of them) become `untitled` here, so
    nothing downstream needs a fallback. Every listed path passes the same
    traversal guard a URL does: a manifest is a file somebody copied, and is
    trusted no further than a request.
    """
    path = root / EXPORT_TREE / MANIFEST
    remedy = f"copy the sitescraper export (manifest.json, posts/, images/) into {path.parent}"
    try:
        document = json.loads(path.read_text())
    except OSError as exc:
        raise ManifestError(f"{path}: {exc.strerror or exc}; {remedy}") from exc
    except ValueError as exc:
        raise ManifestError(f"{path}: not valid JSON ({exc}); re-export, then {remedy}") from exc
    if not isinstance(document, dict) or not isinstance(document.get("posts"), list):
        raise ManifestError(f"{path}: has no 'posts' list; is it a sitescraper manifest?")
    placeholder = document.get("root_placeholder")
    if placeholder != ROOT_PLACEHOLDER:
        raise ManifestError(
            f"{path}: was exported with the root placeholder {placeholder!r}, but this "
            f"app substitutes {ROOT_PLACEHOLDER!r}; sitescraper and podpack_pages.blog.publish "
            "have to agree before any post can be served"
        )
    posts: list[Post] = []
    comment_pages: dict[str, CommentPage] = {}
    for i, entry in enumerate(document["posts"]):
        entry_path = entry.get("path") if isinstance(entry, dict) else None
        if not isinstance(entry_path, str):
            raise ManifestError(f"{path}: posts[{i}] has no 'path'")
        try:
            check_relative(entry_path)
        except ContentNotFound as exc:
            raise ManifestError(
                f"{path}: posts[{i}] path {entry_path!r} steps outside the export tree"
            ) from exc
        post = Post(
            path=entry_path,
            title=entry.get("title") or untitled,
            published=entry.get("published") or None,
            updated=entry.get("updated") or None,
            categories=tuple(entry.get("categories") or ()),
            original_url=entry.get("original_url") or None,
        )
        posts.append(post)
        listed = entry.get("comment_pages") or []
        comment_pages.update(_comment_pages(path, i, post, listed))
    return Manifest(
        path=path,
        generated_at=document.get("generated_at"),
        posts=tuple(posts),
        by_path={post.path: post for post in posts},
        comment_pages=comment_pages,
    )


def _comment_pages(
    manifest_path: Path, i: int, post: Post, listed: object
) -> dict[str, CommentPage]:
    """The pages of `post`'s comments, each path guarded as a post's is.

    An export older than sitescraper ADR-0014 omits the key, and a post with no
    comments lists none; either is simply no pages. Anything that is not a list
    of paths cannot be trusted, and refuses the whole file like any other fault.
    """
    if not isinstance(listed, list) or not all(isinstance(p, str) for p in listed):
        raise ManifestError(
            f"{manifest_path}: posts[{i}] comment_pages is not a list of paths"
        )
    pages: dict[str, CommentPage] = {}
    for number, page_path in enumerate(listed, start=1):
        try:
            check_relative(page_path)
        except ContentNotFound as exc:
            raise ManifestError(
                f"{manifest_path}: posts[{i}] comment page {page_path!r}"
                " steps outside the export tree"
            ) from exc
        pages[page_path] = CommentPage(page_path, post, number, len(listed))
    return pages


def read_post(root: Path, path: str) -> str:
    """The stored fragment for a listed path, or ContentNotFound.

    Listed but absent is a copy that did not complete, and the view says so;
    the guard has already run on the path when the manifest was loaded.
    """
    try:
        return (root / EXPORT_TREE / path).read_text()
    except OSError as exc:
        raise ContentNotFound(path) from exc
