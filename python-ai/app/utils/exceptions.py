"""Errors the API can explain without exposing internal details."""


class AppError(Exception):
    """A known failure with a message that is safe to return to the caller."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)
