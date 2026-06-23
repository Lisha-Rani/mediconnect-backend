import json
import uuid
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
        self.active_rooms: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, room_id: str):
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
                    pass

manager = ConnectionManager()


# --- ENDPOINTS ---

# 1. FETCH HISTORICAL CHAT LOGS
@router.get("/history/{room_id}")
@router.get("/history/{room_id}/")
async def get_chat_history(
    room_id: str, 
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        clean_room_id = room_id.strip().replace("[", "").replace("]", "")
        
        result = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.room_id == clean_room_id)
            .order_by(ChatMessage.created_at.asc())
        )
        messages = result.scalars().all()
        
        return [
            {
                "id": msg.id,
                "room_id": msg.room_id,
                "sender": msg.sender,  # "Doctor" or "Patient" for stable style checks
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
    # Establish connection handshake immediately
    await websocket.accept()

    if not token:
        token = websocket.query_params.get("token")

    if not token:
        await websocket.send_json({"error": "Missing authentication token criteria."})
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise ValueError("Token missing subject payload properties.")

        # Cast string user ID to native Python UUID safely
        try:
            db_uuid = uuid.UUID(str(user_id).strip())
        except ValueError:
            raise ValueError("Token identifier format mismatch.")

        result = await db.execute(select(User).where(User.id == db_uuid))
        user = result.scalars().first()
        if user is None:
            raise ValueError("Authenticated identity profile not found.")

    except Exception as e:
        print(f"🔒 WebSocket Credentials Rejected: {str(e)}")
        await websocket.send_json({"error": f"Authentication validation failed: {str(e)}"})
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # Join the active memory matrix room pool
    await manager.connect(websocket, room_id)
    
    # Compile safe role tracking identifiers for frontend styling engines
    layout_role = "Doctor" if user.role.upper() == "DOCTOR" else "Patient"
    
    # 🔄 FIX: Dynamically generate real text display names using your schema updates
    if user.role.upper() == "DOCTOR":
        display_name = f"Dr. {user.first_name or 'Medical'} {user.last_name or 'Specialist'}".strip()
    else:
        display_name = f"{user.first_name or 'Anonymous'} {user.last_name or 'Patient'}".strip()

    try:
        while True:
            raw_data = await websocket.receive_text()
            try:
                data = json.loads(raw_data)
                text_content = data.get("message", "").strip()
            except json.JSONDecodeError:
                text_content = raw_data.strip()

            if not text_content:
                continue

            # Save historical logs using layout roles for unbroken backward mapping
            db_msg = ChatMessage(
                room_id=room_id,
                sender=layout_role,
                message=text_content
            )
            db.add(db_msg)
            await db.commit()

            # 🔄 FIX: Broadcast packet includes structural roles AND real names explicitly
            broadcast_payload = {
                "sender": layout_role,         # Keeps bubble positioning safe
                "sender_name": display_name,   # Real name text display reference
                "message": text_content,
                "user_id": str(user.id)
            }
            await manager.broadcast_to_room(room_id, broadcast_payload)

    except WebSocketDisconnect:
        if room_id in manager.active_rooms and websocket in manager.active_rooms[room_id]:
            manager.active_rooms[room_id].remove(websocket)
        print(f"❌ WebSocket disconnected from room: [{room_id}]")
    except Exception as e:
        print(f"🚨 WebSocket Room Exception Error: {e}")
        if room_id in manager.active_rooms and websocket in manager.active_rooms[room_id]:
            manager.active_rooms[room_id].remove(websocket)