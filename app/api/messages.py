from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.message import (
    MessageCreate,
    MessageEditRequest,
    MessageIdRequest,
    MessageOperationResponse,
    MessageResponse,
)
from app.services.chat import ChatService
from app.api.deps import get_current_user

router = APIRouter(prefix="/api/messages", tags=["Messages"])


def _to_response(msg, sender_username: str, hidden: bool = False) -> MessageResponse:
    return MessageResponse(
        id=msg.id,
        content=msg.content,
        created_at=msg.created_at,
        last_edited=msg.last_edited_at,
        sender_id=msg.sender_id,
        sender_username=sender_username,
        room_id=msg.room_id,
        hidden=hidden,
    )


@router.get("/room/{room_id}", response_model=list[MessageResponse])
async def get_room_messages(
    room_id: int,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get messages for a room with pagination.

    This endpoint is used to:
    1. Load initial message history when joining a room
    2. Implement infinite scroll / load more
    """
    chat_service = ChatService(db)

    room = await chat_service.get_room(room_id)
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Room not found"
        )

    messages = await chat_service.get_room_messages(
        room_id, current_user.id, limit, offset
    )
    hidden_ids = await chat_service.get_hidden_message_ids(current_user.id)

    return [
        _to_response(msg, msg.sender.username, hidden=msg.id in hidden_ids)
        for msg in messages
    ]


@router.post("/", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def create_message(
    message_data: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new message (REST endpoint)."""
    chat_service = ChatService(db)

    room = await chat_service.get_room(message_data.room_id)
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Room not found"
        )

    message = await chat_service.create_message(message_data, current_user.id)

    return _to_response(message, current_user.username)


@router.post("/edit", response_model=MessageOperationResponse)
async def edit_message(
    body: MessageEditRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Edit a message. Only the original sender can edit."""
    chat_service = ChatService(db)
    await chat_service.edit_message(body.message_id, body.content, current_user.id)
    return MessageOperationResponse(success=True, detail="Message edited successfully")


@router.post("/delete", response_model=MessageOperationResponse)
async def delete_message(
    body: MessageIdRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a message. Only the original sender can delete."""
    chat_service = ChatService(db)
    await chat_service.delete_message(body.message_id, current_user.id)
    return MessageOperationResponse(success=True, detail="Message deleted successfully")


@router.post("/hide", response_model=MessageOperationResponse)
async def hide_message(
    body: MessageIdRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Hide a message for the current user only."""
    chat_service = ChatService(db)
    await chat_service.hide_message(body.message_id, current_user.id)
    return MessageOperationResponse(success=True, detail="Message hidden successfully")


@router.post("/unhide", response_model=MessageOperationResponse)
async def unhide_message(
    body: MessageIdRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Restore a message the current user previously hid."""
    chat_service = ChatService(db)
    await chat_service.unhide_message(body.message_id, current_user.id)
    return MessageOperationResponse(success=True, detail="Message unhidden successfully")
