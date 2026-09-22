"""
Application errors.

Every failure the client is *expected* to see is one of these classes. Services
raise them; a single set of handlers (app/api/error_handlers.py) turns them into
HTTP responses. Nothing here imports FastAPI, so the same errors work unchanged
from HTTP routes, WebSocket handlers, background jobs and tests.

Each error carries three things:

- status_code: the HTTP status, declared once per category below.
- code:        a stable, machine-readable id. Clients branch on this, never on
               the message, so the wording can change without breaking anyone.
- message:     a human-readable default. Override it per raise when the call
               site knows something more specific.

Adding an error = adding a class here and raising it. No other layer changes.
"""

from http import HTTPStatus
from typing import Any


class AppError(Exception):
    """Base class for every error the client is allowed to see."""

    status_code: int = HTTPStatus.BAD_REQUEST
    code: str = "bad_request"
    message: str = "The request could not be completed."
    headers: dict[str, str] | None = None

    def __init__(self, message: str | None = None, **details: Any):
        self.message = message or self.message
        self.details = details
        super().__init__(self.message)


# ==================== Categories: one per HTTP status ====================


class BadRequestError(AppError):
    status_code = HTTPStatus.BAD_REQUEST
    code = "bad_request"


class UnauthorizedError(AppError):
    status_code = HTTPStatus.UNAUTHORIZED
    code = "unauthorized"
    message = "You need to sign in to do that."
    headers = {"WWW-Authenticate": "Bearer"}


class PermissionDeniedError(AppError):
    status_code = HTTPStatus.FORBIDDEN
    code = "forbidden"
    message = "You don't have permission to do that."


class NotFoundError(AppError):
    status_code = HTTPStatus.NOT_FOUND
    code = "not_found"
    message = "Not found."


class ConflictError(AppError):
    status_code = HTTPStatus.CONFLICT
    code = "conflict"
    message = "That conflicts with the current state."


class ServiceUnavailableError(AppError):
    status_code = HTTPStatus.SERVICE_UNAVAILABLE
    code = "service_unavailable"
    message = "A service we depend on is unavailable. Please try again shortly."
    headers = {"Retry-After": "5"}


# ==================== Auth ====================


class InvalidCredentials(UnauthorizedError):
    code = "invalid_credentials"
    message = "Your session has expired. Please sign in again."


class AccountDisabled(PermissionDeniedError):
    code = "account_disabled"
    message = "This account has been disabled."


class AuthUnavailable(ServiceUnavailableError):
    code = "auth_unavailable"
    message = "Sign-in is temporarily unavailable. Please try again shortly."


# ==================== Users ====================


class UserNotFound(NotFoundError):
    code = "user_not_found"
    message = "No user has that email."


class UsernameTaken(ConflictError):
    code = "username_taken"
    message = "That username is already taken."


# ==================== Rooms ====================


class RoomNotFound(NotFoundError):
    code = "room_not_found"
    message = "That room doesn't exist."


class NotRoomMember(PermissionDeniedError):
    code = "not_room_member"
    message = "You're not a member of this room."


class AlreadyRoomMember(ConflictError):
    code = "already_room_member"
    message = "That user is already in this room."


# ==================== Invitations ====================


class InvitationNotFound(NotFoundError):
    code = "invitation_not_found"
    message = "That invitation doesn't exist or has already been answered."


class InvitationAlreadyExists(ConflictError):
    code = "invitation_already_exists"
    message = "That user has already been invited to this room."


class CannotInviteSelf(BadRequestError):
    code = "cannot_invite_self"
    message = "You can't invite yourself."


# ==================== Messages ====================


class MessageNotFound(NotFoundError):
    code = "message_not_found"
    message = "That message doesn't exist."


class NotMessageSender(PermissionDeniedError):
    code = "not_message_sender"
    message = "You can only change your own messages."
