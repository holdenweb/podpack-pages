"""The blog app: a sitescraper export, decorated where the manifest says.

Fixtures write sitescraper-shaped exports (`write_manifest`, `write_post` in
conftest) over the seeded sample, so every assertion is against the real
contract: `.html` kept, placeholders in the bodies, membership decides.
"""

import logging
from pathlib import Path

import pytest
from flask import Flask

from conftest import ALL_CONFIG, SiteFactory, write_manifest, write_post

from podpack_pages.blog import site_app

# A body as the export writes it: a link to another post and a harvested image.
POST = (
    '<p>See <a href="${{{ROOT}}}/posts/2020/01/other.html">the other</a>'
    ' <img src="${{{IMAGE_ROOT}}}/images/y.png"></p>'
)
SAMPLE = "posts/2026/01/welcome.html"  # the shipped sample export's one post


def _site(site: SiteFactory, **changes: object) -> Flask:
    """The three-app site with `[site]` keys changed (mounts, say)."""
    return site(host_config={**ALL_CONFIG, "site": {**ALL_CONFIG["site"], **changes}})


def test_the_blog_names_itself_after_its_blueprint() -> None:
    assert site_app.name == site_app.blueprint.name == "blog"


def test_a_site_installs_it_by_naming_the_subpackage(site: SiteFactory) -> None:
    app = site(
        host_config={
            "site": {"name": "test site", "environment": "test", "apps": ["podpack_pages.blog"]}
        }
    )
    assert app.test_client().get("/blog/").status_code == 200
    assert app.extensions["podpack"].installed_from == {"blog": "podpack_pages.blog"}


def test_its_sample_export_is_seeded_and_served(family: Flask, blog_export: Path) -> None:
    """The sample proves the whole chain on a fresh install: manifest read,
    post decorated, placeholder filled with the mount."""
    assert (blog_export / "manifest.json").is_file()
    client = family.test_client()
    assert f'href="/blog/{SAMPLE}"' in client.get("/blog/").get_data(as_text=True)
    body = client.get(f"/blog/{SAMPLE}").get_data(as_text=True)
    assert 'href="/blog/"' in body
    assert "${{{" not in body


def test_the_index_lists_posts_newest_first_grouped_by_year(
    family: Flask, blog_export: Path
) -> None:
    write_manifest(
        blog_export,
        [
            {"path": "posts/2019/12/old.html", "title": "Old", "published": "2019-12-31T00:00:00"},
            {"path": "posts/2026/02/new.html", "title": "New", "published": "2026-02-01T00:00:00"},
            {"path": "posts/2020/01/mid.html", "title": "Mid", "published": "2020-01-02T00:00:00"},
        ],
    )
    body = family.test_client().get("/blog/").get_data(as_text=True)
    assert body.index(">New<") < body.index(">Mid<") < body.index(">Old<")
    assert body.index("<h2>2026</h2>") < body.index("<h2>2020</h2>") < body.index("<h2>2019</h2>")
    assert 'href="/blog/posts/2026/02/new.html"' in body
    assert "<title>A test-site blog</title>" in body  # [apps.blog] index_title


def test_a_listed_post_is_decorated_with_the_sites_chrome(
    family: Flask, blog_export: Path
) -> None:
    write_manifest(
        blog_export,
        [
            {
                "path": "posts/2020/01/first.html",
                "title": "First",
                "published": "2020-01-02T00:00:00",
                "categories": ["python"],
            }
        ],
    )
    write_post(blog_export, "posts/2020/01/first.html", POST)
    response = family.test_client().get("/blog/posts/2020/01/first.html")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'href="/blog/posts/2020/01/other.html"' in body
    assert 'src="/blog/images/y.png"' in body
    assert "<title>First</title>" in body
    assert "2 January 2020" in body and "python" in body  # the dateline
    assert "Served by podpack" in body  # extends base.html: the chrome wraps it


def test_the_roots_follow_a_remount(site: SiteFactory) -> None:
    """ROOT is the mount the site chose, read per request, so every link inside
    every post moves with no regeneration -- and so does the nav entry."""
    app = _site(site, mounts={"blog": "/weblog"})
    export = app.extensions["podpack"].data_root / "blog" / "export"
    write_manifest(export, [{"path": "posts/2020/01/first.html"}])
    write_post(export, "posts/2020/01/first.html", POST)
    client = app.test_client()
    assert client.get("/blog/").status_code == 404
    body = client.get("/weblog/posts/2020/01/first.html").get_data(as_text=True)
    assert 'href="/weblog/posts/2020/01/other.html"' in body
    assert 'src="/weblog/images/y.png"' in body
    assert '<a href="/weblog/">Blog</a>' in body
    assert "/blog/" not in body


