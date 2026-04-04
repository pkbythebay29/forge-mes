from collections import defaultdict

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: dict[str, list[WebSocket]] = defaultdict(list)

    async def connect(self, channel: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections[channel].append(websocket)

    def disconnect(self, channel: str, websocket: WebSocket) -> None:
        if websocket in self.active_connections[channel]:
            self.active_connections[channel].remove(websocket)

    async def broadcast(self, channel: str, message: dict) -> None:
        stale: list[WebSocket] = []
        for connection in self.active_connections[channel]:
            try:
                await connection.send_json(message)
            except Exception:
                stale.append(connection)
        for connection in stale:
            self.disconnect(channel, connection)


manager = ConnectionManager()
