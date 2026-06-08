class LSApiError(Exception):
    def __init__(self, message: str, *, rsp_cd: str | None = None) -> None:
        super().__init__(message)
        self.rsp_cd = rsp_cd


class AuthError(LSApiError):
    pass


class RateLimitError(LSApiError):
    pass


class LSSpecError(LSApiError):
    pass
