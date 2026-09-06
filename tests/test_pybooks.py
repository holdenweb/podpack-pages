"""The pybooks app: the pages kind under a second name, on trees of its own.

The content it exists for is orpy's `--fragments` output, so the tree written
here has that shape: absolute suffix-less links between pages, absolute css/js
links, relative image srcs, `common/` beside the courses.
"""

from pathlib import Path

from flask import Flask

from conftest import ALL_CONFIG, SiteFactory

from podpack_pages.pybooks import site_app

ORPY_LESSON = """<!-- title: Iteration: For and While Loops -->
<link rel="stylesheet" href="/pybooks/asset/common/course.css">
<script src="/pybooks/asset/common/course.js" defer></script>
<main class="lesson">
<img src="images/x.png">
<a href="/pybooks/python1/makingDecisions">Making Decisions</a>
<a href="/pybooks/python1/index">Contents</a>
</main>
"""


def _orpy_tree(root: Path) -> None:
    """A one-course fragment tree, as build.py --fragments lays it out."""
    course = root / "html-pages" / "python1"
    (course / "images").mkdir(parents=True)
    (course / "index.html").write_text(
        '<!-- title: Introduction to Python -->\n<a href="/pybooks/python1/iteration">Iteration</a>'
    )
    (course / "iteration.html").write_text(ORPY_LESSON)
    (course / "images" / "x.png").write_bytes(b"\x89PNG not really")
    common = root / "html-pages" / "common"
    common.mkdir()
    (common / "course.css").write_text("main { color: red }")


def _remounted(site: SiteFactory, mounts: dict[str, str]) -> Flask:
    return site(host_config={**ALL_CONFIG, "site": {**ALL_CONFIG["site"], "mounts": mounts}})


def test_pybooks_names_itself_after_its_blueprint() -> None:
    assert site_app.name == site_app.blueprint.name == "pybooks"


def test_a_site_installs_it_by_naming_the_subpackage(site: SiteFactory) -> None:
    app = site(
        host_config={
            "site": {"name": "test site", "environment": "test", "apps": ["podpack_pages.pybooks"]}
        }
    )
    assert app.test_client().get("/pybooks/").status_code == 200
    assert app.extensions["podpack"].installed_from == {"pybooks": "podpack_pages.pybooks"}


def test_its_placeholder_landing_page_is_seeded_from_its_own_package(
    family: Flask, pybooks_content: Path
) -> None:
    """Seeded from podpack_pages/pybooks/data, not from the pages app's data:
    the pages seed would put test.md and parts_demo.html here."""
    assert (pybooks_content / "html-pages" / "index.html").is_file()
    assert not (pybooks_content / "html-pages" / "parts_demo.html").exists()
    assert not (pybooks_content / "md-pages").exists()
    body = family.test_client().get("/pybooks/").get_data(as_text=True)
    assert "placeholder" in body
    assert "<title>Python courses</title>" in body  # its own title comment


def test_an_orpy_shaped_tree_serves_at_its_addresses(family: Flask, pybooks_content: Path) -> None:
    _orpy_tree(pybooks_content)
    client = family.test_client()

    lesson = client.get("/pybooks/python1/iteration")
    assert lesson.status_code == 200
    body = lesson.get_data(as_text=True)
    # Relative image src rewritten through this app's asset route; orpy's
    # absolute links pass through byte for byte, which is what it relies on.
    assert 'src="/pybooks/asset/python1/images/x.png"' in body
    assert 'href="/pybooks/python1/makingDecisions"' in body
    assert 'href="/pybooks/asset/common/course.css"' in body
    assert "<title>Iteration: For and While Loops</title>" in body

    # The contents page answers at both addresses orpy links, and the bare
    # directory redirects to its slash form.
    assert client.get("/pybooks/python1/").status_code == 200
    assert client.get("/pybooks/python1/index").status_code == 200
    bare = client.get("/pybooks/python1")
    assert bare.status_code == 308
    assert bare.headers["Location"].endswith("/pybooks/python1/")

    css = client.get("/pybooks/asset/common/course.css")
    assert css.status_code == 200
    assert css.mimetype == "text/css"
    assert css.headers["Cache-Control"] == "public, max-age=3600"
    assert client.get("/pybooks/asset/python1/images/x.png").mimetype == "image/png"


def test_pybooks_content_is_not_reachable_through_pages(
    family: Flask, pybooks_content: Path
) -> None:
    _orpy_tree(pybooks_content)
    client = family.test_client()
    assert client.get("/pages/python1/iteration").status_code == 404
    assert client.get("/pages/asset/common/course.css").status_code == 404


def test_pybooks_reads_its_own_config_section(family: Flask, pybooks_content: Path) -> None:
    (pybooks_content / "html-pages" / "plain.html").write_text("<p>untitled</p>")
    body = family.test_client().get("/pybooks/plain").get_data(as_text=True)
    assert "<title>A test-site course</title>" in body  # [apps.pybooks], not [apps.pages]


def test_its_nav_entry_resolves_to_its_root(family: Flask) -> None:
    body = family.test_client().get("/pages/test").get_data(as_text=True)
    assert '<a href="/pybooks/">Python</a>' in body


def test_pybooks_follows_its_own_mount(site: SiteFactory) -> None:
    """Routes, rewritten asset URLs and the nav entry all move with the mount;
    the other apps stay where they were."""
    app = _remounted(site, {"pybooks": "/courses"})
    _orpy_tree(app.extensions["podpack"].data_root / "pybooks")
    client = app.test_client()
    assert client.get("/pybooks/").status_code == 404
    body = client.get("/courses/python1/iteration").get_data(as_text=True)
    assert 'src="/courses/asset/python1/images/x.png"' in body
    assert '<a href="/courses/">Python</a>' in body
    assert client.get("/pages/test").status_code == 200
    assert client.get("/blog/").status_code == 200


def test_markdown_shadows_html_in_pybooks_too(family: Flask, pybooks_content: Path) -> None:
    (pybooks_content / "md-pages").mkdir()
    (pybooks_content / "md-pages" / "both.md").write_text("# From Markdown\n\nmd body")
    (pybooks_content / "html-pages" / "both.html").write_text("<p>html body</p>")
    body = family.test_client().get("/pybooks/both").get_data(as_text=True)
    assert "md body" in body
    assert "html body" not in body


def test_a_traversal_cannot_escape_the_pybooks_trees(family: Flask, tmp_path: Path) -> None:
    (tmp_path / "secret.txt").write_text("secret")
    client = family.test_client()
    for probe in (
        "/pybooks/asset/..%2f..%2fsecret.txt",
        "/pybooks/..%2f..%2fsecret.txt",
        "/pybooks/..%2f",
    ):
        response = client.get(probe)
        assert response.status_code == 404
        assert b"secret" not in response.data
