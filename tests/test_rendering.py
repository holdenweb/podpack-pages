"""How a Markdown page's code and math reach the reader.

Two things happen in the browser, not here: Pygments' classes need the
stylesheet the page carries, and mdx_math's `<script type="math/tex">`
elements need MathJax loaded with the render action that looks for them.
These tests pin what the page must carry for that to work; the rendering
itself is checked by opening a page (README, Templates).
"""

from pathlib import Path

from flask import Flask

from conftest import SiteFactory

PYTHON = "def f(x):\n    return x + 1\n"


def test_a_fenced_block_is_highlighted(app: Flask, content: Path) -> None:
    (content / "md-pages" / "code.md").write_text(f"# Code\n\n```python\n{PYTHON}```\n")
    body = app.test_client().get("/pages/code").get_data(as_text=True)
    assert '<div class="codehilite">' in body
    assert '<span class="k">def</span>' in body  # Pygments marked it up ...
    assert ".codehilite .k {" in body  # ... and the page styles the marks


def test_an_unlabelled_fence_stays_plain(app: Flask, content: Path) -> None:
    """Highlighted iff the fence names a language: no guessing, however Python it looks."""
    (content / "md-pages" / "plain.md").write_text(f"# Plain\n\n```\n{PYTHON}```\n")
    body = app.test_client().get("/pages/plain").get_data(as_text=True)
    assert '<div class="codehilite">' in body
    assert '<span class="k">' not in body


def test_math_is_handed_to_mathjax_3(site: SiteFactory) -> None:
    """The loader lives in `{% block scripts %}`, which podpack's default chrome
    does not define (README: a chrome without it silently drops MathJax);
    tests/testsite's base.html has the block, as a real site's does."""
    app = site(site_package="testsite")
    pages = app.extensions["podpack"].data_root / "pages"
    (pages / "md-pages" / "math.md").write_text("# Math\n\n$$x^2$$\n")
    body = app.test_client().get("/pages/math").get_data(as_text=True)
    assert '<script type="math/tex; mode=display">' in body  # what mdx_math writes
    assert "mathjax@3.2.2/es5/tex-chtml.js" in body  # who renders it
    assert 'script[type^="math/tex"]' in body  # and how it finds it
    assert "cdn.mathjax.org" not in body  # the retired host


def test_a_site_rethemes_code_by_shipping_the_stylesheet(site: SiteFactory) -> None:
    """The stylesheet is included through the template loader, so a site's
    templates/podpack_pages/codehilite.css shadows the shipped one; tests/testsite
    ships exactly that file. Without it the shipped rules are what the page carries."""
    plain = site()
    themed = site(site_package="testsite")
    for app, rethemed in ((plain, False), (themed, True)):
        pages = app.extensions["podpack"].data_root / "pages"
        (pages / "md-pages" / "code.md").write_text("# Code\n\nplain prose\n")
        body = app.test_client().get("/pages/code").get_data(as_text=True)
        assert ("TESTSITE CODE THEME" in body) is rethemed, rethemed
        assert (".codehilite .k {" in body) is not rethemed, rethemed
