import json
import base64
import sys
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Dict, List

# Verified imports straight from your session and models infrastructure
from app.db.session import async_session_maker, get_db 
from app.db.models import ChatMessage

router = APIRouter(prefix="/chat", tags=["Real-Time Consultation Hub"])

# 🌐 THE IN-MEMORY SWITCHBOARD
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

# 📥 HTTP GET Route to reload past history records on mount
@router.get("/history/{room_id}")
async def get_chat_history(room_id: str, db: AsyncSession = Depends(get_db)):
    try:
        print(f"🔍 DEBUG: Fetching history logs for room channel: '{room_id}'")
        
        result = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.room_id == room_id)
            .order_by(ChatMessage.created_at.asc())
        )
        history = result.scalars().all()
        
        return [
            {
                "sender": msg.sender,
                "message": msg.message, # 💡 Matches 'msg.message' mapping in frontend history parser loop
                "text": msg.message,    # Fallback safety key mapping
                "created_at": msg.created_at.isoformat() if msg.created_at else None,
                "timestamp": msg.created_at.strftime("%I:%M %p") if msg.created_at else ""
            }
            for msg in history
        ]
    except Exception as e:
        print("\n" + "="*60)
        print(f"🚨 DATABASE HISTORY CRASH DETECTED:")
        print(f"Error Details: {str(e)}")
        print("="*60 + "\n")
        raise HTTPException(status_code=500, detail="Internal server database logs failure.")

# ⚡ THE DUAL-STREAM WEBSOCKET ROUTER WITH PERSISTENCE
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
            
            sender_role = data.get("sender", "patient")  # 'doctor' or 'patient'
            message_text = data.get("message", "")

            if not message_text.strip():
                continue

            # Save the message to Neon PostgreSQL database asynchronously
            async with async_session_maker() as db_session:
                new_msg = ChatMessage(
                    room_id=room_id,   # This is uniformly the patient's user UUID string
                    sender=sender_role,
                    message=message_text
                )
                db_session.add(new_msg)
                await db_session.commit()
            
            # Broadcast payload to other room participant
            payload = {
                "message": message_text,
                "sender": sender_role,
                "room_id": room_id
            }
            await manager.broadcast_to_room(room_id, payload, sender_socket=websocket)
            
    except WebSocketDisconnect:
        manager.disconnect(room_id, websocket)