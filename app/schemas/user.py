from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    """Schema for creating a new user."""
    username: str = Field(..., min_length=3, max_length=50)
    firebase_uid: str = Field(..., min_length=1, max_length=255)
    email: EmailStr


class UserLogin(BaseModel):
    """Schema for user login."""
    username: str


class UserResponse(BaseModel):
    """Schema for user responses."""
    id: int
    username: str
    email: str
    is_active: bool
    is_online: bool
    created_at: datetime
    last_seen: datetime
    
    class Config:
        from_attributes = True

class UserUpdate(BaseModel):
    """Schema for updating a user."""
    username: str


class Token(BaseModel):
    """Schema for JWT token response."""
    access_token: str
    token_type: str = "bearer"

class InvitationCreate(BaseModel):
    """Schema for creating an invitation."""
    email: EmailStr
    room_id: int

class InvitationResponse(BaseModel):
    """Schema for invitation responses."""
    id: int
    sender_id: int
    sender_username: str
    receiver_id: int
    receiver_username: str
    created_at: datetime
    room_id: int
    room_name: str
    
    class Config:
        from_attributes = True

class InvitationAnswerResponse(BaseModel):
    """Schema for invitation deletion responses."""
    message: str
    
    class Config:
        from_attributes = True

class InvitationAccept(BaseModel):
    """Schema for accepting an invitation."""
    invitation_id: int
    room_id: int