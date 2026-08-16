"""Shared fixtures.

The recorded responses under fixtures/ were trimmed from real captures, with
the expiring URL signatures stripped. No test in this suite is allowed to touch
the network — see the `block_network` autouse fixture.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from tokopedia_scraper.config import Config  # noqa: E402
from tokopedia_scraper.storage import Storage  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def block_network(monkeypatch):
    """Make any accidental HTTP call fail loudly instead of reaching Tokopedia."""

    def forbidden(*args, **kwargs):
        raise AssertionError(
            "a test tried to make a network request; tests must run offline"
        )

    import requests

    monkeypatch.setattr(requests.Session, "request", forbidden)
    monkeypatch.setattr(requests, "get", forbidden, raising=False)
    monkeypatch.setattr(requests, "post", forbidden, raising=False)

    try:
        from curl_cffi import requests as cffi_requests
    except ImportError:
        pass
    else:
        monkeypatch.setattr(cffi_requests, "Session", forbidden, raising=False)


@pytest.fixture
def search_payload():
    return load_fixture("search_v5.json")


@pytest.fixture
def pdp_payload():
    return load_fixture("pdp_with_description.json")


@pytest.fixture
def pdp_image_only_payload():
    """A PDP whose seller uploaded the description as pictures, not text."""
    return load_fixture("pdp_image_only.json")


@pytest.fixture
def cfg(tmp_path) -> Config:
    config = Config(keywords=["alpha", "beta"])
    config.root = tmp_path
    config.storage.db_path = tmp_path / "products.db"
    config.storage.export_dir = tmp_path / "exports"
    config.images.dir = tmp_path / "images"
    config.search.max_pages_per_keyword = 5
    config.search.target_per_keyword = 0
    return config


@pytest.fixture
def storage(cfg):
    with Storage(cfg.storage.db_path) as store:
        yield store
