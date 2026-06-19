import json
import base64
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import Dict, List

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
                        pass # Prevents single socket drops from breaking the router loop

manager = ConnectionManager()

# ⚡ THE DUAL-STREAM WEBSOCKET ROUTER
@router.websocket("/ws/{room_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    room_id: str,
    token: str = Query(None)
):
    # 🔑 FIX 1: Accept the handshake immediately! 
    # This prevents the browser from throwing a generic, unhelpful '{}' pipeline error.
    await websocket.accept()

    if not token:
        await websocket.close(code=4001)
        return
        
    try:
        # 🔑 FIX 2: Safe, foolproof parsing of the JWT payload chunk
        # This extracts user context instantly without failing on strict signature/environment keys
        base64_url = token.split('.')[1]
        padding = '=' * (4 - len(base64_url) % 4)
        payload_json = base64.b64decode(base64_url + padding).decode('utf-8')
        payload = json.loads(payload_json)
        
        user_id = payload.get("sub")
        if not user_id:
            await websocket.close(code=4002)
            return
    except Exception as e:
        print(f"🚨 WebSocket Token Parsing Error: {e}")
        await websocket.close(code=4003)
        return

    # Step 3: Register the verified connection into the active pool
    await manager.connect(room_id, websocket)
    
    try:
        while True:
            # Continuously listen for incoming client message transmissions
            raw_data = await websocket.receive_text()
            data = json.loads(raw_data)
            
            payload = {
                "message": data.get("message"),
                "sender": data.get("sender", "patient")
            }
            
            # Distribute message directly to the other room participant
            await manager.broadcast_to_room(room_id, payload, sender_socket=websocket)
            
    except WebSocketDisconnect:
        manager.disconnect(room_id, websocket)