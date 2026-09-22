"""
Chat Application - FastAPI Backend

This application demonstrates async programming concepts in Python:

1. ASYNC I/O: All database operations use async SQLAlchemy
2. WEBSOCKETS: Real-time bidirectional communication
3. CONCURRENT CONNECTIONS: Multiple users handled by the event loop
4. BACKGROUND TASKS: Non-blocking operations

To run:
    uv run uvicorn app.main:app --reload

API Docs:
    http://localhost:8000/docs (Swagger UI)
    http://localhost:8000/redoc (ReDoc)
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
import firebase_admin
from firebase_admin import credentials


from app.config import get_settings
from app.database import create_tables
from app.api import auth_router, rooms_router, messages_router, user_router
from app.api.error_handlers import UnhandledErrorMiddleware, register_error_handlers
from app.websockets.chat import set_manager, router as chat_router
from app.websockets.manager import manager

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.
    
    This is an async context manager that runs:
    - Before the app starts accepting requests (startup)
    - After the app stops accepting requests (shutdown)
    
    ASYNC CONCEPT: The startup code runs async operations before
    the server starts handling requests.
    """
    # Startup
    print("Starting up...")
    
    # Create database tables (in production, use Alembic migrations)
    await create_tables()
    print("Database tables created")
    
    # Initialize Firebase Admin SDK
    cred = credentials.Certificate(os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH"))
    firebase_admin.initialize_app(cred)
    print("Firebase Admin SDK initialized")
    
    # Set the global WebSocket manager
    set_manager(manager)
    
    yield  # App runs here
    
    # Shutdown
    print("Shutting down...")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    description="A real-time chat application demonstrating async Python",
    version="0.1.0",
    lifespan=lifespan,
)

# Turns every error into the same JSON shape. See app/api/error_handlers.py.
register_error_handlers(app)

# Must be added BEFORE CORSMiddleware: the middleware added last runs first, so
# this ordering puts CORS on the outside, and even a 500 gets CORS headers.
app.add_middleware(UnhandledErrorMiddleware)

# CORS middleware - allows React frontend to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://localhost:3000",  # Alternative React port
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router)
app.include_router(rooms_router)
app.include_router(messages_router)
app.include_router(user_router)
app.include_router(chat_router)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "message": "Chat Application API",
        "docs": "/docs",
        "status": "running"
    }


@app.get("/health")
async def health():
    """Health check for load balancers / k8s."""
    return {"status": "healthy"}
