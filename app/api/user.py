from app.database import AsyncSession, get_db
from app.schemas import WebSocketMessage
from app.services import ChatService
from app.services.user import UserService
from app.websockets import manager
from fastapi import APIRouter, Depends, status

from app.models.user import User
from app.schemas.user import (
    InvitationAccept,
    InvitationAnswerResponse,
    InvitationCreate,
    InvitationResponse,
    UserResponse,
    UserUpdate,
)
from app.api.deps import get_current_user

router = APIRouter(prefix="/api/users", tags=["User"])


@router.get(
    "/invitations/received",
    response_model=list[InvitationResponse],
    status_code=status.HTTP_200_OK,
)
async def get_received_invitations(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """
    Get the current user's invitations.
    """
    user_service = UserService(db)
    invitations = await user_service.get_received_invitations(current_user.id)
    print("received invitations:", invitations)
    return [
        InvitationResponse(
            id=invitation.id,
            sender_id=invitation.sender_id,
            sender_username=invitation.sender.username,
            receiver_id=invitation.receiver_id,
            receiver_username=invitation.receiver.username,
            created_at=invitation.created_at,
            room_id=invitation.room_id,
            room_name=invitation.room.name,
        )
        for invitation in invitations
    ]

@router.get(
    "/invitations/sent",
    response_model=list[InvitationResponse],
    status_code=status.HTTP_200_OK,
)
async def get_sent_invitations(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """
    Get the current user's invitations.
    """
    user_service = UserService(db)
    invitations = await user_service.get_sent_invitations(current_user.id)
    print("sent invitations:", invitations)
    return [
        InvitationResponse(
            id=invitation.id,
            sender_id=invitation.sender_id,
            sender_username=invitation.sender.username,
            receiver_id=invitation.receiver_id,
            receiver_username=invitation.receiver.username,
            created_at=invitation.created_at,
            room_id=invitation.room_id,
            room_name=invitation.room.name,
        )
        for invitation in invitations
    ]


@router.post("/update", response_model=UserResponse, status_code=status.HTTP_200_OK)
async def update_user(
    user_data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update the current authenticated user's profile.
    """
    user_service = UserService(db)
    await user_service.update_user(current_user.id, user_data.username)
    return current_user


@router.post("/invite", response_model=UserResponse, status_code=status.HTTP_200_OK)
async def invite_user(
    invitation_data: InvitationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Invite a user to a room.
    """
    user_service = UserService(db)
    await user_service.invite_user(
        current_user.id, invitation_data.email, invitation_data.room_id
    )
    return current_user


@router.delete(
    "/invitations/delete/{invitation_id}",
    response_model=InvitationAnswerResponse,
    status_code=status.HTTP_200_OK,
)
async def delete_invitation(
    invitation_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete an invitation.
    """
    user_service = UserService(db)
    await user_service.delete_invitation(current_user.id, invitation_id)
    return InvitationAnswerResponse(message="Invitation deleted successfully")


@router.post("/invitations/accept/", response_model=InvitationAnswerResponse, status_code=status.HTTP_200_OK)
async def accept_invitation(
    invitation_data: InvitationAccept,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Accept an invitation.
    """
    chat_service = ChatService(db)
    user_service = UserService(db)
    await chat_service.add_member_to_room_by_id(invitation_data.room_id, current_user.id)
    await user_service.delete_invitation(current_user.id, invitation_data.invitation_id)
    return InvitationAnswerResponse(message="Invitation accepted successfully")