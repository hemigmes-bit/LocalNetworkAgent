from pydantic import BaseModel, Field
from typing import Optional, Literal, List, Dict, Any
from enum import Enum
from datetime import datetime
from typing import Optional, Union


class WSMessageType(str, Enum):
    STATE = "state"
    TRANSCRIPTION_PARTIAL = "transcription_partial"
    TRANSCRIPTION_FINAL = "transcription_final"
    LLM_TOKEN = "llm_token"
    LLM_COMPLETE = "llm_complete"
    TTS_CHUNK = "tts_chunk"
    TTS_COMPLETE = "tts_complete"
    CORRECTIONS = "corrections"
    VOCABULARY = "vocabulary"
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    TURN_START = "turn_start"
    TURN_END = "turn_end"
    ERROR = "error"
    PING = "ping"
    PONG = "pong"


class WSState(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING_STT = "processing_stt"
    THINKING = "thinking"
    SPEAKING = "speaking"
    ERROR = "error"


class WSBaseMessage(BaseModel):
    type: WSMessageType
    timestamp: datetime = Field(default_factory=datetime.now)
    session_id: Optional[str] = None
    turn: Optional[int] = None


class WSStateMessage(BaseModel):
    type: Literal["state"] = "state"
    state: str
    message: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    session_id: Optional[str] = None
    turn: Optional[int] = None


class WSTranscriptionMessage(BaseModel):
    type: Literal["transcription_partial", "transcription_final"]
    text: str
    is_final: bool
    language: str = "es"
    timestamp: datetime = Field(default_factory=datetime.now)
    session_id: Optional[str] = None
    turn: Optional[int] = None


class WSLLMTokenMessage(BaseModel):
    type: Literal["llm_token"] = "llm_token"
    token: str
    accumulated: str
    timestamp: datetime = Field(default_factory=datetime.now)
    session_id: Optional[str] = None
    turn: Optional[int] = None


class WSLLMCompleteMessage(BaseModel):
    type: Literal["llm_complete"] = "llm_complete"
    full_text: str
    corrections: List[Dict] = []
    vocabulary: List[Dict] = []
    timestamp: datetime = Field(default_factory=datetime.now)
    session_id: Optional[str] = None
    turn: Optional[int] = None


class WSTTSChunkMessage(BaseModel):
    type: Literal["tts_chunk"] = "tts_chunk"
    audio_base64: str
    sample_rate: int = 24000
    format: str = "pcm"
    is_final: bool = False
    timestamp: datetime = Field(default_factory=datetime.now)
    session_id: Optional[str] = None
    turn: Optional[int] = None


class WSTTSCompleteMessage(BaseModel):
    type: Literal["tts_complete"] = "tts_complete"
    duration_ms: int
    timestamp: datetime = Field(default_factory=datetime.now)
    session_id: Optional[str] = None
    turn: Optional[int] = None


class WSCorrectionsMessage(BaseModel):
    type: Literal["corrections"] = "corrections"
    corrections: List[Dict]
    timestamp: datetime = Field(default_factory=datetime.now)
    session_id: Optional[str] = None
    turn: Optional[int] = None


class WSVocabularyMessage(BaseModel):
    type: Literal["vocabulary"] = "vocabulary"
    vocabulary: List[Dict]
    timestamp: datetime = Field(default_factory=datetime.now)
    session_id: Optional[str] = None
    turn: Optional[int] = None


class WSSessionStartMessage(BaseModel):
    type: Literal["session_start"] = "session_start"
    session_id: str
    level: str
    unit: str
    timestamp: datetime = Field(default_factory=datetime.now)


class WSSessionEndMessage(BaseModel):
    type: Literal["session_end"] = "session_end"
    session_id: str
    turns: int
    duration_seconds: float
    timestamp: datetime = Field(default_factory=datetime.now)


class WSTurnStartMessage(BaseModel):
    type: Literal["turn_start"] = "turn_start"
    turn: int
    timestamp: datetime = Field(default_factory=datetime.now)
    session_id: Optional[str] = None


class WSTurnEndMessage(BaseModel):
    type: Literal["turn_end"] = "turn_end"
    turn: int
    duration_ms: int
    timestamp: datetime = Field(default_factory=datetime.now)
    session_id: Optional[str] = None


class WSErrorMessage(BaseModel):
    type: Literal["error"] = "error"
    error: str
    code: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    session_id: Optional[str] = None


class WSPingMessage(BaseModel):
    type: Literal["ping"] = "ping"
    timestamp: datetime = Field(default_factory=datetime.now)


class WSPongMessage(BaseModel):
    type: Literal["pong"] = "pong"
    timestamp: datetime = Field(default_factory=datetime.now)


# Imports necesarios
from pydantic import BaseModel, Field
from typing import Optional, Literal, List, Dict, Any
from enum import Enum
from datetime import datetime
from typing import Optional, Union