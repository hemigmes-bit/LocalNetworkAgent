from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from contextlib import asynccontextmanager
import asyncio
import json
import uuid
from typing import Optional
import os
from datetime import datetime

# Imports de modelos y managers
from server.models import (
    WSMessageType, WSState, WSStateMessage,
    WSTranscriptionMessage, WSLLMTokenMessage, WSLLMCompleteMessage,
    WSTTSChunkMessage, WSTTSCompleteMessage, WSCorrectionsMessage,
    WSVocabularyMessage, WSSessionStartMessage, WSSessionEndMessage,
    WSTurnStartMessage, WSTurnEndMessage, WSErrorMessage,
    WSPingMessage, WSPongMessage
)
from server.websocket_manager import connection_manager, session_manager, init_managers
from server.audio_stream import AudioStreamer, MicrophoneStream

# Importar componentes de Emma
import sys
sys.path.insert(0, r"C:\Users\Usuario\LocalNetworkAgent\python\src\main\python")

from emma_core.curriculum import get_curriculum
from emma_core.profile import get_profile_manager
from emma_core.srs import SimpleSRS
from emma_core.timer import Timer
from silero_vad import load_silero_vad, VADIterator
from stt_faster_whisper import FasterWhisperSTT
from llm_openrouter import OpenRouterLLM
from tts_kokoro import KokoroTTS


# Configuración
SAMPLE_RATE = 16000
CHANNELS = 1
BLOCK_SIZE = 512
MIN_SILENCE_MS = 400
MAX_RECORDING_S = 30

# Variables globales para el pipeline
emma_pipeline = None
active_sessions = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[START] Iniciando servidor Emma Bilingüe...")
    yield
    print("[STOP] Apagando servidor...")


