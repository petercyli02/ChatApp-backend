from app.models.user import Invitation
from app.schemas import WebSocketMessage
from app.services import AuthService
from app.websockets import manager
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload


class UserService:
    """
    Service class for user operations.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.auth_service = AuthService(db)

    async def update_user(self, user_id: int, username: str) -> None:
        """Update user's online status."""
        user = await self.auth_service.get_user_by_id(user_id)
        if user:
            user.username = username
            await self.db.commit()

    async def invite_user(self, user_id: int, email: str, room_id: int) -> None:
        """Invite a user to a room."""
        sender = await self.auth_service.get_user_by_id(user_id)
        receiver = await self.auth_service.get_user_by_email(email)
        if sender and receiver:
            invitation = Invitation(
                sender_id=sender.id, receiver_id=receiver.id, room_id=room_id
            )
            self.db.add(invitation)
            await self.db.commit()
        payload = {
            "invitation_id": invitation.id,
            "sender_id": sender.id,
            "sender_username": sender.username,
            "receiver_id": receiver.id,
            "receiver_username": receiver.username,
            "room_id": room_id,
        }
        await manager.send_to_user(receiver.id, WebSocketMessage(type="invite.created", payload=payload))
        await manager.send_to_user(sender.id, WebSocketMessage(type="invite.created", payload=payload))

    async def get_received_invitations(self, user_id: int) -> list[Invitation]:
        """Get the current user's received invitations."""
        invitations = await self.db.execute(
            select(Invitation).options(
                selectinload(Invitation.sender),
                selectinload(Invitation.receiver),
                selectinload(Invitation.room),
            ).where(Invitation.receiver_id == user_id)
        )
        return invitations.scalars().all()

    async def get_sent_invitations(self, user_id: int) -> list[Invitation]:
        """Get the current user's sent invitations."""
        invitations = await self.db.execute(
            select(Invitation).options(
                selectinload(Invitation.sender),
                selectinload(Invitation.receiver),
                selectinload(Invitation.room),
            ).where(Invitation.sender_id == user_id)
        )
        return invitations.scalars().all()
    
    async def delete_invitation(self, user_id: int, invitation_id: int) -> None:
        """Delete an invitation."""
        invitation = await self.db.execute(
            select(Invitation).where(Invitation.id == invitation_id)
        )
        invitation = invitation.scalar_one_or_none()
        await self.db.delete(invitation)
        await self.db.commit()
        payload = {
            "invitation_id": invitation.id,
            "sender_id": invitation.sender_id,
            "sender_username": invitation.sender.username,
            "receiver_id": invitation.receiver_id,
            "receiver_username": invitation.receiver.username,
            "room_id": invitation.room_id,
        }
        await manager.send_to_user(invitation.receiver_id, WebSocketMessage(type="invite.deleted", payload=payload))
        await manager.send_to_user(invitation.sender_id, WebSocketMessage(type="invite.deleted", payload=payload))