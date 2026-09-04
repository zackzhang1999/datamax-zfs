class AuthenticationFailed(Exception):
    pass


class RateLimitExceeded(Exception):
    """Raised when login rate limit is exceeded."""
    
    def __init__(self, retry_after_seconds: int = 60):
        self.retry_after_seconds = retry_after_seconds
        super().__init__(
            f"登录尝试次数过多。请在 {retry_after_seconds} 秒后重试。"
        )
