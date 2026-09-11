"""Serving a sitescraper export: listed posts decorated, the rest as stored.

Two routes, one rule. `/` is an index built from the manifest. Any other path
is looked up in the manifest first: a listed path is a post, whose placeholders
are filled with the mount the site actually gave this app and which is then
wrapped in the site's chrome; anything else that exists in the export tree --
an image, the manifest itself, a stray file -- is served exactly as stored
(sitescraper ADR-0007). No relative-URL rewriting happens here: fragments
carry absolute or placeholder URLs by contract, unlike the pages kind.

The manifest is read on every request. That costs milliseconds and buys the
property the host's refresh script promises for every app in this
distribution: a copied tree is live the moment it lands, with no restart and
nothing that can be stale.
"""

from logging import getLogger
from typing import Any

from flask import Response, abort, url_for
from flask.typing import ResponseReturnValue

from podpack import app_config
from podpack.paths import data_dir

from .. import chrome
from ..content import ASSET_CACHE_CONTROL, ContentNotFound, find_asset
from .manifest import EXPORT_TREE, Manifest, ManifestError, Post, load_manifest, read_post
from .publish import render_fragment

logger = getLogger(__name__)

FALLBACK_INDEX_TITLE = "Blog"
FALLBACK_POST_TITLE = "Untitled post"

blueprint = chrome.blueprint("blog")


@blueprint.route("/")
def index() -> ResponseReturnValue:
    """Every post, newest first, grouped by year."""
    manifest = _manifest()
    title = str(app_config().get("index_title", FALLBACK_INDEX_TITLE))
    return chrome.render(
        "blog-index.html", title=title, years=_by_year(manifest.posts), subnav=_archive(manifest)
    )


@blueprint.route("/<path:path>")
def page(path: str) -> ResponseReturnValue:
    """A listed path is a post; anything else on disk is served as stored."""
    manifest = _manifest()
    post = manifest.by_path.get(path)
    if post is not None:
        return _decorate(post, manifest)
    try:
        body, ctype = find_asset(data_dir(), path, trees=(EXPORT_TREE,))
    except ContentNotFound:
        abort(404)
    resp = Response(body, mimetype=ctype)
    resp.headers["Cache-Control"] = ASSET_CACHE_CONTROL
    return resp


def _manifest() -> Manifest:
    """The manifest as it is on disk right now, or 503 naming what is wrong.

    The whole blog is unavailable rather than partly served: without a
    trustworthy manifest nothing can say which files are posts. The message
    carries the file's path and the remedy, and `/healthz` says the same.
    """
    try:
        return load_manifest(data_dir(), _untitled())
    except ManifestError as exc:
        logger.error("blog unavailable: %s", exc)
        abort(503)


def _decorate(post: Post, manifest: Manifest) -> ResponseReturnValue:
    """Fill a post's placeholders with this app's mount and wrap it in chrome.

    A placeholder the contract does not define raises out of `render_fragment`
    and surfaces as a 500 with the post's path in the traceback -- loud on
    purpose, since nothing here can guess what an unknown placeholder meant.
    """
    try:
        raw = read_post(data_dir(), post.path)
    except ContentNotFound:
        logger.warning(
            "manifest lists %s but %s is missing: the copy did not complete; "
            "copy the export again, mirroring it",
            post.path,
            data_dir() / EXPORT_TREE / post.path,
        )
        abort(404)
    root = _root()
    html = render_fragment(raw, root, _image_root(root), source=post.path)
    return chrome.render(
        "blog-post.html",
        title=post.title,
        content=html,
        post=post,
        subnav=_archive(manifest, current_year=post.year),
    )


def _root() -> str:
    """What `${{{ROOT}}}` becomes: this app's mount, wherever the site put it.

    Derived from the index route rather than from any setting, so a remount
    moves every link inside every post with no regeneration. At the site root
    this is "" and `${{{ROOT}}}/posts/...` still joins correctly.
    """
    return url_for(".index").rstrip("/")


def _image_root(root: str) -> str:
    """What `${{{IMAGE_ROOT}}}` becomes: the site's `image_root`, else the mount.

    The same default the export's reference publisher encodes (ADR-0010): a
    self-contained tree needs nothing set; a site serving the images from
    elsewhere sets one key.
    """
    configured = app_config().get("image_root")
    return str(configured).rstrip("/") if configured else root


def _untitled() -> str:
    return str(app_config().get("default_title", FALLBACK_POST_TITLE))


def _by_year(posts: tuple[Post, ...]) -> list[tuple[str, list[Post]]]:
    """Posts newest first, grouped under their year in that order.

    Sorted on the ISO date string, which is one format throughout the export,
    so no naive-versus-aware datetime comparison can arise; an undated post
    sorts last and is grouped under the year of its mirrored path.
    """
    ordered = sorted(posts, key=lambda p: (p.published or "", p.path), reverse=True)
    years: dict[str, list[Post]] = {}
    for post in ordered:
        years.setdefault(post.year, []).append(post)
    return list(years.items())


def _archive(manifest: Manifest, current_year: str | None = None) -> list[dict[str, Any]]:
    """A year-archive section nav, newest first, linking to the index anchors.

    One group of year links to `<mount>/#<year>` -- the index's own year
    headings carry those ids -- so it works from a post page as well as from
    the index, and marks the post's year current. The shape matches the pages
    kind's `Subnav` and the site's subnav template: groups of {label, href,
    current} items.
    """
    root = _root()
    items = [
        {
            "label": year or "Undated",
            "href": f"{root}/#{year or 'undated'}",
            "current": year == current_year,
        }
        for year, _posts in _by_year(manifest.posts)
    ]
    return [{"heading": "Archive", "items": items}]
