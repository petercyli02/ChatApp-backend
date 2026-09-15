from datetime import datetime, timezone
from sqlalchemy import (
    ARRAY,
    Boolean,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    Table,
    Column,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# Many-to-many association table for room members
room_members = Table(
    "room_members",
    Base.metadata,
    Column("user_id", ForeignKey("users.id"), primary_key=True),
    Column("room_id", ForeignKey("rooms.id"), primary_key=True),
)

# Per-user hidden messages (Hide in the UI, not a global delete)
message_hides = Table(
    "message_hides",
    Base.metadata,
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "message_id",
        ForeignKey("messages.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Room(Base):
    """Chat room model."""

    __tablename__ = "rooms"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), index=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    admin_ids: Mapped[list[int]] = mapped_column(ARRAY(Integer), default=[])

    # Relationships
    messages: Mapped[list["Message"]] = relationship(
        "Message", back_populates="room", cascade="all, delete-orphan"
    )
    members: Mapped[list["User"]] = relationship("User", secondary=room_members)
    invitations: Mapped[list["Invitation"]] = relationship(
        "Invitation", back_populates="room", foreign_keys="Invitation.room_id"
    )

    def __repr__(self) -> str:
        return f"<Room(id={self.id}, name={self.name})>"


class Message(Base):
    """Chat message model."""

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        String(100), default=datetime.now(timezone.utc).isoformat(), index=True
    )
    last_edited_at: Mapped[datetime | None] = mapped_column(String(100), nullable=True)
    hidden: Mapped[bool] = mapped_column(Boolean, default=False)

    # Foreign keys
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"), index=True)

    # Relationships
    sender: Mapped["User"] = relationship("User", back_populates="messages")
    room: Mapped["Room"] = relationship("Room", back_populates="messages")

    def __repr__(self) -> str:
        return f"<WebSocketMessage(id={self.id}, sender_id={self.sender_id})>"
