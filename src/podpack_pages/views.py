"""Serving pages from the unified content space."""

import posixpath
import re
from logging import getLogger

import markdown
from flask import Blueprint, abort, redirect, render_template, url_for, Response
from flask.typing import ResponseReturnValue

from podpack import app_config
from podpack.paths import data_dir

from .content import (
    ContentNotFound,
    find_asset,
    find_page,
    is_page_dir,
    rewrite_asset_urls,
)

logger = getLogger(__name__)

blueprint = Blueprint("pages", __name__, template_folder="templates")

FALLBACK_TITLE = "Untitled"

# One instance, reset between documents: some extensions accumulate state.
_md = markdown.Markdown(extensions=["mdx_math", "codehilite"])

_HEADING = re.compile(r"^(#+)\s+(.+)")


@blueprint.route("/", defaults={"name": ""})
@blueprint.route("/<path:name>")
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
            return redirect(url_for("pages.page", name=f"{name}/"), code=308)
        abort(404)
    if kind == "markdown":
        return _render_markdown(raw)
    return _render_html(raw, name)


@blueprint.route("/asset/<path:path>")
def asset(path: str) -> ResponseReturnValue:
    """Serve an asset (image, stylesheet, ...) belonging to a page."""
    try:
        body, ctype = find_asset(data_dir(), path)
    except ContentNotFound:
        abort(404)
    resp = Response(body, mimetype=ctype)
    resp.headers["Cache-Control"] = "public, max-age=3600"
    return resp


def _render_markdown(raw: str) -> ResponseReturnValue:
    """A leading heading becomes the page title and leaves the body."""
    first, _, rest = raw.partition("\n")
    match = _HEADING.match(first)
    if match:
        title = match.group(2)
        body = rest
    else:
        title = app_config().get("default_title", FALLBACK_TITLE)
        body = raw
    _md.reset()
    return render_template(
        "pages/markdown.html", content=_md.convert(body), title=title
    )


def _render_html(raw: str, name: str) -> ResponseReturnValue:
    """Relative asset references are rewritten to this app's asset route."""
    page_dir = posixpath.dirname(name)
    body = rewrite_asset_urls(
        raw, page_dir, lambda target: url_for("pages.asset", path=target)
    )
    return render_template("pages/html.html", content=body)
