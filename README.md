# Chat API

Async FastAPI backend for a real-time chat product. Pair with the [React client](https://github.com/petercyli02/ChatApp-frontend).

Firebase owns identity. This service owns authorization, persistence, and fan-out. HTTP is the source of truth; WebSockets are a live overlay.

## Stack

| Layer | Choice | Why |
|---|---|---|
| HTTP / WS | FastAPI + Uvicorn | Native async, typed routes, OpenAPI for free |
| ORM | SQLAlchemy 2.0 async + asyncpg | Non-blocking I/O against Postgres |
| Auth | Firebase Admin ID tokens | Same credential on REST and WebSocket; no homemade password store |
| Validation | Pydantic v2 | Request/response contracts at the boundary |
| Runtime | Python 3.12, `uv` | Fast, reproducible installs |

## What it does

- Rooms with membership, admins, and email invitations (send / list / accept / revoke)
- Message history with pagination, plus edit and delete (sender only)
- Per-user hide/unhide — a hide is not a global delete
- Live room events over WebSocket: messages, join/leave, presence, typing
- First-seen Firebase users provisioned in Postgres, race-safe under concurrent `/me`

## Architecture

```
HTTP / WS
    │
    ├─ deps.get_current_user        Bearer → Firebase verify → User
    ├─ api/                         thin routers, HTTPException only
    ├─ services/                    rooms, messages, invitations
    ├─ models/ + schemas/           SQLAlchemy ↔ Pydantic
    └─ websockets/manager.py        in-process connection map + broadcast
```

Auth failures are transport-agnostic (`InvalidTokenError`, `AccountDisabledError`, `AuthUnavailableError`). HTTP maps them to **401 / 403 / 503**. WebSockets map them to close codes **4001 / 4003 / 4503**. A Google cert-fetch blip does not look like a bad password, and the client is told not to retry 4xxx closes.

`verify_id_token` is sync and can hit the network. It runs in `run_in_threadpool` so the event loop is not blocked.

Related rows are loaded with `selectinload`. Async sessions cannot lazy-load after the await returns.

## HTTP

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/auth/me` | Upsert local user from Firebase UID |
| `POST` | `/api/auth/logout` | Clears online flag (JWTs are client-discarded) |
| `GET/POST` | `/api/rooms` | List memberships / create |
| `GET` | `/api/rooms/{id}` | Room + members |
| `POST` | `/api/rooms/{id}/join` `…/leave` `…/add` | Membership |
| `GET` | `/api/messages/room/{id}` | History, `limit`/`offset`, hide flags for caller |
| `POST` | `/api/messages/edit` `…/delete` `…/hide` `…/unhide` | Authz in the service layer |
| `POST` | `/api/users/invite` | Body: `{ email, room_id }` |
| `GET` | `/api/users/invitations/sent` `…/received` | Eager-loads sender, receiver, room |
| `POST` | `/api/users/invitations/accept/` | Join room, drop invitation |
| `DELETE` | `/api/users/invitations/delete/{id}` | Sender or receiver |

Interactive spec: `http://localhost:8000/docs`

## WebSocket

```
WS /ws/{room_id}?token=<firebase_id_token>
```

Accept first, then verify. Persistence uses a short-lived session; the socket itself stays open. Broadcast is `asyncio.gather` across the room. This process is the connection plane — multi-worker fan-out would be Redis pub/sub, not more in-memory dicts.

Application close codes (`4000–4999`) are terminal. Network drops are not.

## Run it

Needs Postgres 16 and a Firebase service-account JSON (Admin SDK). Put the following in `.env`. Default URL assumes Postgres on **5433**.

```bash
uv sync
uv run uvicorn app.main:app --reload
```

```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/chatapp
FIREBASE_SERVICE_ACCOUNT_PATH=/absolute/path/to/serviceAccount.json
SECRET_KEY=dev-only
```

Never commit the service-account file. CORS is locked to the Vite origin (`localhost:5173`).

## Layout

```
app/
  api/           routers
  services/      use-cases
  models/        tables + relationships
  schemas/       wire types
  websockets/    chat endpoint + ConnectionManager
  utils/         Firebase verifier
  database.py    async engine, session, create_all
```

## Honest limits

- Schema is `create_all` on boot — fine for this repo, not a migration story.
- Connection manager is single-process.
- Tests are declared (`pytest-asyncio`, `httpx`) but not the focus of this snapshot.
