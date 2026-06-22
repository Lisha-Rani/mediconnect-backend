import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from jose import jwt, JWTError

from app.core.config import settings
from app.db.session import get_db
from app.db.models import ChatMessage, User
from app.api.dependencies import get_current_user

router = APIRouter(prefix="/chat", tags=["Real-time Chat Engine"])

# --- REAL-TIME CONNECTION MANAGER Matrix ---
class ConnectionManager:
    def __init__(self):
        # Maps room_id -> list of active WebSocket links
        self.active_rooms: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, room_id: str):
        await websocket.accept()
        if room_id not in self.active_rooms:
            self.active_rooms[room_id] = []
        self.active_rooms[room_id].append(websocket)
        print(f"🔌 WebSocket joined room: [{room_id}]. Total members: {len(self.active_rooms[room_id])}")

    def disconnect(self, websocket: WebSocket, room_id: str):
        if room_id in self.active_rooms:
            if websocket in self.active_rooms[room_id]:
                self.active_rooms[room_id].remove(websocket)
            if not self.active_rooms[room_id]:
                del self.active_rooms[room_id]
        print(f"❌ WebSocket disconnected from room: [{room_id}]")

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        await websocket.send_json(message)

    async def broadcast_to_room(self, room_id: str, message: dict):
        if room_id in self.active_rooms:
            for connection in self.active_rooms[room_id]:
                try:
                    await connection.send_json(message)
                except Exception:
                    # Catch stale closed links safely
                    pass

manager = ConnectionManager()


# 🛡️ WEB SOCKET QUERY TOKEN AUTHENTICATOR
async def get_websocket_user(token: str, db: AsyncSession) -> User:
    """Decodes security payloads pulled directly from URL parameters."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise ValueError("Missing subject code identifier")
            
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalars().first()
        if user is None:
            raise ValueError("Identity record missing")
        return user
    except (JWTError, ValueError) as e:
        print(f"🔒 WebSocket Credentials Rejected: {str(e)}")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid session token.")


# --- ENDPOINTS ---

# 1. FETCH HISTORICAL CHAT LOGS
@router.get("/history/{room_id}")
async def get_chat_history(
    room_id: str, 
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Resolves the 404 error by returning past conversations for a room."""
    try:
        result = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.room_id == room_id)
            .order_by(ChatMessage.created_at.asc())
        )
        messages = result.scalars().all()
        return [
            {
                "id": msg.id,
                "room_id": msg.room_id,
                "sender": msg.sender,
                "message": msg.message,
                "created_at": msg.created_at.isoformat() if msg.created_at else None
            }
            for msg in messages
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 2. FULL-DUPLEX WEBSOCKET ROOM GATEWAY
@router.websocket("/ws/{room_id}")
async def websocket_chat_endpoint(
    websocket: WebSocket,
    room_id: str,
    token: str | None = None,
    db: AsyncSession = Depends(get_db)
):
    """Processes message streaming through parameterized authentication tokens."""
    # Read the token parameter out of the query string if not parsed by dependencies
    if not token:
        token = websocket.query_params.get("token")

    if not token:
        print("🔒 Connection dropped: No token parameter detected in query string.")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    try:
        # Validate connection credentials securely
        user = await get_websocket_user(token, db)
    except Exception:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # Add authenticated client to room matrix
    await manager.connect(websocket, room_id)
    sender_name = "Doctor" if user.role.upper() == "DOCTOR" else "Patient"

    try:
        while True:
            # Await incoming message packets from this socket connection
            raw_data = await websocket.receive_text()
            try:
                data = json.loads(raw_data)
                text_content = data.get("message", "").strip()
            except json.JSONDecodeError:
                text_content = raw_data.strip()

            if not text_content:
                continue

            # Commit the chat message transaction log to Neon Postgres
            db_msg = ChatMessage(
                room_id=room_id,
                sender=sender_name,
                message=text_content
            )
            db.add(db_msg)
            await db.commit()

            # Broadcast message outbound payload packets to everyone connected to the room
            broadcast_payload = {
                "sender": sender_name,
                "message": text_content,
                "user_id": str(user.id)
            }
            await manager.broadcast_to_room(room_id, broadcast_payload)

    except WebSocketDisconnect:
        manager.disconnect(websocket, room_id)
    except Exception as e:
        print(f"🚨 WebSocket Room Exception Error: {e}")
        manager.disconnect(websocket, room_id)