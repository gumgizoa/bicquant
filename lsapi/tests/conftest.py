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

import pytest
from dotenv import load_dotenv

from lsapi import LSClient

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
