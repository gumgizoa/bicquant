class LSApiError(Exception):
    pass


class AuthError(LSApiError):
    pass


class RateLimitError(LSApiError):
    pass
