class APIError(Exception):
    """Custom exception class to handle error code and message from API request"""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")
