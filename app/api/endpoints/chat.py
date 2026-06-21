import json
import base64
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Dict, List

from app.api.dependencies import get_db # Adjust based on your DB dependency path
from app.db.session import async_session_maker # Used to generate isolated database transactions inside loops
from app.db.models import ChatMessage

router = APIRouter(prefix="/chat", tags=["Real-Time Consultation Hub"])

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, room_id: str, websocket: WebSocket):
        if room_id not in self.active_connections:
            self.active_connections[room_id] = []
        self.active_connections[room_id].append(websocket)

    def disconnect(self, room_id: str, websocket: WebSocket):
        if room_id in self.active_connections:
            self.active_connections[room_id].remove(websocket)
            if not self.active_connections[room_id]:
                del self.active_connections[room_id]

    async def broadcast_to_room(self, room_id: str, message: dict, sender_socket: WebSocket):
        if room_id in self.active_connections:
            for connection in self.active_connections[room_id]:
                if connection != sender_socket:
                    try:
                        await connection.send_text(json.dumps(message))
                    except Exception:
                        pass

manager = ConnectionManager()

# 📥 NEW: HTTP GET Route to reload past history records on mount
@router.get("/history/{room_id}")
async def get_chat_history(room_id: str, db: AsyncSession = Depends(get_db)):
    try:
        result = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.room_id == room_id)
            .order_by(ChatMessage.created_at.asc())
        )
        history = result.scalars().all()
        return [
            {
                "sender": msg.sender,
                "text": msg.message,
                "timestamp": msg.created_at.strftime("%I:%M %p") if msg.created_at else ""
            }
            for msg in history
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ⚡ WebSocket Pipeline with Auto-Persistence Engine
@router.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str, token: str = Query(None)):
    await websocket.accept()

    if not token:
        await websocket.close(code=4001)
        return
        
    try:
        base64_url = token.split('.')[1]
        padding = '=' * (4 - len(base64_url) % 4)
        payload = json.loads(base64.b64decode(base64_url + padding).decode('utf-8'))
        user_id = payload.get("sub")
        if not user_id:
            await websocket.close(code=4002)
            return
    except Exception:
        await websocket.close(code=4003)
        return

    await manager.connect(room_id, websocket)
    
    try:
        while True:
            raw_data = await websocket.receive_text()
            data = json.loads(raw_data)
            
            sender_role = data.get("sender", "patient")
            message_text = data.get("message", "")

            # 💾 PERSIST TO NEON POSTGRESQL: Commit message to database asynchronously
            async with async_session_maker() as db_session:
                new_msg = ChatMessage(
                    room_id=room_id,
                    sender=sender_role,
                    message=message_text
                )
                db_session.add(new_msg)
                await db_session.commit()
            
            # Broadcast out to other room client
            payload = {
                "message": message_text,
                "sender": sender_role
            }
            await manager.broadcast_to_room(room_id, payload, sender_socket=websocket)
            
    except WebSocketDisconnect:
        manager.disconnect(room_id, websocket)