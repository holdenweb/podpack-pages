"""Serving pages from the unified content space.

This module is the *pages kind*: the views behind every app in this
distribution that serves a unified Markdown/HTML name space -- `pages` and
`pybooks` today. `make_blueprint(name)` builds one such app's blueprint; the
views are plain module-level functions shared by every one of them, and
everything that differs between the apps is resolved from the request.
`data_dir()`, `app_config()` and the template namespace all follow
`request.blueprint`, and `url_for(".asset")` names an endpoint relative to
the blueprint in play, so an app's name is typed once, in its `site_app`, and
nowhere here.
"""

import posixpath
import re
from logging import getLogger
from typing import Any

import markdown
from flask import Blueprint, Response, abort, redirect, url_for
from flask.typing import ResponseReturnValue

from podpack import SiteApp, app_config
from podpack.paths import data_dir

from . import chrome
from .content import (
    ASSET_CACHE_CONTROL,
    HTML_TREE,
    MD_TREE,
    ContentNotFound,
    find_asset,
    find_page,
    is_page_dir,
    rewrite_asset_urls,
)

logger = getLogger(__name__)

FALLBACK_TITLE = "Untitled"

# One instance, reset between documents: some extensions accumulate state.
_md = markdown.Markdown(extensions=["mdx_math", "codehilite"])

_HEADING = re.compile(r"^(#+)\s+(.+)")

# An HTML page may declare its title on its first line, as a comment. The
# Markdown rule's twin, and producer-neutral: a generator emits one line and
# each page names itself in the site's chrome instead of all wearing the app's
# default. The comment leaves the body, as the Markdown heading does.
_TITLE_COMMENT = re.compile(r"^\s*<!--\s*title:\s*(?P<title>.*?)\s*-->\s*$")


def make_blueprint(name: str) -> Blueprint:
    """The blueprint for one app of the pages kind, named `name`.

    Rules are added by hand rather than by decorator so that one set of view
    functions can serve several blueprints; a decorator binds a function to
    exactly one.
    """
    blueprint = chrome.blueprint(name)
    blueprint.add_url_rule("/", "page", page, defaults={"name": ""})
    blueprint.add_url_rule("/<path:name>", "page", page)
    blueprint.add_url_rule("/asset/<path:path>", "asset", asset)
    return blueprint


class PagesApp(SiteApp):
    """A pages-kind app that reports how much content it holds.

    Two counts on `/_status` answer the question an operator asks after copying
    a tree onto the host -- "did it land, and where?" -- without a shell.
    """

    def status(self) -> dict[str, Any]:
        # `/_status` is podpack's request, not this app's, so the name is
        # passed rather than read from the blueprint in play.
        root = data_dir(self.name)
        return {
            tree: sum(1 for p in (root / tree).rglob(f"*{suffix}") if p.is_file())
            for tree, suffix in ((MD_TREE, ".md"), (HTML_TREE, ".html"))
        }


def page(name: str) -> ResponseReturnValue:
    """One address per page, whatever format it is stored in.

    A directory's address is its slash form -- the app's root included -- and
    serves the directory's `index` page. The bare form redirects there rather
    than serving, so relative references inside an index page resolve within
    its directory.
    """
    if not name or name.endswith("/"):
        name += "index"
    try:
        kind, raw = find_page(data_dir(), name)
    except ContentNotFound:
        if is_page_dir(data_dir(), name):
            return redirect(url_for(".page", name=f"{name}/"), code=308)
        abort(404)
    if kind == "markdown":
        return _render_markdown(raw)
    return _render_html(raw, name)


def asset(path: str) -> ResponseReturnValue:
    """Serve an asset (image, stylesheet, ...) belonging to a page."""
    try:
        body, ctype = find_asset(data_dir(), path)
    except ContentNotFound:
        abort(404)
    resp = Response(body, mimetype=ctype)
    resp.headers["Cache-Control"] = ASSET_CACHE_CONTROL
    return resp


def _default_title() -> str:
    """The title for content that declares none: the app's own setting."""
    return str(app_config().get("default_title", FALLBACK_TITLE))


def _render_markdown(raw: str) -> ResponseReturnValue:
    """A leading heading becomes the page title and leaves the body."""
    first, _, rest = raw.partition("\n")
    match = _HEADING.match(first)
    if match:
        title, body = match.group(2), rest
    else:
        title, body = _default_title(), raw
    _md.reset()
    return chrome.render("markdown.html", content=_md.convert(body), title=title)


def _render_html(raw: str, name: str) -> ResponseReturnValue:
    """A leading title comment names the page; relative asset references are
    rewritten to this app's asset route."""
    first, _, rest = raw.partition("\n")
    match = _TITLE_COMMENT.match(first)
    if match and match.group("title"):
        title, body = match.group("title"), rest
    else:
        title, body = _default_title(), raw
    page_dir = posixpath.dirname(name)
    body = rewrite_asset_urls(body, page_dir, lambda target: url_for(".asset", path=target))
    return chrome.render("html.html", content=body, title=title)
