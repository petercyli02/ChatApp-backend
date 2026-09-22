from fastapi import APIRouter, Depends, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.user import User
from app.models.message import Room
from app.schemas.error import error_responses
from app.schemas.message import RoomCreate, RoomResponse
from app.schemas.user import UserResponse
from app.services.chat import ChatService
from app.api.deps import get_current_user

router = APIRouter(prefix="/api/rooms", tags=["Rooms"])


@router.get("/debug")
async def debug_rooms(db: AsyncSession = Depends(get_db)):
    """Debug endpoint to see all rooms and memberships."""
    # Get all rooms
    rooms_result = await db.execute(
        select(Room).options(selectinload(Room.members))
    )
    rooms = rooms_result.scalars().all()
    
    # Get raw room_members table
    members_result = await db.execute(text("SELECT * FROM room_members"))
    raw_members = members_result.fetchall()
    
    return {
        "rooms": [
            {
                "id": r.id,
                "name": r.name,
                "created_by_id": r.created_by_id,
                "members": [{"id": m.id, "username": m.username} for m in r.members]
            }
            for r in rooms
        ],
        "room_members_table": [
            {"user_id": row[0], "room_id": row[1]} for row in raw_members
        ]
    }


@router.post("/", response_model=RoomResponse, status_code=status.HTTP_201_CREATED)
async def create_room(
    room_data: RoomCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new chat room."""
    print("Creating room:", room_data)
    print("Current user:", current_user)
    print("Database:", db)
    chat_service = ChatService(db)
    room = await chat_service.create_room(room_data, current_user.id)
    
    return RoomResponse(
        id=room.id,
        name=room.name,
        description=room.description,
        created_at=room.created_at,
        created_by_id=room.created_by_id,
        member_count=1
    )


@router.get("/", response_model=list[RoomResponse])
async def get_rooms_for_user(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all rooms for a user."""
    print("Getting rooms for user:", current_user)
    print("Database:", db)
    chat_service = ChatService(db)
    rooms = await chat_service.get_all_rooms_for_user(current_user.id)
    print("Rooms:", rooms)
    return [
        RoomResponse(
            id=room.id,
            name=room.name,
            description=room.description,
            created_at=room.created_at,
            created_by_id=room.created_by_id,
            member_count=len(room.members),
            admin_ids=room.admin_ids
        )
        for room in rooms
    ]

@router.get("/{room_id}", response_model=RoomResponse, responses=error_responses(404))
async def get_room(
    room_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific room by ID."""
    chat_service = ChatService(db)
    room = await chat_service.require_room(room_id)
    
    return RoomResponse(
        id=room.id,
        name=room.name,
        description=room.description,
        created_at=room.created_at,
        created_by_id=room.created_by_id,
        member_count=len(room.members)
    )

@router.get("/{room_id}/members", response_model=list[UserResponse], responses=error_responses(404))
async def get_room_members(
    room_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get the members of a room."""
    chat_service = ChatService(db)
    room = await chat_service.require_room(room_id)
    
    print(f"Room members: {room.members}")

    return [UserResponse(
        id=member.id,
        username=member.username,
        email=member.email,
        is_active=member.is_active,
        is_online=member.is_online,
        created_at=member.created_at,
        last_seen=member.last_seen
    ) for member in room.members]

@router.get("/{room_id}/admins", response_model=list[int], responses=error_responses(404))
async def get_room_admins(
    room_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get the admins of a room."""
    chat_service = ChatService(db)
    room = await chat_service.require_room(room_id)
    return room.admin_ids

@router.post("/{room_id}/join", responses=error_responses(404))
async def join_room(
    room_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Join a room."""
    chat_service = ChatService(db)
    
    room = await chat_service.require_room(room_id)
    
    await chat_service.add_member_to_room_by_id(room_id, current_user.id)
    
    return {"message": f"Joined room {room.name}"}

@router.post("/{room_id}/add", responses=error_responses(404))
async def add_member_to_room(
    room_id: int,
    email: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Add a member to a room."""
    chat_service = ChatService(db)
    print("#1")

    room = await chat_service.require_room(room_id)
    print("#2")
    await chat_service.add_member_to_room_by_email(room_id, email)
    print("#3")
    return {"message": f"Added member {email} to room {room.name}"}

@router.post("/{room_id}/remove/{user_id}", responses=error_responses(404))
async def remove_member_from_room(
    room_id: int,
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Remove a member from a room."""
    chat_service = ChatService(db)
    await chat_service.remove_member_from_room(room_id, user_id)
    return {"message": f"Removed member {user_id} from room {room_id}"}

@router.post("/{room_id}/leave", responses=error_responses(404))
async def leave_room(
    room_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Leave a room."""
    chat_service = ChatService(db)
    await chat_service.remove_member_from_room(room_id, current_user.id)
    return {"message": f"Left room with id{room_id}"}

@router.post("/{room_id}/add_admin/{user_id}", responses=error_responses(404))
async def add_admin_to_room(
    room_id: int,
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Add an admin to a room."""
    chat_service = ChatService(db)
    await chat_service.add_admin_to_room_by_id(room_id, user_id)
    return {"message": f"Added admin {user_id} to room {room_id}"}

@router.post("/{room_id}/remove_admin/{user_id}", responses=error_responses(404))
async def remove_admin_from_room(
    room_id: int,
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Remove an admin from a room."""
    chat_service = ChatService(db)
    await chat_service.remove_admin_from_room_by_id(room_id, user_id)