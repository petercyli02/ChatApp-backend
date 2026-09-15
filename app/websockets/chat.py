import asyncio
from datetime import datetime
from app.services.auth import AuthService
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Query, status

from app.database import async_session_maker
from app.schemas.message import WebSocketMessage, MessageCreate
from app.services.chat import ChatService
from app.utils.security import AccountDisabledError, AuthUnavailableError, InvalidTokenError, verify_firebase_token
from app.websockets.manager import ConnectionManager

router = APIRouter()

# This will be set from main.py to use the global manager
manager: ConnectionManager = None


def set_manager(m: ConnectionManager) -> None:
    """Set the global connection manager."""
    global manager
    manager = m


@router.websocket("/ws/{room_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    room_id: int,
    token: str = Query(...),  # JWT token passed as query param
):
    """
    WebSocket endpoint for real-time chat.
    
    ASYNC CONCEPTS DEMONSTRATED:
    
    1. Long-lived connections: Each WebSocket connection runs in its own
       coroutine that stays alive for the duration of the connection.
       
    2. Async receive loop: We await messages from the client. While waiting,
       the event loop can handle other connections.
       
    3. Concurrent handling: Many clients can be connected simultaneously,
       each in their own coroutine. The event loop switches between them.
    
    """
    await websocket.accept()

    try:
        payload = await verify_firebase_token(token)
    except AuthUnavailableError:
        await websocket.close(code=4503, reason="Auth service unavailable")
        return
    except AccountDisabledError:
        await websocket.close(code=4003, reason="Account disabled")
        return
    except InvalidTokenError:
        await websocket.close(code=4001, reason="Invalid or expired token")
        return

    firebase_uid = payload.get("uid")
    
    if not firebase_uid:
        await websocket.close(code=4001, reason="Invalid token payload")
        return

    async with async_session_maker() as session:
        auth_service = AuthService(session)
        user = await auth_service.get_user_by_firebase_uid(firebase_uid)
    
        if not user:
            await websocket.close(code=4002, reason="User not found")
            return

        user_id = user.id
        username = user.username
        print("firebase_uid/username:", firebase_uid if firebase_uid else username)
    
    # Connect to the room
    await manager.connect(websocket, room_id, user_id, username)
    
    try:
        # Main message loop - this runs for the lifetime of the connection
        while True:
            # Await incoming message (async I/O - doesn't block other connections)
            data = await websocket.receive_json()
            print("data: ", data)
            message_type = data.get("type", "message")
            message_created_at = data.get("createdAt", datetime.utcnow())

            if message_type == "message":
                content = data.get("content", "")
                
                if content.strip():
                    async with async_session_maker() as session:
                        chat_service = ChatService(session)
                        message = await chat_service.create_message(
                            MessageCreate(content=content, room_id=room_id),
                            sender_id=user_id,
                            created_at=message_created_at
                        )

                    ws_message = WebSocketMessage(
                        id=message.id,
                        type="message",
                        room_id=room_id,
                        content=content,
                        sender_id=user_id,
                        sender_username=username,
                        created_at=message_created_at,
                    )
                    print("normal message: ", ws_message)
                    
                    await manager.broadcast_to_room(room_id, ws_message)
                    
            elif message_type == "typing":
                # Typing indicator - broadcast to others (not persisted)
                ws_message = WebSocketMessage(
                    type="typing",
                    room_id=room_id,
                    sender_id=user_id,
                    sender_username=username,
                    created_at=datetime.utcnow(),
                )

                print("typing message: ", ws_message)
                
                # Exclude sender from receiving their own typing indicator
                await manager.broadcast_to_room(
                    room_id,
                    ws_message,
                    exclude_user_id=user_id
                )
    
    except WebSocketDisconnect:
        # Client disconnected (closed browser, network issue, etc.)
        manager.disconnect(websocket, room_id, user_id, username)
        
        # Notify room that user left
        leave_message = WebSocketMessage(
            type="leave",
            room_id=room_id,
            sender_id=user_id,
            sender_username=username,
            content=f"{username} left the room",
            created_at=datetime.utcnow(),
        )
        await manager.broadcast_to_room(room_id, leave_message)
        await manager.send_user_list(room_id)
    
    except Exception as e:
        # Handle unexpected errors(
        manager.disconnect(websocket, room_id, user_id, username)
        print(f"WebSocket error: {e}")



@router.websocket("/ws")
async def user_socket(websocket: WebSocket, token: str = Query(...)):
    await websocket.accept()

    try:
        payload = await verify_firebase_token(token)
    except AuthUnavailableError:
        await websocket.close(code=4503, reason="Auth service unavailable")
        return
    except AccountDisabledError:
        await websocket.close(code=4003, reason="Account disabled")
        return
    except InvalidTokenError:
        await websocket.close(code=4001, reason="Invalid or expired token")
        return

    firebase_uid = payload.get("uid")
    
    if not firebase_uid:
        await websocket.close(code=4001, reason="Invalid token payload")
        return

    async with async_session_maker() as session:
        auth_service = AuthService(session)
        user = await auth_service.get_user_by_firebase_uid(firebase_uid)
    
        if not user:
            await websocket.close(code=4002, reason="User not found")
            return

        user_id = user.id
        username = user.username
        print("firebase_uid/username:", firebase_uid if firebase_uid else username)

    await manager.connect(websocket, user_id, username)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id, username)