app = FastAPI(
    title="Emma Bilingüe - Voice Tutor API",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Modelos para REST API
from pydantic import BaseModel

class SessionCreateRequest(BaseModel):
    level: str = "B1"
    unit: Optional[str] = None

class SessionResponse(BaseModel):
    session_id: str
    level: str
    unit: str

class TurnRequest(BaseModel):
    session_id: str
    audio_base64: str


# ============================================
# REST ENDPOINTS
# ============================================

@app.get("/")
async def root():
    return {"message": "Emma Bilingüe API", "version": "1.0.0", "status": "running"}

@app.get("/health")
async def health():
    import torch
    return {
        "status": "healthy",
        "gpu": torch.cuda.is_available(),
        "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
    }

@app.post("/api/sessions", response_model=dict)
async def create_session(request: dict):
    session_id = str(uuid.uuid4())
    return {"session_id": session_id, "level": "B1", "unit": "B1-u1"}

@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    return {"session_id": session_id, "status": "active"}

@app.delete("/api/sessions/{session_id}")
async def end_session(session_id: str):
    return {"message": "Session ended", "session_id": session_id}


# ============================================
# WEBSOCKET ENDPOINT
# ============================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    client_id = await connection_manager.connect(websocket)

    welcome_msg = {
        "type": "session_start",
        "timestamp": datetime.now().isoformat(),
        "session_id": None,
        "message": "Conectado a Emma Bilingüe"
    }
    await connection_manager.send_json(client_id, welcome_msg)

    try:
        while True:
            data = await websocket.receive_json()
            await handle_ws_message(client_id, data)
    except WebSocketDisconnect:
        connection_manager.disconnect(client_id)
    except Exception as e:
        print(f"Error WebSocket: {e}")
        connection_manager.disconnect(client_id)


async def handle_ws_message(client_id: str, data: dict):
    msg_type = data.get("type")

    if msg_type == "ping":
        await connection_manager.send_json(client_id, {
            "type": "pong",
            "timestamp": datetime.now().isoformat()
        })

    elif msg_type == "start_session":
        level = data.get("level", "B1")
        unit = data.get("unit", "B1-u1")
        session_id = str(uuid.uuid4())

        await connection_manager.send_json(client_id, {
            "type": "session_start",
            "session_id": session_id,
            "level": "B1",
            "unit": "B1-u1",
            "message": "Sesión iniciada"
        })

    elif msg_type == "audio_chunk":
        pass

    elif msg_type == "text_message":
        pass

    elif msg_type == "end_session":
        await connection_manager.send_json(client_id, {
            "type": "session_end",
            "message": "Sesión finalizada"
        })

    elif msg_type == "pong":
        pass


# ============================================
# PIPELINE DE EMMA (Background Tasks)
# ============================================

class EmmaPipeline:
    def __init__(self, session_id: str, client_id: str):
        self.session_id = session_id
        self.client_id = client_id

        self.timer = Timer()
        self.vad_model = load_silero_vad(); self.vad_iterator = VADIterator(self.vad_model, threshold=0.5)
        self.stt = FasterWhisperSTT(model_size="base", device="cuda")
        self.llm = OpenRouterLLM()
        self.tts = KokoroTTS()

        self.mic_stream = MicrophoneStream()
        self.audio_streamer = AudioStreamer()

        self.messages = []
        self.turn = 0
        self.running = False

        from emma_core.curriculum import get_curriculum
        from emma_core.profile import get_profile_manager
        from emma_core.srs import SimpleSRS

        self.curriculum = get_curriculum()
        self.profile_manager = get_profile_manager()
        self.profile = get_profile_manager().get_profile()
        self.current_level = "B1"
        self.current_unit = "B1-u1"

        self.timer = Timer()
        self.vad_model = load_silero_vad(); self.vad_iterator = VADIterator(self.vad_model, threshold=0.5)
        self.stt = FasterWhisperSTT(model_size="base", device="cuda")
        self.llm = OpenRouterLLM()
        self.tts = KokoroTTS()

        self.mic_stream = MicrophoneStream()
        self.audio_streamer = AudioStreamer()

    async def start_listening(self):
        await self.mic_stream.start()

        await self.send_state("listening", "Escuchando...")

    async def process_turn(self, turn: int):
        await self.send_state("listening", "Escuchando...")

        audio = await self.record_audio()
        if len(audio) == 0:
            return False

        self.timer.mark_stt()
        user_text = self.stt.transcribe(audio, language="es")

        await self.send_transcription(user_text, is_final=True)

        await self.send_state("thinking", "Emma pensando...")

        full_response = ""
        async for token in self.llm.stream_chat(...):
            await self.send_llm_token(token)
            full_response += token

        await self.send_llm_complete(full_response)

        await self.send_state("speaking", "Emma hablando...")

        audio = self.tts.synthesize(response_text)
        async for chunk_b64 in self.audio_streamer.stream_audio_chunks(audio):
            await self.send_tts_chunk(chunk_b64)

        await self.send_tts_complete()
        await self.send_state("idle", "Listo")

        return True

    async def record_audio(self):
        self.recording = True
        self.audio_buffer = []
        self.silence_start = None
        silence_samples = int(MIN_SILENCE_MS * 16000 / 1000)
        max_samples = int(MAX_RECORDING_S * 16000)

        stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            blocksize=BLOCK_SIZE,
            callback=self.audio_callback
        )
        stream.start()

        try:
            while self.recording:
                try:
                    chunk = self.audio_queue.get(timeout=0.5)
                    self.audio_buffer.append(chunk)

                    is_speech = self.vad.is_speech(chunk.flatten())

                    if is_speech:
                        self.silence_start = None
                    else:
                        if self.silence_start is None:
                            self.silence_start = time.time()
                        elif time.time() - self.silence_start > (MIN_SILENCE_MS / 1000):
                            print("   🔇 Silencio detectado, procesando...")
                            break

                    total_samples = sum(len(c) for c in self.audio_buffer)
                    if total_samples > max_samples:
                        print("   [TIME] Tiempo máximo alcanzado")
                        break

                except queue.Empty:
                    continue

        finally:
            stream.stop()
            stream.close()

        if self.audio_buffer:
            return np.concatenate(self.audio_buffer, axis=0).flatten()
        return np.array([])

    async def send_state(self, state: str, message: str = ""):
        msg = {
            "type": "state",
            "state": state,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }
        await connection_manager.send_json(self.client_id, msg)

    async def send_transcription(self, text: str, is_final: bool):
        msg = {
            "type": "transcription_final" if is_final else "transcription_partial",
            "text": text,
            "is_final": is_final,
            "language": "es",
            "timestamp": datetime.now().isoformat()
        }
        await connection_manager.send_json(self.client_id, msg)

    async def send_llm_token(self, token: str):
        msg = {
            "type": "llm_token",
            "token": token,
            "timestamp": datetime.now().isoformat()
        }
        await connection_manager.send_json(self.client_id, msg)

    async def send_llm_complete(self, text: str):
        msg = {
            "type": "llm_complete",
            "full_text": text,
            "timestamp": datetime.now().isoformat()
        }
        await connection_manager.send_json(self.client_id, msg)

    async def send_tts_chunk(self, chunk_b64: str):
        # Calculate amplitude and vowel for lip-sync
        import base64
        import numpy as np
        
        # Decode base64 audio
        audio_bytes = base64.b64decode(chunk_b64)
        audio_array = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        
        # RMS amplitude (0-1)
        rms = np.sqrt(np.mean(audio_array**2))
        amplitude = min(1.0, rms * 10)  # Scale for visibility
        
        # Simple vowel estimation from spectral centroid
        vowel = 'a'  # default
        if len(audio_array) > 100:
            # Very simple heuristic: check energy in different freq bands
            fft = np.fft.rfft(audio_array)
            freqs = np.fft.rfftfreq(len(audio_array), 1/24000)
            magnitude = np.abs(fft)
            
            # F1/F2 regions for vowels (rough approximation)
            f1_energy = np.sum(magnitude[(freqs > 300) & (freqs < 1000)])
            f2_energy = np.sum(magnitude[(freqs > 1000) & (freqs < 3000)])
            
            if f1_energy > f2_energy * 2:
                vowel = 'a'  # low F1, low F2
            elif f2_energy > f1_energy * 2:
                vowel = 'i'  # high F2
            elif f1_energy > f2_energy:
                vowel = 'o'  # mid F1, low F2
            else:
                vowel = 'e'  # mid
        
        msg = {
            "type": "tts_chunk",
            "audio_base64": chunk_b64,
            "sample_rate": 24000,
            "format": "pcm",
            "is_final": False,
            "amplitude": float(amplitude),
            "vowel": vowel,
            "timestamp": datetime.now().isoformat()
        }
        await connection_manager.send_json(self.client_id, msg)

    async def send_tts_complete(self):
        msg = {
            "type": "tts_complete",
            "timestamp": datetime.now().isoformat()
        }
        await connection_manager.send_json(self.client_id, msg)


