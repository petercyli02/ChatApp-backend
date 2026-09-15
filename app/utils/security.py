from datetime import datetime, timedelta
from typing import Any

from fastapi.concurrency import run_in_threadpool
from firebase_admin import auth

from app.config import get_settings

settings = get_settings()

class AuthError(Exception):
    """
    Base class for authentication failures.

    These are deliberately transport-agnostic. HTTP routes translate them into
    status codes; WebSocket handlers translate them into close codes. Neither
    concern belongs in the verifier itself.
    """


class InvalidTokenError(AuthError):
    """Token is malformed, expired, revoked, or fails signature verification."""


class AccountDisabledError(AuthError):
    """Token verified, but the Firebase account behind it is disabled."""


class AuthUnavailableError(AuthError):
    """Verification could not be completed. Transient - the caller may retry."""


async def verify_firebase_token(token: str) -> dict[str, Any]:
    """
    Verify a Firebase ID token and return its decoded claims.

    Raises an AuthError subclass on failure so callers can distinguish "the
    client's credentials are bad" from "we temporarily cannot check them".

    A ValueError is deliberately left uncaught: it means the Admin SDK was
    never initialised, which is our bug and should surface as a 500 rather
    than be disguised as a rejected credential.
    """
    try:
        # verify_id_token is synchronous and hits the network when its cache of
        # Google's signing certificates is cold, so it cannot run on the event loop.
        return await run_in_threadpool(auth.verify_id_token, token)
    except auth.UserDisabledError as exc:
        # Only raised when verify_id_token is called with check_revoked=True.
        raise AccountDisabledError("Firebase account is disabled") from exc
    except auth.CertificateFetchError as exc:
        raise AuthUnavailableError("Could not fetch Firebase signing keys") from exc
    except auth.InvalidIdTokenError as exc:
        # Base class of ExpiredIdTokenError and RevokedIdTokenError; all three
        # mean the same thing to a caller: get a fresh token.
        raise InvalidTokenError(str(exc)) from exc
