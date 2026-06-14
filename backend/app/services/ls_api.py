import os

from lsapi import AsyncLSClient as LSClient
from lsapi import TRResponse
from lsapi.exceptions import LSApiError

__all__ = ["LSApiError", "TRResponse", "get_client", "get_bic_stocks"]

_client: LSClient | None = None


def get_client() -> LSClient:
    global _client
    if _client is None:
        _client = LSClient(
            app_key=os.environ["LS_OPENAPI_APP_KEY"],
            app_secret=os.environ["LS_OPENAPI_APP_SECRET"],
        )
    return _client


async def get_bic_stocks() -> list:
    """
    Retrieve a list of stocks matching the BIC screening condition.

    This function queries the LS OpenAPI for available screening conditions,
    finds the condition with the query name "BIC", and then fetches the matching stocks
    using that condition.

    Returns:
        list: A list of stocks (dicts) which match the BIC condition.
    """
    client = get_client()
    user_id = os.environ["LS_OPENAPI_USER_ID"]

    resp = await client.call(
        "t1866",
        user_id=user_id,
        gb="0",
        group_name="",
        cont="",
        cont_key="",
    )
    conditions: list = resp.body.get("t1866OutBlock1", [])
    bic = next((c for c in conditions if c.get("query_name") == "BIC"), None)
    if not bic:
        raise ValueError("BIC condition not found in server condition list")

    try:
        resp = await client.call("t1859", query_index=bic["query_index"])
    except LSApiError as e:
        if e.rsp_cd == "09000":  # 검색 결과가 없습니다 — no matching stocks
            return []
        raise
    return resp.body.get("t1859OutBlock1", [])