def test_image_root_comes_from_the_site(site: SiteFactory) -> None:
    """One key moves the images to a shared host and leaves the content where
    it is -- the export's own default, `IMAGE_ROOT` falling back to `ROOT`,
    is what a site gets by leaving it unset (sitescraper ADR-0010)."""
    blog = {**ALL_CONFIG["apps"]["blog"], "image_root": "https://img.example/"}
    app = site(host_config={**ALL_CONFIG, "apps": {**ALL_CONFIG["apps"], "blog": blog}})
    export = app.extensions["podpack"].data_root / "blog" / "export"
    write_manifest(export, [{"path": "posts/2020/01/first.html"}])
    write_post(export, "posts/2020/01/first.html", POST)
    body = app.test_client().get("/blog/posts/2020/01/first.html").get_data(as_text=True)
    assert 'src="https://img.example/images/y.png"' in body
    assert 'href="/blog/posts/2020/01/other.html"' in body


def test_jinja_and_shell_syntax_in_a_post_body_pass_through(
    family: Flask, blog_export: Path
) -> None:
    """The consumer side of sitescraper ADR-0009: only the sentinels are live."""
    sample = "shell=${HOME} var={{ x }} block={% for i in xs %}{{ i }}{% endfor %} comment={# note #}"
    write_manifest(blog_export, [{"path": "posts/2020/01/code.html"}])
    write_post(blog_export, "posts/2020/01/code.html", f"<pre>{sample}</pre> ${{{{{{ROOT}}}}}}/")
    body = family.test_client().get("/blog/posts/2020/01/code.html").get_data(as_text=True)
    assert sample in body
    assert "/blog/" in body


def test_no_relative_url_rewrite_is_applied_to_posts(family: Flask, blog_export: Path) -> None:
    """Fragments are absolute by contract; the pages kind's rewrite must not touch them."""
    write_manifest(blog_export, [{"path": "posts/2020/01/p.html"}])
    write_post(blog_export, "posts/2020/01/p.html", '<img src="local.png">')
    body = family.test_client().get("/blog/posts/2020/01/p.html").get_data(as_text=True)
    assert 'src="local.png"' in body


def test_an_unlisted_file_is_served_as_stored(family: Flask, blog_export: Path) -> None:
    (blog_export / "images").mkdir()
    (blog_export / "images" / "y.png").write_bytes(b"\x89PNG bytes")
    response = family.test_client().get("/blog/images/y.png")
    assert response.status_code == 200
    assert response.data == b"\x89PNG bytes"
    assert response.mimetype == "image/png"
    assert response.headers["Cache-Control"] == "public, max-age=3600"


def test_an_unlisted_html_file_is_served_as_stored_not_decorated(
    family: Flask, blog_export: Path
) -> None:
    """Membership decides, not the extension (ADR-0007): a file the manifest
    does not list is not a post, whatever it is called."""
    write_post(blog_export, "posts/2020/01/stray.html", "<p>stray ${{{ROOT}}}</p>")
    response = family.test_client().get("/blog/posts/2020/01/stray.html")
    assert response.status_code == 200
    assert response.data == b"<p>stray ${{{ROOT}}}</p>"


def test_the_manifest_itself_is_served_as_stored(family: Flask) -> None:
    response = family.test_client().get("/blog/manifest.json")
    assert response.status_code == 200
    assert response.mimetype == "application/json"


def test_a_post_address_keeps_its_html_suffix(family: Flask) -> None:
    """Blogger's paths, mirrored 1:1 under the mount (ADR-0007)."""
    client = family.test_client()
    assert client.get(f"/blog/{SAMPLE}").status_code == 200
    assert client.get(f"/blog/{SAMPLE.removesuffix('.html')}").status_code == 404


def test_an_untitled_post_gets_the_default_title(family: Flask, blog_export: Path) -> None:
    """Blogger exported sixteen posts with no title; their path has no slug either."""
    write_manifest(blog_export, [{"path": "posts/2007/09/.html", "published": "2007-09-01T00:00:00"}])
    write_post(blog_export, "posts/2007/09/.html", "<p>no title</p>")
    client = family.test_client()
    assert ">An untitled test post<" in client.get("/blog/").get_data(as_text=True)
    response = client.get("/blog/posts/2007/09/.html")
    assert response.status_code == 200
    assert "<title>An untitled test post</title>" in response.get_data(as_text=True)


def test_a_listed_post_missing_on_disk_is_404_and_logged(
    family: Flask, blog_export: Path, caplog: pytest.LogCaptureFixture
) -> None:
    write_manifest(blog_export, [{"path": "posts/2020/01/gone.html"}])
    with caplog.at_level(logging.WARNING, logger="podpack_pages.blog"):
        assert family.test_client().get("/blog/posts/2020/01/gone.html").status_code == 404
    assert "posts/2020/01/gone.html" in caplog.text
    assert "did not complete" in caplog.text


