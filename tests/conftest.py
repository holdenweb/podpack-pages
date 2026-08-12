"""Fixtures that build a real podpack site with this app installed.

Testing the blueprint in isolation would prove the views work and say nothing
about whether this is a well-formed app, which is the part that can break.
"""

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


@pytest.fixture
def site(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> SiteFactory:
    """A podpack site with this app installed, roots pointed at tmp_path.

    Secrets come from the environment in production and `create_app` insists on
    them. The roots are real directories so the registry's per-app mkdir, data
    seeding and log wiring all run rather than being stubbed.
    """
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("SQLALCHEMY_DATABASE_URI", "sqlite:///:memory:")

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