# ============================================
# MAIN
# ============================================

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from contextlib import asynccontextmanager
import asyncio
import json
import uuid
from typing import Optional
import os
from datetime import datetime

# Inicializar managers
init_managers()

app = FastAPI(
    title="Emma Bilingüe - Voice Tutor API",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Modelos para REST API
from pydantic import BaseModel

class SessionCreateRequest(BaseModel):
    level: str = "B1"
    unit: Optional[str] = None

class SessionResponse(BaseModel):
    session_id: str
    level: str
    unit: str

class TurnRequest(BaseModel):
    session_id: str
    audio_base64: str


# ============================================
# REST ENDPOINTS
# ============================================

@app.get("/")
async def root():
    return {"message": "Emma Bilingüe API", "version": "1.0.0", "status": "running"}

@app.get("/health")
async def health():
    import torch
    return {
        "status": "healthy",
        "gpu": torch.cuda.is_available(),
        "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
    }

@app.post("/api/sessions", response_model=dict)
async def create_session(request: dict):
    session_id = str(uuid.uuid4())
    return {"session_id": session_id, "level": "B1", "unit": "B1-u1"}

@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    return {"session_id": session_id, "status": "active"}

@app.delete("/api/sessions/{session_id}")
async def end_session(session_id: str):
    return {"message": "Session ended", "session_id": session_id}


# ============================================
# WEBSOCKET ENDPOINT
# ============================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    client_id = await connection_manager.connect(websocket)

    welcome_msg = {
        "type": "session_start",
        "timestamp": datetime.now().isoformat(),
        "session_id": None,
        "message": "Conectado a Emma Bilingüe"
    }
    await connection_manager.send_json(client_id, welcome_msg)

    try:
        while True:
            data = await websocket.receive_json()
            await handle_ws_message(client_id, data)
    except WebSocketDisconnect:
        connection_manager.disconnect(client_id)
    except Exception as e:
        print(f"Error WebSocket: {e}")
        connection_manager.disconnect(client_id)


async def handle_ws_message(client_id: str, data: dict):
    msg_type = data.get("type")

    if msg_type == "ping":
        await connection_manager.send_json(client_id, {
            "type": "pong",
            "timestamp": datetime.now().isoformat()
        })

    elif msg_type == "start_session":
        level = data.get("level", "B1")
        unit = data.get("unit", "B1-u1")
        session_id = str(uuid.uuid4())

        await connection_manager.send_json(client_id, {
            "type": "session_start",
            "session_id": session_id,
            "level": "B1",
            "unit": "B1-u1",
            "message": "Sesión iniciada"
        })

    elif msg_type == "audio_chunk":
        pass

    elif msg_type == "text_message":
        pass

    elif msg_type == "end_session":
        await connection_manager.send_json(client_id, {
            "type": "session_end",
            "message": "Sesión finalizada"
        })

    elif msg_type == "pong":
        pass


# ============================================
# PIPELINE DE EMMA (Background Tasks)
# ============================================

class EmmaPipeline:
    def __init__(self, session_id: str, client_id: str):
        self.session_id = session_id
        self.client_id = client_id

        self.timer = Timer()
        self.vad_model = load_silero_vad(); self.vad_iterator = VADIterator(self.vad_model, threshold=0.5)
        self.stt = FasterWhisperSTT(model_size="base", device="cuda")
        self.llm = OpenRouterLLM()
        self.tts = KokoroTTS()

        self.mic_stream = MicrophoneStream()
        self.audio_streamer = AudioStreamer()

        self.messages = []
        self.turn = 0
        self.running = False

        from emma_core.curriculum import get_curriculum
        from emma_core.profile import get_profile_manager
        from emma_core.srs import SimpleSRS

        self.curriculum = get_curriculum()
        self.profile_manager = get_profile_manager()
        self.profile = get_profile_manager().get_profile()
        self.current_level = "B1"
        self.current_unit = "B1-u1"

        self.timer = Timer()
        self.vad_model = load_silero_vad(); self.vad_iterator = VADIterator(self.vad_model, threshold=0.5)
        self.stt = FasterWhisperSTT(model_size="base", device="cuda")
        self.llm = OpenRouterLLM()
        self.tts = KokoroTTS()

        self.mic_stream = MicrophoneStream()
        self.audio_streamer = AudioStreamer()

    async def start_listening(self):
        await self.mic_stream.start()

        await self.send_state("listening", "Escuchando...")

    async def process_turn(self, turn: int):
        await self.send_state("listening", "Escuchando...")

        audio = await self.record_audio()
        if len(audio) == 0:
            return False

        self.timer.mark_stt()
        user_text = self.stt.transcribe(audio, language="es")

        await self.send_transcription(user_text, is_final=True)

        await self.send_state("thinking", "Emma pensando...")

        full_response = ""
        async for token in self.llm.stream_chat(...):
            await self.send_llm_token(token)
            full_response += token

        await self.send_llm_complete(full_response)

        await self.send_state("speaking", "Emma hablando...")

        audio = self.tts.synthesize(response_text)
        async for chunk_b64 in self.audio_streamer.stream_audio_chunks(audio):
            await self.send_tts_chunk(chunk_b64)

        await self.send_tts_complete()
        await self.send_state("idle", "Listo")

        return True

    async def record_audio(self):
        self.recording = True
        self.audio_buffer = []
        self.silence_start = None
        silence_samples = int(MIN_SILENCE_MS * 16000 / 1000)
        max_samples = int(MAX_RECORDING_S * 16000)

        stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            blocksize=BLOCK_SIZE,
            callback=self.audio_callback
        )
        stream.start()

        try:
            while self.recording:
                try:
                    chunk = self.audio_queue.get(timeout=0.5)
                    self.audio_buffer.append(chunk)

                    is_speech = self.vad.is_speech(chunk.flatten())

                    if is_speech:
                        self.silence_start = None
                    else:
                        if self.silence_start is None:
                            self.silence_start = time.time()
                        elif time.time() - self.silence_start > (MIN_SILENCE_MS / 1000):
                            print("   🔇 Silencio detectado, procesando...")
                            break

                    total_samples = sum(len(c) for c in self.audio_buffer)
                    if total_samples > max_samples:
                        print("   [TIME] Tiempo máximo alcanzado")
                        break

                except queue.Empty:
                    continue

        finally:
            stream.stop()
            stream.close()

        if self.audio_buffer:
            return np.concatenate(self.audio_buffer, axis=0).flatten()
        return np.array([])

    async def send_state(self, state: str, message: str = ""):
        msg = {
            "type": "state",
            "state": state,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }
        await connection_manager.send_json(self.client_id, msg)

    async def send_transcription(self, text: str, is_final: bool):
        msg = {
            "type": "transcription_final" if is_final else "transcription_partial",
            "text": text,
            "is_final": is_final,
            "language": "es",
            "timestamp": datetime.now().isoformat()
        }
        await connection_manager.send_json(self.client_id, msg)

    async def send_llm_token(self, token: str):
        msg = {
            "type": "llm_token",
            "token": token,
            "timestamp": datetime.now().isoformat()
        }
        await connection_manager.send_json(self.client_id, msg)

    async def send_llm_complete(self, text: str):
        msg = {
            "type": "llm_complete",
            "full_text": text,
            "timestamp": datetime.now().isoformat()
        }
        await connection_manager.send_json(self.client_id, msg)

    async def send_tts_chunk(self, chunk_b64: str):
        # Calculate amplitude and vowel for lip-sync
        import base64
        import numpy as np
        
        # Decode base64 audio
        audio_bytes = base64.b64decode(chunk_b64)
        audio_array = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        
        # RMS amplitude (0-1)
        rms = np.sqrt(np.mean(audio_array**2))
        amplitude = min(1.0, rms * 10)  # Scale for visibility
        
        # Simple vowel estimation from spectral centroid
        vowel = 'a'  # default
        if len(audio_array) > 100:
            # Very simple heuristic: check energy in different freq bands
            fft = np.fft.rfft(audio_array)
            freqs = np.fft.rfftfreq(len(audio_array), 1/24000)
            magnitude = np.abs(fft)
            
            # F1/F2 regions for vowels (rough approximation)
            f1_energy = np.sum(magnitude[(freqs > 300) & (freqs < 1000)])
            f2_energy = np.sum(magnitude[(freqs > 1000) & (freqs < 3000)])
            
            if f1_energy > f2_energy * 2:
                vowel = 'a'  # low F1, low F2
            elif f2_energy > f1_energy * 2:
                vowel = 'i'  # high F2
            elif f1_energy > f2_energy:
                vowel = 'o'  # mid F1, low F2
            else:
                vowel = 'e'  # mid
        
        msg = {
            "type": "tts_chunk",
            "audio_base64": chunk_b64,
            "sample_rate": 24000,
            "format": "pcm",
            "is_final": False,
            "amplitude": float(amplitude),
            "vowel": vowel,
            "timestamp": datetime.now().isoformat()
        }
        await connection_manager.send_json(self.client_id, msg)

    async def send_tts_complete(self):
        msg = {
            "type": "tts_complete",
            "timestamp": datetime.now().isoformat()
        }
        await connection_manager.send_json(self.client_id, msg)


