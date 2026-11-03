import asyncio
import json
import uuid
from typing import Dict, Set, Optional, Any
from datetime import datetime
from fastapi import WebSocket

from server.models import (
    WSMessageType, WSState, WSStateMessage,
    WSTranscriptionMessage, WSLLMTokenMessage, WSLLMCompleteMessage,
    WSTTSChunkMessage, WSTTSCompleteMessage, WSCorrectionsMessage,
    WSVocabularyMessage, WSSessionStartMessage, WSSessionEndMessage,
    WSTurnStartMessage, WSTurnEndMessage, WSErrorMessage,
    WSPingMessage, WSPongMessage
)


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.connection_metadata: Dict[str, dict] = {}

    async def connect(self, websocket: WebSocket, client_id: str = None) -> str:
        await websocket.accept()
        if client_id is None:
            client_id = str(uuid.uuid4())[:8]
        self.active_connections[client_id] = websocket
        self.connection_metadata[client_id] = {
            "connected_at": datetime.now().isoformat(),
            "session_id": None,
            "turn": 0
        }
        print(f"🔌 Cliente conectado: {client_id}")
        return client_id

    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        if client_id in self.connection_metadata:
            del self.connection_metadata[client_id]
        print(f"🔌 Cliente desconectado: {client_id}")

    async def send_json(self, client_id: str, message: dict):
        if client_id in self.active_connections:
            try:
                await self.active_connections[client_id].send_json(message)
            except Exception as e:
                print(f"Error enviando a {client_id}: {e}")
                self.disconnect(client_id)

    async def send_message(self, client_id: str, message: Any):
        if client_id in self.active_connections:
            try:
                if hasattr(message, 'model_dump'):
                    data = message.model_dump(mode='json')
                else:
                    data = message
                await self.active_connections[client_id].send_json(data)
            except Exception as e:
                print(f"Error enviando a {client_id}: {e}")
                self.disconnect(client_id)

    async def broadcast(self, message: dict, exclude: Optional[str] = None):
        for client_id, ws in self.active_connections.items():
            if client_id != exclude:
                try:
                    await ws.send_json(message)
                except:
                    pass

    def get_active_count(self) -> int:
        return len(self.active_connections)


class SessionManager:
    def __init__(self):
        self.sessions: Dict[str, dict] = {}

    def create_session(self, client_id: str, level: str = "B1", unit: str = "B1-u1") -> str:
        session_id = str(uuid.uuid4())
        self.sessions[session_id] = {
            "session_id": session_id,
            "client_id": None,
            "level": "B1",
            "unit": "B1-u1",
            "turn": 0,
            "started_at": datetime.now().isoformat(),
            "turns_data": [],
            "active": True
        }
        return session_id

    def get_session(self, session_id: str) -> Optional[dict]:
        return self.sessions.get(session_id)

    def end_session(self, session_id: str) -> Optional[dict]:
        if session_id in self.sessions:
            session = self.sessions[session_id]
            session["active"] = False
            session["ended_at"] = datetime.now().isoformat()
            return session
        return None


# Instancias globales
connection_manager = None
session_manager = None

def init_managers():
    global connection_manager, session_manager
    connection_manager = ConnectionManager()
    session_manager = SessionManager()


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.connection_metadata: Dict[str, dict] = {}

    async def connect(self, websocket: WebSocket, client_id: str = None) -> str:
        await websocket.accept()
        if client_id is None:
            client_id = str(uuid.uuid4())[:8]
        self.active_connections[client_id] = websocket
        self.connection_metadata[client_id] = {
            "connected_at": datetime.now().isoformat(),
            "session_id": None,
            "turn": 0
        }
        print(f"🔌 Cliente conectado: {client_id}")
        return client_id

    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        if client_id in self.connection_metadata:
            del self.connection_metadata[client_id]
        print(f"🔌 Cliente desconectado: {client_id}")

    async def send_json(self, client_id: str, message: dict):
        if client_id in self.active_connections:
            try:
                await self.active_connections[client_id].send_json(message)
            except Exception as e:
                print(f"Error enviando a {client_id}: {e}")
                self.disconnect(client_id)

    async def send_message(self, client_id: str, message: Any):
        if client_id in self.active_connections:
            try:
                if hasattr(message, 'model_dump'):
                    data = message.model_dump(mode='json')
                else:
                    data = message
                await self.active_connections[client_id].send_json(data)
            except Exception as e:
                print(f"Error enviando a {client_id}: {e}")
                self.disconnect(client_id)

    async def broadcast(self, message: dict, exclude: Optional[str] = None):
        for client_id, ws in self.active_connections.items():
            if client_id != exclude:
                try:
                    await ws.send_json(message)
                except:
                    pass

    def get_active_count(self) -> int:
        return len(self.active_connections)


class SessionManager:
    def __init__(self):
        self.sessions: Dict[str, dict] = {}

    def create_session(self, client_id: str, level: str = "B1", unit: str = "B1-u1") -> str:
        session_id = str(uuid.uuid4())
        self.sessions[session_id] = {
            "session_id": session_id,
            "client_id": None,
            "level": "B1",
            "unit": "B1-u1",
            "turn": 0,
            "started_at": datetime.now().isoformat(),
            "turns_data": [],
            "active": True
        }
        return session_id

    def get_session(self, session_id: str) -> Optional[dict]:
        return self.sessions.get(session_id)

    def end_session(self, session_id: str) -> Optional[dict]:
        if session_id in self.sessions:
            session = self.sessions[session_id]
            session["active"] = False
            session["ended_at"] = datetime.now().isoformat()
            return session
        return None


# Instancias globales
connection_manager = None
session_manager = None

def init_managers():
    global connection_manager, session_manager
    connection_manager = ConnectionManager()
    session_manager = SessionManager()