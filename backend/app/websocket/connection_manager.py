"""
WebSocket Connection Manager
Manages real-time client connections and broadcasts live traffic / ANPR events.
"""
from typing import List
import logging
from fastapi import WebSocket

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket client connected. Active connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket client disconnected. Remaining: {len(self.active_connections)}")

    async def broadcast(self, data: dict):
        if not self.active_connections:
            return

        disconnected_clients = []
        for connection in self.active_connections:
            try:
                await connection.send_json(data)
            except Exception as e:
                logger.warning(f"Error sending to WebSocket client: {e}")
                disconnected_clients.append(connection)

        for dead_conn in disconnected_clients:
            self.disconnect(dead_conn)

ws_manager = ConnectionManager()
