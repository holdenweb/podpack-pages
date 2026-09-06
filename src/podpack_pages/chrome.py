"""How an app finds its templates: its own name first, then its package's.

`blueprint()` builds a blueprint that exposes the `templates/` directory of a
package -- this one by default, so every app here shares one shipped set --
and `render()` looks a page up under the app's own name first, then under
that package's. A site therefore restyles one app by shadowing
`templates/<app name>/<page>` (podpack ADR-0005), and every app of a kind by
shadowing `templates/<package>/<page>`.

The default namespace is the package's name and not the first app's, because
`pages` would then mean both an app and the default for its kind: a site
overriding `templates/pages/html.html` would restyle `pybooks` as well,
silently. And it is read off the blueprint rather than fixed here, so a
package of its own -- a `podpack_blog` depending on this one, say -- gets its
defaults from its own `templates/<its name>/` by passing its name once, to
`blueprint()`, and calling `render()` exactly as the apps here do.
"""

from flask import Blueprint, current_app, render_template, request

PACKAGE = "podpack_pages"


def blueprint(name: str, package: str = PACKAGE) -> Blueprint:
    """A blueprint named `name` whose templates are `package`'s.

    The import name is the package rather than the calling module, so the
    blueprint's root path is the package directory whichever module built it,
    and an app installed on its own still finds the shipped templates.
    """
    return Blueprint(name, package, template_folder="templates")


def render(page: str, **context: object) -> str:
    """Render `page` for the app handling this request.

    Flask tries the names in order across every loader -- site, then apps, then
    podpack's fallback -- so the site's override of the app's own name wins,
    and the package's default answers only when nothing more specific does.
    The package is the one the blueprint was built for: Flask keeps it as the
    blueprint's import name, which is also what locates its template folder,
    so the two cannot disagree.
    """
    serving = current_app.blueprints[request.blueprint or ""]
    return render_template([f"{serving.name}/{page}", f"{serving.import_name}/{page}"], **context)
