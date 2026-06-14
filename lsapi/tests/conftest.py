"""Shared fixtures for live LS OpenAPI integration tests.

These tests hit the **real** gateway. Credentials are read from the repo ``.env``
(``LS_OPENAPI_APP_KEY`` / ``LS_OPENAPI_APP_SECRET``); each live module skips
itself when the keys are absent.

Rate limiting: a single session-scoped :class:`~lsapi.LSClient` is shared across
all synchronous tests so the client's per-TR TPS throttle (``spec.tps_limit``)
sees every call and spaces them out. Tests run sequentially (no xdist), so the
gateway's per-second quota is never exceeded.
"""

import os
import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv

# Pytest can place the project directory before src/, resolving ``lsapi`` as a
# namespace package. Force the real src package before importing test fixtures.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
if "lsapi" in sys.modules and getattr(sys.modules["lsapi"], "__file__", None) is None:
    del sys.modules["lsapi"]

from lsapi import LSClient  # noqa: E402

load_dotenv()  # repo .env when pytest is run from the project root


@pytest.fixture(scope="session")
def live_client() -> LSClient:
    """One shared sync client — its TPS throttle state spans the whole session."""
    key = os.environ.get("LS_OPENAPI_APP_KEY", "")
    secret = os.environ.get("LS_OPENAPI_APP_SECRET", "")
    if not (key and secret):
        pytest.skip("LS_OPENAPI_APP_KEY/SECRET not set in .env")
    client = LSClient(app_key=key, app_secret=secret)
    yield client
    client.close()
