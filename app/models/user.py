from datetime import datetime
from sqlalchemy import ForeignKey, String, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    """User model for authentication and chat."""
    
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    firebase_uid: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_online: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    messages: Mapped[list["Message"]] = relationship("Message", back_populates="sender")
    sent_invitations: Mapped[list["Invitation"]] = relationship("Invitation", back_populates="sender", foreign_keys="Invitation.sender_id")
    received_invitations: Mapped[list["Invitation"]] = relationship("Invitation", back_populates="receiver", foreign_keys="Invitation.receiver_id")
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, username={self.username})>"


class Invitation(Base):
    """Invitation model for user invitations."""
    
    __tablename__ = "invitations"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    receiver_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"))

    # Relationships
    sender: Mapped["User"] = relationship("User", back_populates="sent_invitations", foreign_keys=[sender_id])
    receiver: Mapped["User"] = relationship("User", back_populates="received_invitations", foreign_keys=[receiver_id])
    room: Mapped["Room"] = relationship("Room", back_populates="invitations", foreign_keys=[room_id])

    def __repr__(self) -> str:
        return f"<Invitation(id={self.id}, sender_id={self.sender_id}, receiver_id={self.receiver_id})>"