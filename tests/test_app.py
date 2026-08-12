"""Conformance with the podpack app contract, and the unified content space."""

from pathlib import Path

from flask import Flask

from conftest import SiteFactory

from podpack_pages import site_app
from podpack_pages.content import rewrite_asset_urls


def test_the_app_names_itself_after_its_blueprint() -> None:
    assert site_app.name == site_app.blueprint.name == "pages"


def test_a_site_installs_it_by_naming_it(site: SiteFactory) -> None:
    app = site()
    assert app.test_client().get("/pages/test").status_code == 200
    assert app.extensions["podpack"].installed_from == {"pages": "podpack_pages"}


def test_its_shipped_content_is_seeded_to_the_host(content: Path) -> None:
    assert (content / "md-pages" / "test.md").is_file()
    assert (content / "html-pages" / "parts_demo.html").is_file()


def test_the_site_decides_where_it_lands(site: SiteFactory) -> None:
    app = site(
        host_config={
            "site": {
                "name": "test site",
                "environment": "test",
                "apps": ["podpack_pages"],
                "mounts": {"pages": "/writing"},
            }
        }
    )
    client = app.test_client()
    assert client.get("/writing/test").status_code == 200
    assert client.get("/pages/test").status_code == 404


def test_one_name_space_markdown_first(app: Flask, content: Path) -> None:
    """The same name in both trees resolves to the Markdown page."""
    (content / "md-pages" / "both.md").write_text("# From Markdown\n\nmd body")
    (content / "html-pages" / "both.html").write_text("<p>html body</p>")
    body = app.test_client().get("/pages/both").get_data(as_text=True)
    assert "md body" in body
    assert "html body" not in body


def test_an_html_page_answers_when_no_markdown_shadows_it(app: Flask, content: Path) -> None:
    (content / "html-pages" / "plain.html").write_text("<p>just html</p>")
    body = app.test_client().get("/pages/plain").get_data(as_text=True)
    assert "just html" in body


def test_a_missing_page_is_404(app: Flask) -> None:
    assert app.test_client().get("/pages/no-such-page").status_code == 404


def test_a_leading_heading_becomes_the_title(app: Flask, content: Path) -> None:
    (content / "md-pages" / "titled.md").write_text("# The Real Title\n\nbody here")
    body = app.test_client().get("/pages/titled").get_data(as_text=True)
    assert "The Real Title" in body
    # The heading moved into the title; it is not repeated as an <h1> in the body.
    assert "<h1>The Real Title</h1>" not in body


def test_an_untitled_page_gets_the_sites_default_title(app: Flask, content: Path) -> None:
    (content / "md-pages" / "untitled.md").write_text("no heading at all")
    body = app.test_client().get("/pages/untitled").get_data(as_text=True)
    assert "A test-site note" in body  # [apps.pages] default_title in conftest


def test_relative_assets_are_rewritten_to_the_asset_route(app: Flask, content: Path) -> None:
    subdir = content / "html-pages" / "sub"
    subdir.mkdir()
    (subdir / "page.html").write_text('<img src="images/pic.png">')
    body = app.test_client().get("/pages/sub/page").get_data(as_text=True)
    assert 'src="/pages/asset/sub/images/pic.png"' in body


def test_the_rewrite_follows_a_remount(site: SiteFactory) -> None:
    """Asset URLs go through url_for, so they move when the site moves the app."""
    app = site(
        host_config={
            "site": {
                "name": "test site",
                "environment": "test",
                "apps": ["podpack_pages"],
                "mounts": {"pages": "/writing"},
            }
        }
    )
    content = app.extensions["podpack"].data_root / "pages"
    (content / "html-pages" / "moved.html").write_text('<img src="pic.png">')
    body = app.test_client().get("/writing/moved").get_data(as_text=True)
    assert 'src="/writing/asset/pic.png"' in body


def test_absolute_urls_pass_through_the_rewrite() -> None:
    html = '<a href="https://example.com/x">x</a><a href="#frag">f</a><img src="/abs.png">'
    assert rewrite_asset_urls(html, "dir", lambda t: f"/X/{t}") == html


def test_assets_are_served_with_a_content_type(app: Flask, content: Path) -> None:
    (content / "html-pages" / "style.css").write_bytes(b"body { color: red }")
    response = app.test_client().get("/pages/asset/style.css")
    assert response.status_code == 200
    assert response.mimetype == "text/css"
    assert response.data == b"body { color: red }"


def test_a_traversal_cannot_escape_the_content_trees(app: Flask, tmp_path: Path) -> None:
    (tmp_path / "secret.txt").write_text("secret")
    client = app.test_client()
    for probe in ("/pages/asset/..%2f..%2fsecret.txt", "/pages/..%2f..%2fsecret.txt"):
        response = client.get(probe)
        assert response.status_code == 404
        assert b"secret" not in response.data


def test_it_reads_the_host_copy_not_the_packaged_one(app: Flask, content: Path) -> None:
    (content / "md-pages" / "test.md").write_text("# Edited\n\nedited on the host")
    assert "edited on the host" in app.test_client().get("/pages/test").get_data(as_text=True)
