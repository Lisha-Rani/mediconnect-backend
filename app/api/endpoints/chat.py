import uuid
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.db.session import get_db
from app.db.models import ChatMessage

router = APIRouter(prefix="/chat", tags=["Real-Time Patient Chat"])

# --- LIVE SOCKET MANAGER ---
class ChatConnectionManager:
    def __init__(self):
        # Maps an appointment ID channel string to its active streaming socket pools
        self.active_rooms: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, room_id: str):
        await websocket.accept()
        if room_id not in self.active_rooms:
            self.active_rooms[room_id] = []
        self.active_rooms[room_id].append(websocket)

    def disconnect(self, websocket: WebSocket, room_id: str):
        if room_id in self.active_rooms:
            self.active_rooms[room_id].remove(websocket)
            if not self.active_rooms[room_id]:
                del self.active_rooms[room_id]

    async def broadcast_message(self, message: str, room_id: str):
        if room_id in self.active_rooms:
            for connection in self.active_rooms[room_id]:
                await connection.send_text(message)

manager = ChatConnectionManager()

# 1. Persistent Real-Time WebSocket Channel Connection
@router.websocket("/ws/{appointment_id}")
async def websocket_chat_endpoint(websocket: WebSocket, appointment_id: str, db: AsyncSession = Depends(get_db)):
    await manager.connect(websocket, appointment_id)
    try:
        while True:
            # Expecting incoming JSON input from the socket connection: {"sender_type": "PATIENT", "message": "Hello Doc!"}
            raw_data = await websocket.receive_text()
            data = json.loads(raw_data)
            
            # Save the text frame directly to database history log logs
            db_msg = ChatMessage(
                appointment_id=uuid.UUID(appointment_id),
                sender_type=data["sender_type"].upper(),
                message=data["message"]
            )
            db.add(db_msg)
            await db.commit()
            
            # Broadcast the live text packet instantly to the other user listening on this channel
            await manager.broadcast_message(raw_data, appointment_id)
            
    except WebSocketDisconnect:
        manager.disconnect(websocket, appointment_id)

# 2. History Retrieval Endpoint: Pulls historical records when chat re-opens
@router.get("/history/{appointment_id}")
async def get_chat_thread_history(appointment_id: str, db: AsyncSession = Depends(get_db)):
    appt_uuid = uuid.UUID(appointment_id)
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.appointment_id == appt_uuid)
        .order_by(ChatMessage.created_at.asc())
    )
    messages = result.scalars().all()
    return [
        {
            "id": m.id,
            "sender_type": m.sender_type,
            "message": m.message,
            "created_at": m.created_at
        } for m in messages
    ]