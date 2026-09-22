from typing import Any

from pydantic import BaseModel


class ErrorBody(BaseModel):
    """What went wrong. `code` is stable; `message` is for humans."""

    code: str
    message: str
    details: dict[str, Any] = {}


class ErrorResponse(BaseModel):
    """
    The body of every non-2xx response from this API.

        {"error": {"code": "room_not_found", "message": "...", "details": {}}}
    """

    error: ErrorBody


def error_responses(*status_codes: int) -> dict[int, dict[str, Any]]:
    """
    For a route's `responses=`: documents which errors it can return, so they
    appear (with this schema) on the /docs page.
    """
    return {code: {"model": ErrorResponse} for code in status_codes}
