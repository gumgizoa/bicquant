class KofiaApiError(Exception):
    """FreeSIS 요청 실패 (네트워크 오류, 비정상 응답 등)."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")
