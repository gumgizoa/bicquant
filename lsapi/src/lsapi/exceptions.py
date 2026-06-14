"""Exception hierarchy for the LS Securities OpenAPI client."""

from __future__ import annotations


class LSApiError(Exception):
    """Base exception / non-success response from the LS OpenAPI gateway."""

    def __init__(
        self,
        message: str,
        *,
        rsp_cd: str | None = None,
        rsp_msg: str | None = None,
        http_status: int | None = None,
        body: object | None = None,
    ) -> None:
        super().__init__(message)
        self.rsp_cd = rsp_cd
        self.rsp_msg = rsp_msg
        self.http_status = http_status
        self.body = body

    def __str__(self) -> str:
        parts = [super().__str__()]
        if self.rsp_cd:
            parts.append(f"rsp_cd={self.rsp_cd}")
        if self.http_status is not None:
            parts.append(f"http={self.http_status}")
        return " | ".join(parts)


class LSAuthError(LSApiError):
    """OAuth token acquisition or refresh failed."""


class LSSpecError(LSApiError):
    """Unknown TR code, missing block definition, or spec lookup miss."""


class LSRateLimitError(LSApiError):
    """Hit the per-second throughput quota (HTTP 429)."""


# Backwards-compatible aliases (the previous async client used these names).
AuthError = LSAuthError
RateLimitError = LSRateLimitError
