"""Fixtures that build a real podpack site with this distribution's apps installed.

Testing a blueprint in isolation would prove the views work and say nothing
about whether this is a well-formed app, which is the part that can break.

`HOST_CONFIG` installs the `pages` app alone, as the original suite did, so
those tests keep meaning what they meant. `ALL_CONFIG` installs the three apps
side by side -- keyed by import name in `apps` and by app name everywhere
else, the distinction podpack documents as the one most easily got wrong.
"""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from flask import Flask

from podpack import create_app

SiteFactory = Callable[..., Flask]

HOST_CONFIG: dict[str, Any] = {
    "site": {"name": "test site", "environment": "test", "apps": ["podpack_pages"]},
    "apps": {"pages": {"default_title": "A test-site note"}},
}

ALL_APPS = ["podpack_pages", "podpack_pages.pybooks", "podpack_pages.blog"]
ALL_CONFIG: dict[str, Any] = {
    "site": {"name": "test site", "environment": "test", "apps": ALL_APPS},
    "apps": {
        "pages": {"default_title": "A test-site note"},
        "pybooks": {"default_title": "A test-site course"},
        "blog": {"index_title": "A test-site blog", "default_title": "An untitled test post"},
    },
}


@pytest.fixture
def site(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> SiteFactory:
    """A podpack site with this app installed, roots pointed at tmp_path.

    Secrets come from the environment in production and `create_app` insists on
    them. The roots are real directories so the registry's per-app mkdir, data
    seeding and log wiring all run rather than being stubbed.
    """
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("SQLALCHEMY_DATABASE_URI", "sqlite:///:memory:")
    # Required since podpack 0.5.2, when login became core: podpack refuses to
    # boot without it whether or not this app uses login.
    monkeypatch.setenv("SECURITY_PASSWORD_SALT", "test-password-salt")

    def _build(**overrides: Any) -> Flask:
        config = {**HOST_CONFIG, **overrides.pop("host_config", {})}
        return create_app(
            host_config=config,
            data_root=tmp_path / "data",
            log_root=tmp_path / "logs",
            **overrides,
        )

    return _build


@pytest.fixture
def app(site: SiteFactory) -> Flask:
    return site()


@pytest.fixture
def content(app: Flask) -> Path:
    """The app's seeded content directory on the (test) host."""
    return app.extensions["podpack"].data_root / "pages"


@pytest.fixture
def family(site: SiteFactory) -> Flask:
    """A site with all three of this distribution's apps installed."""
    return site(host_config=ALL_CONFIG)


@pytest.fixture
def pybooks_content(family: Flask) -> Path:
    """The pybooks app's data directory on the (test) host, placeholder seeded."""
    return family.extensions["podpack"].data_root / "pybooks"


@pytest.fixture
def blog_export(family: Flask) -> Path:
    """The blog app's export tree on the (test) host, sample export seeded."""
    return family.extensions["podpack"].data_root / "blog" / "export"


def write_manifest(export: Path, posts: list[dict[str, Any]]) -> None:
    """A sitescraper-shaped manifest listing `posts`, each at least a `path`.

    Every field the export writes is present, so a test that reads one back
    is reading the real shape and not a convenient subset of it.
    """
    entries = [
        {
            "post_id": f"tag:test,{i}",
            "title": "",
            "original_url": None,
            "published": None,
            "updated": None,
            "categories": [],
            "comment_count": 0,
            "thumbnail_url": None,
            **post,
        }
        for i, post in enumerate(posts)
    ]
    manifest = {
        "generated_at": "2026-09-05T12:00:00",
        "root_placeholder": "${{{ROOT}}}",
        "posts": entries,
    }
    (export / "manifest.json").write_text(json.dumps(manifest, indent=2))


def write_post(export: Path, path: str, html: str) -> None:
    """A fragment at `path` inside the export tree, directories made as needed."""
    target = export / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(html)
