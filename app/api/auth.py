from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.user import UserResponse
from app.services.auth import AuthService
from app.api.deps import get_current_user

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """
    Get the current authenticated user's profile.
    
    The get_current_user dependency handles:
    1. Token extraction from Authorization header
    2. Token validation
    3. User lookup
    """
    return current_user


@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Logout the current user.
    
    Note: With JWT, there's no server-side session to invalidate.
    The client should discard the token. This endpoint is useful for:
    1. Updating online status
    2. Future: Token blacklisting with Redis
    """
    auth_service = AuthService(db)
    await auth_service.set_user_online(current_user.id, False)
    
    return {"message": "Successfully logged out"}
