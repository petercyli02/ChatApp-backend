from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.database import get_db
from app.errors import AccountDisabled, AuthUnavailable, InvalidCredentials
from app.models.user import User
from app.schemas import UserCreate
from app.services.auth import AuthService
from app.utils.security import (
    AccountDisabledError,
    AuthUnavailableError,
    InvalidTokenError,
    verify_firebase_token,
)

# HTTP Bearer scheme - looks for Bearer token in Authorization header
http_bearer_scheme = HTTPBearer()


async def get_current_user(
    token: HTTPAuthorizationCredentials = Depends(http_bearer_scheme), db: AsyncSession = Depends(get_db)
) -> User:
    """
    Dependency to get the current authenticated user.

    This is an async dependency that:
    1. Extracts the JWT token from the Authorization header
    2. Decodes and validates the token
    3. Fetches the user from the database

    Usage:
        @app.get("/me")
        async def get_me(user: User = Depends(get_current_user)):
            return user
    """
    # Translate the verifier's auth failures into app errors. The distinction
    # matters: 401 tells the client to re-authenticate, while 503 tells it to
    # retry, so a Firebase outage does not sign everybody out.
    try:
        payload = await verify_firebase_token(token.credentials)
    except AuthUnavailableError as exc:
        raise AuthUnavailable() from exc
    except AccountDisabledError as exc:
        raise AccountDisabled() from exc
    except InvalidTokenError as exc:
        raise InvalidCredentials() from exc

    # Fetch user from database
    auth_service = AuthService(db)
    user = await auth_service.get_user_by_firebase_uid(payload["uid"])

    if user is None:
        try:
            user = await auth_service.create_user(
                UserCreate(
                    firebase_uid=payload["uid"],
                    username=payload["email"],
                    email=payload["email"],
                )
            )
        except IntegrityError:
            # Lost a race with a concurrent request for the same new UID.
            # The row now exists, so adopt the winner's result.
            await db.rollback()
            user = await auth_service.get_user_by_firebase_uid(payload["uid"])

    if not user.is_active:
        raise AccountDisabled()

    return user
