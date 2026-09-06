"""The pages app: a site's prose content, served from one name space.

Content is Markdown or HTML files under the app's host data directory. A
request names a page, not a format: the Markdown space is searched first and
the HTML space second, so the two kinds of content share one set of addresses
and a Markdown page shadows an HTML one of the same name. A request naming a
directory -- the app's root included -- serves the directory's `index` page.

This distribution ships three apps, each installed on its own by import name
and each an ordinary podpack app with its own data directory, config section,
mount, log and nav entry:

    podpack_pages           pages     this app, at /pages
    podpack_pages.pybooks   pybooks   the same kind of app under a second name,
                                      at /pybooks, for the generated course books
    podpack_pages.blog      blog      a Blogger export served from its manifest,
                                      at /blog

See README.md for what each expects on the host.
"""

from .views import PagesApp, make_blueprint

site_app = PagesApp(blueprint=make_blueprint("pages"), url_prefix="/pages")
