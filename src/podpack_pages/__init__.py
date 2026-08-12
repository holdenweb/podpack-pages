"""The pages app: a site's prose content, served from one name space.

Content is Markdown or HTML files under the app's host data directory. A
request names a page, not a format: the Markdown space is searched first and
the HTML space second, so the two kinds of content share one set of addresses
and a Markdown page shadows an HTML one of the same name.
"""

from podpack import SiteApp

from .views import blueprint

site_app = SiteApp(
    blueprint=blueprint,
    url_prefix="/pages",
)
