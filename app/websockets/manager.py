import asyncio
from datetime import datetime
from fastapi import WebSocket
from typing import Any

from app.schemas.message import WebSocketMessage


class ConnectionManager:
    """
    Manages WebSocket connections for real-time chat.
    
    KEY ASYNC CONCEPTS DEMONSTRATED:
    
    1. Concurrent connections: Multiple users connect simultaneously,
       each connection is handled by a separate coroutine.
       
    2. asyncio.gather: Broadcasting messages to many clients at once
       without waiting for each one sequentially.
       
    3. Async context managers: Proper connection lifecycle management.
    
    4. Shared state: The connections dict is shared across all coroutines.
       In production with multiple workers, you'd use Redis pub/sub.
    """
    
    def __init__(self):
        # room_id -> list of (websocket, user_id, username)
        self.active_connections: dict[int, list[tuple[WebSocket, int, str]]] = {}
        # user_id -> set of room_ids they're in
        self.user_rooms: dict[int, set[int]] = {}
        self.user_connections: dict[int, set[WebSocket]] = {}
    
    async def connect(
        self,
        websocket: WebSocket,
        room_id: int,
        user_id: int,
        username: str
    ) -> None:
        """
        Accept a WebSocket connection and add to room.
        
        This is an async operation - accept() is I/O bound.
        """        
        if room_id not in self.active_connections:
            self.active_connections[room_id] = []
        
        self.active_connections[room_id].append((websocket, user_id, username))
        
        if user_id not in self.user_rooms:
            self.user_rooms[user_id] = set()
        self.user_rooms[user_id].add(room_id)
        
        # Notify room that user joined
        await self.broadcast_to_room(
            room_id,
            WebSocketMessage(
                type="join",
                room_id=room_id,
                sender_id=user_id,
                sender_username=username,
                content=f"{username} joined the room",
                created_at=datetime.utcnow(),
            ),
            exclude_user_id=None  # Include everyone
        )
        
        # Send current user list to the new connection
        await self.send_user_list(room_id)

    def connect_user(self, websocket: WebSocket, user_id: int) -> None:
        """
        Accept a WebSocket connection and add to user.
        """
        if user_id not in self.user_connections:
            self.user_connections[user_id] = set()
        self.user_connections[user_id].add(websocket)
            
    def disconnect(self, websocket: WebSocket, room_id: int, user_id: int) -> None:
        """
        Remove a WebSocket connection from a room.
        
        Note: This is synchronous because we're just modifying in-memory data.
        The async broadcast for "leave" is called separately.
        """
        if room_id in self.active_connections:
            self.active_connections[room_id] = [
                conn for conn in self.active_connections[room_id]
                if conn[0] != websocket
            ]
            
            # Clean up empty rooms
            if not self.active_connections[room_id]:
                del self.active_connections[room_id]
        
        if user_id in self.user_rooms:
            self.user_rooms[user_id].discard(room_id)
            if not self.user_rooms[user_id]:
                del self.user_rooms[user_id]
    
    def disconnect_user(self, websocket: WebSocket, user_id: int) -> None:
        if user_id in self.user_connections:
            self.user_connections[user_id].discard(websocket)
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]
    
    async def broadcast_to_room(
        self,
        room_id: int,
        message: WebSocketMessage,
        exclude_user_id: int | None = None
    ) -> None:
        """
        Broadcast a message to all connections in a room.
        
        KEY ASYNC PATTERN: asyncio.gather
        
        Instead of:
            for conn in connections:
                await conn.send_json(...)  # Sequential, slow!
        
        We use:
            await asyncio.gather(*[conn.send_json(...) for conn in connections])
            # Parallel, fast!
        
        This sends to ALL clients concurrently rather than one at a time.
        """
        if room_id not in self.active_connections:
            return
        
        message_dict = message.model_dump(mode="json")
        
        # Build list of send coroutines
        send_tasks = []
        for websocket, user_id, username in self.active_connections[room_id]:
            if exclude_user_id is None or user_id != exclude_user_id:
                send_tasks.append(self._safe_send(websocket, message_dict))
        
        # Execute all sends concurrently
        if send_tasks:
            await asyncio.gather(*send_tasks, return_exceptions=True)

    async def notify_room_members(self, room_id: int, message: WebSocketMessage, member_ids: list[int]):
        await self.send_to_users(member_ids, message)

    async def send_to_user(self, user_id: int, message: WebSocketMessage):
        for ws in self.user_connections.get(user_id, []):
            await self._safe_send(ws, message.model_dump(mode="json"))

    async def send_to_users(self, user_ids: list[int], message: WebSocketMessage):
        await asyncio.gather(*[self.send_to_user(uid, message) for uid in user_ids])
        
    async def _safe_send(self, websocket: WebSocket, data: dict[str, Any]) -> None:
        """
        Safely send data to a WebSocket, handling connection errors.
        
        This wrapper ensures one failed send doesn't break the gather.
        """
        try:
            await websocket.send_json(data)
        except Exception:
            # Connection probably closed - will be cleaned up elsewhere
            pass
    
    async def send_personal_message(self, websocket: WebSocket, message: WebSocketMessage) -> None:
        """Send a message to a specific connection."""
        try:
            await websocket.send_json(message.model_dump(mode="json"))
        except Exception:
            pass
    
    async def send_user_list(self, room_id: int) -> None:
        """
        Send the list of online users to everyone in a room.
        
        This is called when someone joins/leaves.
        """
        if room_id not in self.active_connections:
            return
        
        usernames = [username for _, _, username in self.active_connections[room_id]]
        
        message = WebSocketMessage(
            type="user_list",
            room_id=room_id,
            users=usernames,
            created_at=datetime.utcnow(),
        )
        
        await self.broadcast_to_room(room_id, message)
    
    def get_room_usernames(self, room_id: int) -> list[str]:
        """Get list of usernames in a room."""
        if room_id not in self.active_connections:
            return []
        return [username for _, _, username in self.active_connections[room_id]]
    
    def get_room_user_ids(self, room_id: int) -> list[int]:
        """Get list of user ids in a room."""
        if room_id not in self.active_connections:
            return []
        return [user_id for _, user_id, _ in self.active_connections[room_id]]

    def is_user_online(self, user_id: int) -> bool:
        """Check if a user has any active connections."""
        return user_id in self.user_rooms and len(self.user_rooms[user_id]) > 0

manager = ConnectionManager()