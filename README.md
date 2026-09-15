# Chat Application Backend

A real-time chat application backend built with FastAPI, demonstrating **async programming** and **concurrency** in Python.

## Learning Goals

This project teaches:

1. **Async I/O** - Non-blocking database operations with async SQLAlchemy
2. **WebSockets** - Real-time bidirectional communication
3. **Concurrent connections** - Handling many users with asyncio
4. **Background tasks** - Non-blocking operations
5. **Event loop** - Understanding how Python async works

## Tech Stack

- **FastAPI** - Modern async web framework
- **SQLAlchemy (async)** - Async ORM with asyncpg driver
- **PostgreSQL** - Database
- **WebSockets** - Real-time messaging
- **JWT** - Authentication
- **Pydantic** - Data validation

## Quick Start

### 1. Start PostgreSQL

```bash
# From project root
docker-compose up -d postgres
```

### 2. Install Dependencies

```bash
cd backend
uv sync
```

### 3. Create .env file

```bash
# Copy example and edit as needed
cp .env.example .env
```

### 4. Run the Server

```bash
uv run uvicorn app.main:app --reload
```

### 5. Open API Docs

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Project Structure

```
backend/
├── app/
│   ├── main.py           # FastAPI app entry point
│   ├── config.py         # Settings from environment
│   ├── database.py       # Async SQLAlchemy setup
│   │
│   ├── models/           # SQLAlchemy models
│   │   ├── user.py       # User model
│   │   └── message.py    # Message & Room models
│   │
│   ├── schemas/          # Pydantic schemas
│   │   ├── user.py       # User request/response schemas
│   │   └── message.py    # Message/Room schemas
│   │
│   ├── api/              # REST API endpoints
│   │   ├── auth.py       # Authentication endpoints
│   │   ├── rooms.py      # Room CRUD
│   │   ├── messages.py   # Message history
│   │   └── deps.py       # Shared dependencies
│   │
│   ├── websockets/       # WebSocket handlers
│   │   ├── manager.py    # Connection manager (KEY FILE!)
│   │   └── chat.py       # Chat WebSocket endpoint
│   │
│   ├── services/         # Business logic
│   │   ├── auth.py       # Auth operations
│   │   └── chat.py       # Chat operations
│   │
│   └── utils/
│       └── security.py   # JWT & password utilities
│
├── pyproject.toml        # Dependencies (uv/pip)
└── .env                  # Environment variables
```

## Key Files to Study

### 1. `app/websockets/manager.py`
The **ConnectionManager** class demonstrates:
- Managing concurrent WebSocket connections
- `asyncio.gather()` for parallel message broadcasting
- Shared state across coroutines

### 2. `app/websockets/chat.py`
The WebSocket endpoint shows:
- Long-lived async connections
- Async receive loop
- Concurrent client handling

### 3. `app/database.py`
Async database setup:
- Async engine creation
- Async session management
- Dependency injection pattern

### 4. `app/services/auth.py`
Async service pattern:
- Async database queries
- Non-blocking I/O operations

## API Endpoints

### Authentication
- `POST /api/auth/register` - Create account
- `POST /api/auth/login` - Get JWT token
- `GET /api/auth/me` - Get current user
- `POST /api/auth/logout` - Logout

### Rooms
- `GET /api/rooms` - List all rooms
- `POST /api/rooms` - Create room
- `GET /api/rooms/{id}` - Get room
- `POST /api/rooms/{id}/join` - Join room

### Messages
- `GET /api/messages/room/{id}` - Get room history
- `POST /api/messages` - Send message (REST)

### WebSocket
- `WS /ws/{room_id}?token=JWT` - Real-time chat

## WebSocket Message Types

```typescript
{
  type: 'message' | 'typing' | 'join' | 'leave' | 'user_list',
  room_id: number,
  content?: string,
  sender_id?: number,
  sender_username?: string,
  users?: string[],  // for user_list type
  created_at: string
}
```

## Next Steps

After understanding the basics:

1. **Add message persistence** - Save WebSocket messages to DB
2. **Add Redis pub/sub** - Scale across multiple workers
3. **Add typing indicators** - Real-time typing status
4. **Add file uploads** - Learn ThreadPoolExecutor for CPU-bound work
5. **Add tests** - Async testing with pytest-asyncio
