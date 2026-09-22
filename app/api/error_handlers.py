"""
The one place where errors become HTTP responses.

Every non-2xx response from this API has the same body, whatever caused it:

    {"error": {"code": "...", "message": "...", "details": {...}}}

so the frontend needs exactly one piece of code to read errors.
"""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.errors import AppError

logger = logging.getLogger(__name__)


def error_response(
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message, "details": details or {}}},
        headers=headers,
    )


async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
    """Errors we raised on purpose. The normal case."""
    return error_response(
        exc.status_code, exc.code, exc.message, exc.details, exc.headers
    )


async def handle_validation_error(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """The request didn't match its Pydantic schema (missing field, bad email...)."""
    fields = {
        # loc looks like ("body", "email"); drop the "body"/"query" prefix.
        ".".join(str(part) for part in error["loc"][1:]) or str(error["loc"][0]): error["msg"]
        for error in exc.errors()
    }
    return error_response(
        422, "validation_error", "Some fields are invalid.", {"fields": fields}
    )


async def handle_http_exception(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """
    HTTPExceptions raised by FastAPI itself: unknown URLs (404), wrong method
    (405), or a missing Authorization header (HTTPBearer's 403).
    """
    return error_response(
        exc.status_code,
        f"http_{exc.status_code}",
        str(exc.detail),
        headers=getattr(exc, "headers", None),
    )


class UnhandledErrorMiddleware:
    """
    Turns an unexpected exception (a bug) into a JSON 500.

    Why a middleware and not `@app.exception_handler(Exception)`? Starlette
    runs a catch-all Exception handler in its outermost layer, *outside*
    CORSMiddleware, so the 500 goes out without CORS headers. The browser then
    hides the response entirely, and the frontend sees a network error instead
    of a server error. Added before CORSMiddleware in main.py, this sits inside
    it, so the 500 gets CORS headers like any other response.
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        response_started = False

        async def send_wrapper(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            logger.exception("Unhandled error on %s %s", scope["method"], scope["path"])
            if response_started:
                # Headers are already on the wire; nothing sensible left to send.
                raise
            response = error_response(
                500, "internal_error", "Something went wrong on our side. Please try again."
            )
            await response(scope, receive, send)


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, handle_app_error)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, handle_http_exception)
