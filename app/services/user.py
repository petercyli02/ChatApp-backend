from app.errors import (
    AlreadyRoomMember,
    CannotInviteSelf,
    InvitationAlreadyExists,
    InvitationNotFound,
    NotRoomMember,
    UserNotFound,
    UsernameTaken,
)
from app.models.user import Invitation, User
from app.schemas import WebSocketMessage
from app.services import AuthService
from app.services.chat import ChatService
from app.websockets.manager import manager
from sqlalchemy import exists, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload


class UserService:
    """
    Service class for user operations.

    Failures are raised as app errors (app/errors.py). Nothing here knows about
    HTTP: the handlers in app/api/error_handlers.py pick the status code.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.auth_service = AuthService(db)
        self.chat_service = ChatService(self.db)

    async def update_user(self, user: User, username: str) -> None:
        """Change a user's username."""
        user.username = username
        try:
            await self.db.commit()
        except IntegrityError as exc:
            # usernames are UNIQUE in the database. Letting the database decide
            # is race-free, unlike checking first and then writing.
            await self.db.rollback()
            raise UsernameTaken(username=username) from exc

    # ==================== Invitations ====================

    async def invite_user(self, sender: User, email: str, room_id: int) -> Invitation:
        """
        Invite the user with `email` to a room.

        Checks run from broadest to narrowest: does the room exist, may the
        sender invite to it, does the receiver exist, and is the invite valid.
        """
        room = await self.chat_service.require_room(room_id)
        if sender not in room.members:
            raise NotRoomMember()

        receiver = await self.auth_service.get_user_by_email(email)
        if receiver is None:
            raise UserNotFound(email=email)
        if receiver.id == sender.id:
            raise CannotInviteSelf()
        if receiver in room.members:
            raise AlreadyRoomMember(f"{receiver.username} is already in this room.")
        if await self._invitation_exists(receiver.id, room_id):
            raise InvitationAlreadyExists(
                f"{receiver.username} has already been invited to this room."
            )

        # Passing the related objects (not just ids) means invitation.sender,
        # .receiver and .room are populated without another query.
        invitation = Invitation(sender=sender, receiver=receiver, room=room)
        self.db.add(invitation)
        await self.db.commit()

        await self._notify_both(invitation, "invite.created")
        return invitation

    async def accept_invitation(self, user: User, invitation_id: int) -> None:
        """Join the room an invitation is for, then remove the invitation."""
        invitation = await self._get_invitation(invitation_id)
        # Someone else's invitation is reported as "not found" rather than
        # "forbidden", so ids can't be probed to learn which invitations exist.
        if invitation is None or invitation.receiver_id != user.id:
            raise InvitationNotFound()

        await self.chat_service.add_member_to_room_by_id(invitation.room_id, user.id)
        await self._delete(invitation)

    async def delete_invitation(self, user: User, invitation_id: int) -> None:
        """Withdraw (as sender) or reject (as receiver) an invitation."""
        invitation = await self._get_invitation(invitation_id)
        if invitation is None or user.id not in (
            invitation.sender_id,
            invitation.receiver_id,
        ):
            raise InvitationNotFound()

        await self._delete(invitation)

    async def get_received_invitations(self, user_id: int) -> list[Invitation]:
        """Get the current user's received invitations."""
        invitations = await self.db.execute(
            self._invitation_query().where(Invitation.receiver_id == user_id)
        )
        return list(invitations.scalars().all())

    async def get_sent_invitations(self, user_id: int) -> list[Invitation]:
        """Get the current user's sent invitations."""
        invitations = await self.db.execute(
            self._invitation_query().where(Invitation.sender_id == user_id)
        )
        return list(invitations.scalars().all())

    # ==================== Helpers ====================

    @staticmethod
    def _invitation_query():
        return select(Invitation).options(
            selectinload(Invitation.sender),
            selectinload(Invitation.receiver),
            selectinload(Invitation.room),
        )

    async def _get_invitation(self, invitation_id: int) -> Invitation | None:
        result = await self.db.execute(
            self._invitation_query().where(Invitation.id == invitation_id)
        )
        return result.scalar_one_or_none()

    async def _invitation_exists(self, receiver_id: int, room_id: int) -> bool:
        return bool(
            await self.db.scalar(
                select(
                    exists().where(
                        Invitation.receiver_id == receiver_id,
                        Invitation.room_id == room_id,
                    )
                )
            )
        )

    async def _delete(self, invitation: Invitation) -> None:
        # Build the event while the row still exists, then delete and notify.
        message = self._event(invitation, "invite.deleted")
        await self.db.delete(invitation)
        await self.db.commit()
        await self._send_to_both(invitation, message)

    async def _notify_both(self, invitation: Invitation, event: str) -> None:
        """Tell sender and receiver, so both of their invitation lists update live."""
        await self._send_to_both(invitation, self._event(invitation, event))

    @staticmethod
    def _event(invitation: Invitation, event: str) -> WebSocketMessage:
        return WebSocketMessage(
            type=event,
            payload={
                "invitation_id": invitation.id,
                "sender_id": invitation.sender_id,
                "sender_username": invitation.sender.username,
                "receiver_id": invitation.receiver_id,
                "receiver_username": invitation.receiver.username,
                "room_id": invitation.room_id,
            },
        )

    @staticmethod
    async def _send_to_both(invitation: Invitation, message: WebSocketMessage) -> None:
        await manager.send_to_user(invitation.receiver_id, message)
        await manager.send_to_user(invitation.sender_id, message)
