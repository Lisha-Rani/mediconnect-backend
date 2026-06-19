import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException, status
from typing import Dict, List
from app.core.security import verify_token # Ensures your existing JWT helper is utilized

router = APIRouter(prefix="/chat", tags=["Real-Time Consultation Hub"])

# 🌐 THE IN-MEMORY SWITCHBOARD
# Tracks active sockets grouped by room/doctor ID: { room_id: [WebSocket, WebSocket] }
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, room_id: str, websocket: WebSocket):
        await websocket.accept()
        if room_id not in self.active_connections:
            self.active_connections[room_id] = []
        self.active_connections[room_id].append(websocket)

    def disconnect(self, room_id: str, websocket: WebSocket):
        if room_id in self.active_connections:
            self.active_connections[room_id].remove(websocket)
            if not self.active_connections[room_id]:
                del self.active_connections[room_id]

    async def broadcast_to_room(self, room_id: str, message: dict, sender_socket: WebSocket):
        """Sends the message payload to everyone in the room except the sender"""
        if room_id in self.active_connections:
            for connection in self.active_connections[room_id]:
                if connection != sender_socket:
                    await connection.send_text(json.dumps(message))

manager = ConnectionManager()

# ⚡ THE DUAL-STREAM WEBSOCKET ROUTER
@router.websocket("/ws/{room_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    room_id: str,
    token: str = Query(None)
):
    # 🛡️ Step 1: Secure Gate Check — Authenticate the incoming WebSocket handshake
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
        
    try:
        # Utilizing your existing system token verification routines
        user_profile = verify_token(token)
    except Exception:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # Step 2: Accept the connection into the switchboard pool
    await manager.connect(room_id, websocket)
    
    try:
        while True:
            # Listen continuously for new incoming text messages down the wire
            raw_data = await websocket.receive_text()
            data = json.loads(raw_data)
            
            # Pack the message payload with the sender's role context
            payload = {
                "message": data.get("message"),
                "sender": data.get("sender", "patient")  # 'patient' or 'doctor'
            }
            
            # Broadcast it instantly to the other participant in the room
            await manager.broadcast_to_room(room_id, payload, sender_socket=websocket)
            
    except WebSocketDisconnect:
        # Handle clean socket dropouts if a user navigates away or closes their tab
        manager.disconnect(room_id, websocket)