import json
import os
import threading
import time

import requests

BASE_URL = "https://openapi.ls-sec.co.kr:8080"


class APIError(Exception):
    def __init__(self, code: str, msg: str):
        self.code = code
        self.msg = msg
        super().__init__(f"[{code}] {msg}")


class LSApiClient:
    def __init__(self):
        self.app_key = os.environ["LS_OPENAPI_APP_KEY"]
        self.app_secret = os.environ["LS_OPENAPI_APP_SECRET"]
        self.user_id = os.environ["LS_OPENAPI_USER_ID"]
        self._token: str | None = None
        self._expires_at: float = 0
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Token management
    # ------------------------------------------------------------------

    def _fetch_token(self) -> None:
        resp = requests.post(
            f"{BASE_URL}/oauth2/token",
            headers={"content-type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "client_credentials",
                "appkey": self.app_key,
                "appsecretkey": self.app_secret,
                "scope": "oob",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        self._token = data["access_token"]
        expires_in = int(data.get("expires_in", 3600))
        self._expires_at = time.time() + expires_in - 60  # 60s safety buffer

    def _get_token(self) -> str:
        with self._lock:
            if not self._token or time.time() >= self._expires_at:
                self._fetch_token()
            return self._token

    def _invalidate_token(self) -> None:
        with self._lock:
            self._token = None
            self._expires_at = 0

    # ------------------------------------------------------------------
    # API calls
    # ------------------------------------------------------------------

    def _post(self, token: str, tr_cd: str, body: dict) -> dict:
        resp = requests.post(
            f"{BASE_URL}/stock/item-search",
            headers={
                "content-type": "application/json; charset=utf-8",
                "authorization": f"Bearer {token}",
                "tr_cd": tr_cd,
                "tr_cont": "N",
                "tr_cont_key": "",
            },
            data=json.dumps(body),
        )
        resp.raise_for_status()
        result = resp.json()
        if result.get("rsp_cd") != "00000":
            raise APIError(result.get("rsp_cd", ""), result.get("rsp_msg", ""))
        return result

    def _fetch_bic_stocks(self, token: str) -> list:
        # 1. Get condition list (t1866)
        result = self._post(
            token,
            "t1866",
            {
                "t1866InBlock": {
                    "user_id": self.user_id,
                    "gb": "0",
                    "group_name": "",
                    "cont": "",
                    "cont_key": "",
                }
            },
        )
        conditions = result.get("t1866OutBlock1", [])
        bic = next((c for c in conditions if c["query_name"] == "BIC"), None)
        if not bic:
            raise ValueError("BIC condition not found in server condition list")

        # 2. Search by BIC condition (t1859)
        result = self._post(
            token,
            "t1859",
            {"t1859InBlock": {"query_index": bic["query_index"]}},
        )
        return result.get("t1859OutBlock1", [])

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def get_bic_stocks(self) -> list:
        """Return BIC screened stocks. Refreshes token once on API error."""
        for attempt in range(2):
            try:
                return self._fetch_bic_stocks(self._get_token())
            except APIError:
                if attempt == 0:
                    self._invalidate_token()
                else:
                    raise


# Singleton — shared across workers within the same process
client = LSApiClient()