BREAKAGES = [
    ("missing", None, "copy the sitescraper export"),
    ("malformed", "{not json", "not valid JSON"),
    ("no posts list", '{"root_placeholder": "${{{ROOT}}}", "posts": "x"}', "no 'posts' list"),
    ("foreign placeholder", '{"root_placeholder": "${ROOT}", "posts": []}', "${ROOT}"),
    ("entry without path", '{"root_placeholder": "${{{ROOT}}}", "posts": [{"title": "x"}]}', "posts[0]"),
    (
        "traversal",
        '{"root_placeholder": "${{{ROOT}}}", "posts": [{"path": "../secret.txt"}]}',
        "steps outside",
    ),
]


@pytest.mark.parametrize("what, text, names", BREAKAGES, ids=[b[0] for b in BREAKAGES])
def test_an_untrustworthy_manifest_is_503_naming_the_file(
    family: Flask,
    blog_export: Path,
    caplog: pytest.LogCaptureFixture,
    what: str,
    text: str | None,
    names: str,
) -> None:
    """The whole blog is unavailable rather than partly served, the log names
    the file and the reason, and /healthz reports it without failing the site."""
    manifest = blog_export / "manifest.json"
    if text is None:
        manifest.unlink()
    else:
        manifest.write_text(text)
    client = family.test_client()
    with caplog.at_level(logging.ERROR, logger="podpack_pages.blog"):
        assert client.get("/blog/").status_code == 503
        assert client.get(f"/blog/{SAMPLE}").status_code == 503
    assert str(manifest) in caplog.text
    assert names in caplog.text
    health = client.get("/healthz")
    assert health.status_code == 200
    assert health.get_json()["apps"]["blog"]["status"] == "unhealthy"


def test_status_reports_the_content_each_app_holds_to_an_operator(site: SiteFactory) -> None:
    app = site(host_config=ALL_CONFIG, admin=lambda: True)
    apps = app.test_client().get("/_status").get_json()["apps"]
    assert apps["blog"]["reported"]["manifest"] == {"generated_at": "2026-09-05T00:00:00", "posts": 1}
    assert apps["blog"]["reported"]["export"].endswith("/blog/export")
    assert apps["pybooks"]["reported"] == {"md-pages": 0, "html-pages": 1}
    assert apps["pages"]["reported"] == {"md-pages": 4, "html-pages": 5}


def test_the_manifest_is_read_on_every_request(family: Flask, blog_export: Path) -> None:
    """What lets a copied export be live with no restart: nothing is cached."""
    client = family.test_client()
    assert ">Renamed<" not in client.get("/blog/").get_data(as_text=True)
    write_manifest(blog_export, [{"path": SAMPLE, "title": "Renamed"}])
    assert ">Renamed<" in client.get("/blog/").get_data(as_text=True)


def test_a_stray_placeholder_in_a_post_is_loud(family: Flask, blog_export: Path) -> None:
    """A placeholder the contract does not define cannot be guessed at: the
    request fails with the post's path in the error, and only that post."""
    write_manifest(blog_export, [{"path": "posts/2020/01/bad.html"}, {"path": SAMPLE}])
    write_post(blog_export, "posts/2020/01/bad.html", "x ${{{NOPE}}}")
    family.config["PROPAGATE_EXCEPTIONS"] = True
    client = family.test_client()
    with pytest.raises(RuntimeError, match=r"posts/2020/01/bad\.html.*NOPE"):
        client.get("/blog/posts/2020/01/bad.html")
    assert client.get(f"/blog/{SAMPLE}").status_code == 200


def test_the_bare_address_redirects_to_its_slash_form(family: Flask) -> None:
    response = family.test_client().get("/blog")
    assert response.status_code == 308
    assert response.headers["Location"].endswith("/blog/")


def test_a_traversal_cannot_escape_the_export_tree(family: Flask, tmp_path: Path) -> None:
    (tmp_path / "secret.txt").write_text("secret")
    client = family.test_client()
    for probe in (
        "/blog/..%2f..%2fsecret.txt",
        "/blog/posts/..%2f..%2f..%2fsecret.txt",
        "/blog/images/..%2f..%2f..%2fsecret.txt",
    ):
        response = client.get(probe)
        assert response.status_code == 404
        assert b"secret" not in response.data


def test_records_land_in_the_blogs_own_log(family: Flask, blog_export: Path) -> None:
    write_manifest(blog_export, [{"path": "posts/2020/01/gone.html"}])
    family.test_client().get("/blog/posts/2020/01/gone.html")
    logs = family.extensions["podpack"].log_root
    assert "gone.html" in (logs / "blog" / "blog.log").read_text()
    assert "gone.html" not in (logs / "pybooks" / "pybooks.log").read_text()