# ============================================
# MAIN
# ============================================

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from contextlib import asynccontextmanager
import asyncio
import json
import uuid
from typing import Optional
import os
from datetime import datetime

# Inicializar managers
init_managers()

app = FastAPI(
    title="Emma Bilingüe - Voice Tutor API",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Modelos para REST API
from pydantic import BaseModel

class SessionCreateRequest(BaseModel):
    level: str = "B1"
    unit: Optional[str] = None

class SessionResponse(BaseModel):
    session_id: str
    level: str
    unit: str

class TurnRequest(BaseModel):
    session_id: str
    audio_base64: str


# ============================================
# REST ENDPOINTS
# ============================================

@app.get("/")
async def root():
    return {"message": "Emma Bilingüe API", "version": "1.0.0", "status": "running"}

@app.get("/health")
async def health():
    import torch
    return {
        "status": "healthy",
        "gpu": torch.cuda.is_available(),
        "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
    }

@app.post("/api/sessions", response_model=dict)
async def create_session(request: dict):
    session_id = str(uuid.uuid4())
    return {"session_id": session_id, "level": "B1", "unit": "B1-u1"}

@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    return {"session_id": session_id, "status": "active"}

@app.delete("/api/sessions/{session_id}")
async def end_session(session_id: str):
    return {"message": "Session ended", "session_id": session_id}


# ============================================
# WEBSOCKET ENDPOINT
# ============================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    client_id = await connection_manager.connect(websocket)

    welcome_msg = {
        "type": "session_start",
        "timestamp": datetime.now().isoformat(),
        "session_id": None,
        "message": "Conectado a Emma Bilingüe"
    }
    await connection_manager.send_json(client_id, welcome_msg)

    try:
        while True:
            data = await websocket.receive_json()
            await handle_ws_message(client_id, data)
    except WebSocketDisconnect:
        connection_manager.disconnect(client_id)
    except Exception as e:
        print(f"Error WebSocket: {e}")
        connection_manager.disconnect(client_id)


async def handle_ws_message(client_id: str, data: dict):
    msg_type = data.get("type")

    if msg_type == "ping":
        await connection_manager.send_json(client_id, {
            "type": "pong",
            "timestamp": datetime.now().isoformat()
        })

    elif msg_type == "start_session":
        level = data.get("level", "B1")
        unit = data.get("unit", "B1-u1")
        session_id = str(uuid.uuid4())

        await connection_manager.send_json(client_id, {
            "type": "session_start",
            "session_id": session_id,
            "level": "B1",
            "unit": "B1-u1",
            "message": "Sesión iniciada"
        })

    elif msg_type == "audio_chunk":
        pass

    elif msg_type == "text_message":
        pass

    elif msg_type == "end_session":
        await connection_manager.send_json(client_id, {
            "type": "session_end",
            "message": "Sesión finalizada"
        })

    elif msg_type == "pong":
        pass


# ============================================
# MAIN
# ============================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )