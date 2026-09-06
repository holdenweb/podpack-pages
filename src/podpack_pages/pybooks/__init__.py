"""The pybooks app: the Python course books, served like any other pages.

This is the pages app installed a second time under the name `pybooks`.
Everything it does is in `podpack_pages.views`; everything that differs --
its data directory, its config section, its mount, its log file -- follows
from the name, by podpack's own rules. Its `html-pages/` tree is where the
orpy `build.py --fragments` output is copied, verbatim.
"""

from podpack import Section

from ..views import PagesApp, make_blueprint

site_app = PagesApp(
    blueprint=make_blueprint("pybooks"),
    url_prefix="/pybooks",
    # The route carries defaults={"name": ""}, so url_for builds the app's
    # root with no arguments -- which is all a Section can give it.
    nav=(Section("Python", "pybooks.page"),),
)
