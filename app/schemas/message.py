from datetime import datetime
from pydantic import AliasChoices, BaseModel, Field
from typing import Literal


class MessageEditRequest(BaseModel):
    message_id: int = Field(validation_alias=AliasChoices("message_id", "messageId"))
    content: str = Field(..., min_length=1, max_length=5000)


class MessageIdRequest(BaseModel):
    message_id: int = Field(validation_alias=AliasChoices("message_id", "messageId"))


class MessageCreate(BaseModel):
    """Schema for creating a new message."""

    content: str = Field(..., min_length=1, max_length=5000)
    room_id: int


class MessageOperationResponse(BaseModel):
    """Schema for editing a message response."""

    success: bool
    detail: str | None = None


class MessageResponse(BaseModel):
    """Schema for message responses."""

    id: int
    content: str
    created_at: datetime
    last_edited: str | datetime | None = None
    sender_id: int
    sender_username: str
    room_id: int
    hidden: bool = False

    class Config:
        from_attributes = True


class RoomCreate(BaseModel):
    """Schema for creating a new room."""

    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None


class RoomResponse(BaseModel):
    """Schema for room responses."""

    id: int
    name: str
    description: str | None
    created_at: datetime
    created_by_id: int
    member_count: int = 0
    admin_ids: list[int]

    class Config:
        from_attributes = True


class WebSocketMessage(BaseModel):
    """
    Schema for WebSocket messages.

    This handles all real-time events between client and server.
    """

    id: int | None = None
    type: Literal[
        "message",
        "typing",
        "join",
        "leave",
        "error",
        "user_list",
        "invite.created",
        "invite.deleted",
        "invite.accepted",
        "room.member_added",
        "room.member_removed",
        "room.admin_added",
        "room.admin_removed",
    ]
    payload: dict | None = None
    room_id: int | None = None
    content: str | None = None
    sender_id: int | None = None
    sender_username: str | None = None
    users: list[str] | None = None  # For user_list type
    created_at: datetime | None = None
