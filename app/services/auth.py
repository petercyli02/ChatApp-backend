from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.user import UserCreate


class AuthService:
    """
    Service class for authentication operations.
    
    This demonstrates async database operations with SQLAlchemy.
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_user(self, user_data: UserCreate) -> User:
        """
        Create a new user.
        """
        
        user = User(
            firebase_uid=user_data.firebase_uid,
            username=user_data.username,
            email=user_data.email,
        )
        
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        
        return user
        
    async def get_user_by_username(self, username: str) -> User | None:
        """Get a user by their username."""
        result = await self.db.execute(
            select(User).where(User.username == username)
        )
        return result.scalar_one_or_none()
    
    async def get_user_by_email(self, email: str) -> User | None:
        """Get a user by their email."""
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()
    
    async def get_user_by_id(self, user_id: int) -> User | None:
        """Get a user by their ID."""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def get_user_by_firebase_uid(self, firebase_uid: str) -> User | None:
        """Get a user by their Firebase UID."""
        result = await self.db.execute(
            select(User).where(User.firebase_uid == firebase_uid)
        )
        return result.scalar_one_or_none()
    
    async def set_user_online(self, user_id: int, is_online: bool) -> None:
        """Update user's online status."""
        user = await self.get_user_by_id(user_id)
        if user:
            user.is_online = is_online
            await self.db.commit()
