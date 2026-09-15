from datetime import datetime, timezone
from app.schemas import WebSocketMessage
from app.websockets.manager import manager
from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.message import Message, Room, message_hides
from app.models.user import User
from app.schemas.message import MessageCreate, RoomCreate


class ChatService:
    """
    Service class for chat operations.

    Handles rooms and messages with async database operations.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # ==================== Room Operations ====================

    async def create_room(self, room_data: RoomCreate, creator_id: int) -> Room:
        """Create a new chat room."""
        creator = await self.db.get(User, creator_id)
        if not creator:
            return
        room = Room(
            name=room_data.name,
            description=room_data.description,
            created_by_id=creator_id,
            admin_ids=[creator_id],
            members=[creator],
        )

        self.db.add(room)
        await self.db.commit()
        await self.db.refresh(room)

        return room

    async def get_room(self, room_id: int) -> Room | None:
        """Get a room by ID with members eagerly loaded."""
        result = await self.db.execute(
            select(Room)
            .options(selectinload(Room.members))  # Eagerly load members
            .where(Room.id == room_id)
        )
        return result.scalar_one_or_none()

    async def get_all_rooms(self) -> list[Room]:
        """Get all public rooms with members eagerly loaded."""
        result = await self.db.execute(
            select(Room)
            .options(selectinload(Room.members))  # Eagerly load members
            .order_by(Room.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_all_rooms_for_user(self, user_id: int) -> list[Room]:
        """Get all rooms that a user is a member of."""
        print("get_all_rooms_for_user called with user_id:", user_id)
        result = await self.db.execute(
            select(Room)
            .options(selectinload(Room.members))  # Eagerly load members
            .join(Room.members)
            .where(User.id == user_id)
            .order_by(Room.created_at.desc())
        )
        return list(result.scalars().all())
    
    async def add_member_to_room_by_id(self, room_id: int, user_id: int) -> bool:
        """Add a user to a room."""
        print(f"add_member_to_room called: room_id={room_id}, user_id={user_id}")

        # Get room with members eagerly loaded
        result = await self.db.execute(
            select(Room).options(selectinload(Room.members)).where(Room.id == room_id)
        )
        room = result.scalar_one_or_none()
        print(f"Found room: {room}")

        user = await self.db.get(User, user_id)
        print(f"Found user: {user}")

        if not room or not user:
            print("Room or user not found!")
            return False

        print(f"Current members: {room.members}")
        if user not in room.members:
            room.members.append(user)
            await self.db.commit()
            print(f"Added user to room, new members: {room.members}")
        else:
            print("User already in room")
        
        payload = {
            "user_id": user.id,
            "user_username": user.username,
            "room_id": room.id,
            "room_name": room.name,
        }
        await manager.notify_room_members(room.id, WebSocketMessage(type="room.member_added", payload=payload))

        return True

    async def add_admin_to_room_by_id(self, room_id: int, user_id: int) -> bool:
        """Add a user to the admins of a room."""
        print(f"add_admin_to_room called: room_id={room_id}, user_id={user_id}")

        # Get room with members eagerly loaded
        result = await self.db.execute(
            select(Room).options(selectinload(Room.members)).where(Room.id == room_id)
        )
        room = result.scalar_one_or_none()
        print(f"Found room: {room}")

        user = await self.db.get(User, user_id)
        print(f"Found user: {user}")

        if not room or not user:
            print("Room or user not found!")
            return False
        
        if user_id not in room.admin_ids:
            room.admin_ids = [*(room.admin_ids or []), user_id]
            print(f"Added user to admins, new admins: {room.admin_ids}")
        else:
            print("User already in admins")
        await self.db.commit()
        payload = {
            "user_id": user.id,
            "user_username": user.username,
            "room_id": room.id,
            "room_name": room.name,
            "admin_ids": room.admin_ids,
        }
        await manager.notify_room_members(room.id, WebSocketMessage(type="room.admin_added", payload=payload))
        return True

    async def remove_admin_from_room_by_id(self, room_id: int, user_id: int) -> bool:
        """Remove a user from the admins of a room."""
        print(f"remove_admin_from_room called: room_id={room_id}, user_id={user_id}")

        # Get room with members eagerly loaded
        result = await self.db.execute(
            select(Room).options(selectinload(Room.members)).where(Room.id == room_id)
        )
        room = result.scalar_one_or_none()
        print(f"Found room: {room}")

        user = await self.db.get(User, user_id)
        print(f"Found user: {user}")

        if not room or not user:
            print("Room or user not found!")
            return False

        if user_id in room.admin_ids:
            room.admin_ids = [admin_id for admin_id in room.admin_ids if admin_id != user_id]
            print(f"Removed user from admins, new admins: {room.admin_ids}")
        else:
            print("User not in admins")
        await self.db.commit()
        return True

    async def add_member_to_room_by_email(self, room_id: int, email: str) -> bool:
        """Add a user to a room."""
        print(f"add_member_to_room called: room_id={room_id}, email={email}")

        # Get room with members eagerly loaded
        result = await self.db.execute(
            select(Room).options(selectinload(Room.members)).where(Room.id == room_id)
        )
        room = result.scalar_one_or_none()
        print(f"Found room: {room}")

        user_result = await self.db.execute(select(User).where(User.email == email))
        user = user_result.scalar_one_or_none()
        print(f"Found user: {user}")

        if not room or not user:
            print("Room or user not found!")
            return False

        print(f"Current members: {room.members}")
        if user not in room.members:
            room.members.append(user)
            await self.db.commit()
            print(f"Added user to room, new members: {room.members}")
        else:
            print("User already in room")

        return True

    async def remove_member_from_room(self, room_id: int, user_id: int) -> bool:
        """Remove a user from a room."""
        print(f"remove_member_from_room called: room_id={room_id}, user_id={user_id}")

        # Get room with members eagerly loaded
        result = await self.db.execute(
            select(Room).options(selectinload(Room.members)).where(Room.id == room_id)
        )
        room = result.scalar_one_or_none()
        print(f"Found room: {room}")

        user = await self.db.get(User, user_id)
        print(f"Found user: {user}")

        if not room or not user:
            print("Room or user not found!")
            return False
        
        if user_id in room.admin_ids:
            await self.remove_admin_from_room_by_id(room_id, user_id)
            print(f"Removed user from admins, new admins: {room.admin_ids}")

        print(f"Current members: {room.members}")
        if user in room.members:
            room.members.remove(user)
            if not room.members:
                await self.db.delete(room)
            await self.db.commit()
            print(f"Removed user from room, new members: {room.members}")
        else:
            print("User not in room")

        payload = {
            "user_id": user.id,
            "user_username": user.username,
            "room_id": room.id,
            "room_name": room.name,
        }
        await manager.notify_room_members(room.id, WebSocketMessage(type="room.member_removed", payload=payload))

        return True

    # ==================== Message Operations ====================

    async def create_message(
        self,
        message_data: MessageCreate,
        sender_id: int,
        created_at: str | None = None,
    ) -> Message:
        """
        Create a new message.

        This is called when a WebSocket message is received and needs
        to be persisted to the database.
        """
        message = Message(
            content=message_data.content,
            sender_id=sender_id,
            room_id=message_data.room_id,
            created_at=created_at or datetime.now(timezone.utc).isoformat(),
        )

        self.db.add(message)
        await self.db.commit()
        await self.db.refresh(message)

        return message
    
    async def edit_message(self, message_id: int, content: str, user_id: int) -> Message:
        """Edit a message. Only the sender may edit."""
        message = await self.get_message(message_id)
        if not message:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
        if message.sender_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only edit your own messages")
        message.content = content
        message.last_edited_at = datetime.now(timezone.utc).isoformat()
        await self.db.commit()
        await self.db.refresh(message)
        return message

    async def delete_message(self, message_id: int, user_id: int) -> None:
        """Permanently delete a message. Only the sender may delete."""
        message = await self.get_message(message_id)
        if not message:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
        if message.sender_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only delete your own messages")
        await self.db.delete(message)
        await self.db.commit()

    async def hide_message(self, message_id: int, user_id: int) -> None:
        """Hide a message for this user only."""
        message = await self.get_message(message_id)
        if not message:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
        stmt = (
            insert(message_hides)
            .values(user_id=user_id, message_id=message_id)
            .on_conflict_do_nothing()
        )
        await self.db.execute(stmt)
        await self.db.commit()

    async def unhide_message(self, message_id: int, user_id: int) -> None:
        """Restore a message this user previously hid."""
        await self.db.execute(
            delete(message_hides).where(
                message_hides.c.user_id == user_id,
                message_hides.c.message_id == message_id,
            )
        )
        await self.db.commit()

    async def get_hidden_message_ids(self, user_id: int) -> set[int]:
        result = await self.db.execute(
            select(message_hides.c.message_id).where(
                message_hides.c.user_id == user_id
            )
        )
        return set(result.scalars().all())

    async def get_room_messages(
        self, room_id: int, user_id: int, limit: int = 50, offset: int = 0
    ) -> list[Message]:
        """
        Get messages for a room with pagination.

        Returns messages in reverse chronological order (newest first).
        Uses selectinload for eager loading of sender relationship.
        Hidden messages stay in the list so the client can show a placeholder.
        """
        result = await self.db.execute(
            select(Message)
            .options(selectinload(Message.sender))
            .where(Message.room_id == room_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        messages = list(result.scalars().all())
        # Reverse to get chronological order for display
        return messages[::-1]

    async def get_message(self, message_id: int) -> Message | None:
        """Get a single message by ID."""
        result = await self.db.execute(
            select(Message)
            .options(selectinload(Message.sender))
            .where(Message.id == message_id)
        )
        return result.scalar_one_or_none()
