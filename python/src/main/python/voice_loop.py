#!/usr/bin/env python3
"""
Emma Bilingue - Voice Loop

Pipeline completo: VAD -> STT -> LLM streaming -> TTS -> Altavoz
Repite hasta Ctrl+C.

Flujo: Silero VAD detecta fin de frase -> faster-whisper (GPU) transcribe ->
OpenRouter LLM streaming -> Kokoro TTS reproduce -> altavoz.
Hasta que el usuario pulse Ctrl+C.

REQUISITOS:
- Ollama corriendo localmente (ollama serve)
- Modelo qwen2.5:7b-instruct-q4_K_M descargado (ollama pull qwen2.5:7b-instruct-q4_K_M)
- Media duplex: ignorar mic mientras suena el altavoz
- time.perf_counter por turno: user_speech_end -> transcription_ready -> first_llm_token -> full_response -> first_audio_played
- Guardar logs/latency.csv
- Historial de ultimos N turnos (configurable)
- Voces: ingles y espanol configurables, seleccion por idioma de respuesta
- Prompt sistema: tutora bilingue, frases cortas, puede espanol
- Modular: cambiar solo la voz (TTS) sin reescribir pipeline completo
"""

import sys
import os
import json
import csv
import time
import signal
import threading
import queue
import re
import unicodedata
import numpy as np
from pathlib import Path
import collections
from collections import deque
from dataclasses import dataclass, asdict, field
from typing import Deque, List, Dict, Any, Optional

# Anadir path del proyecto
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "python" / "src" / "main" / "python"))

# Cargar configuracion YAML
try:
    import yaml
    with open(PROJECT_ROOT / "config.yaml", "r", encoding="utf-8") as f:
        CONFIG = yaml.safe_load(f)
except Exception as e:
    print(f"Error cargando config.yaml: {e}")
    sys.exit(1)

# Configuracion
CONFIG = CONFIG or {}
SYSTEM_PROMPT = CONFIG.get("system_prompt", "")
LLM_CONFIG = CONFIG.get("llm", {})
STT_CONFIG = CONFIG.get("stt", {})
VAD_CONFIG = CONFIG.get("vad", {})
TTS_CONFIG = CONFIG.get("tts", {})
HISTORY_CONFIG = CONFIG.get("history", {})
CONVERSATION_CONFIG = CONFIG.get("conversation", {})
AUDIO_CONFIG = CONFIG.get("audio", {})
MEMORY_CONFIG = CONFIG.get("memory", {})

# Configuración nueva
MEMORY_ENABLED = MEMORY_CONFIG.get("enabled", True)
MEMORY_PATH = MEMORY_CONFIG.get("path", "memoria_emma.json")
VOICE_SWITCHING_ENABLED = MEMORY_CONFIG.get("voice_switching", True)
WEB_SEARCH_ENABLED = MEMORY_CONFIG.get("web_search", False)
WEB_SEARCH_ENGINE = MEMORY_CONFIG.get("engine", "duckduckgo")

# Busqueda web (modulo independiente con DuckDuckGo, Wikipedia y noticias)
WEB_CONFIG = CONFIG.get("web", {})
try:
    import web_tools
    WEB_TOOLS_AVAILABLE = True
except Exception as _web_import_error:
    web_tools = None
    WEB_TOOLS_AVAILABLE = False
    print(f"[WEB] Herramientas web no disponibles: {_web_import_error}")

WEB_ENABLED = bool(WEB_CONFIG.get("enabled", True)) and WEB_TOOLS_AVAILABLE

# Reconocimiento de canciones (Shazam + melodias silbadas)
SONG_CONFIG = CONFIG.get("song_recognition", {})
try:
    import song_recognizer
    SONG_RECOGNITION_AVAILABLE = True
except Exception as _song_import_error:
    song_recognizer = None
    SONG_RECOGNITION_AVAILABLE = False
    print(f"[CANCIONES] Reconocimiento no disponible: {_song_import_error}")

SONG_ENABLED = bool(SONG_CONFIG.get("enabled", True)) and SONG_RECOGNITION_AVAILABLE
SONG_SECONDS = float(SONG_CONFIG.get("seconds", 9))

# Estado persistente: idioma preferido y perfil de aprendizaje
try:
    import emma_state
    EMMA_STATE_AVAILABLE = True
except Exception as _state_import_error:
    emma_state = None
    EMMA_STATE_AVAILABLE = False
    print(f"[ESTADO] Perfil de aprendizaje no disponible: {_state_import_error}")

LANGUAGE_PREFERENCE = (
    emma_state.get_language_preference() if EMMA_STATE_AVAILABLE else None
)
print(f"[IDIOMA] Preferencia guardada: {LANGUAGE_PREFERENCE or 'automática'}")

# Esquema JSON que Ollama impone al modelo: evita respuestas a medias y
# garantiza que el perfil de aprendizaje reciba siempre sus campos.
LLM_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "spoken": {"type": "string"},
        "language": {"type": "string", "enum": ["en", "es"]},
        "corrections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "original": {"type": "string"},
                    "corrected": {"type": "string"},
                    "type": {
                        "type": "string",
                        "enum": ["grammar", "vocabulary", "pronunciation"],
                    },
                    "explanation": {"type": "string"},
                },
                "required": ["original", "corrected", "type", "explanation"],
            },
        },
        "vocabulary": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "word": {"type": "string"},
                    "translation": {"type": "string"},
                    "example": {"type": "string"},
                },
                "required": ["word", "translation", "example"],
            },
        },
        "learning": {
            "type": "object",
            "properties": {
                "focus": {"type": "string"},
                "challenge": {"type": "string"},
                "exercise": {"type": "string"},
            },
            "required": ["focus", "challenge", "exercise"],
        },
    },
    "required": ["spoken", "language", "corrections", "vocabulary", "learning"],
}

# Umbral de nivel de inglés (0-1, donde 0 es principiante y 1 es experto)
ENGLISH_PROFICIENCY_THRESHOLD = MEMORY_CONFIG.get("english_proficiency_threshold", 0.5)

# Ollama local - no requiere API key
OLLAMA_URL = LLM_CONFIG.get("ollama_url", "http://localhost:11434")
OLLAMA_MODEL = LLM_CONFIG.get("ollama_model", "qwen2.5:7b-instruct")

LLM_MODELS = [OLLAMA_MODEL]
TEMPERATURE = LLM_CONFIG.get("temperature", 0.7)
MAX_TOKENS = LLM_CONFIG.get("max_tokens", 500)
STORY_MAX_TOKENS = int(LLM_CONFIG.get("story_max_tokens", 1400))
STORY_FIRST_PASS_TOKENS = int(LLM_CONFIG.get("story_first_pass_tokens", 500))
LLM_KEEP_ALIVE = str(LLM_CONFIG.get("keep_alive", "30m"))
LLM_NUM_CTX = int(LLM_CONFIG.get("num_ctx", 4096))
MAX_HISTORY = HISTORY_CONFIG.get("max_turns", 10)
MAX_CONVERSATION_TURNS = int(CONVERSATION_CONFIG.get("max_turns", 500))
STT_MODEL_SIZE = STT_CONFIG.get("model_size", "base")
STT_DEVICE = STT_CONFIG.get("device", "cuda")
STT_COMPUTE_TYPE = STT_CONFIG.get("compute_type", "float16")
STT_LANGUAGE = STT_CONFIG.get("language") or None
STT_BEAM_SIZE = STT_CONFIG.get("beam_size", 1)
STT_VAD_FILTER = STT_CONFIG.get("vad_filter", True)
STT_FALLBACK_LANGUAGES = tuple(STT_CONFIG.get("fallback_languages", ["es", "en"]))
VAD_THRESHOLD = VAD_CONFIG.get("threshold", 0.5)
VAD_MIN_SILENCE_MS = VAD_CONFIG.get("min_silence_duration_ms", 400)
VAD_END_SILENCE_MS = VAD_CONFIG.get("end_of_turn_silence_ms", 800)
TTS_MODEL = TTS_CONFIG.get("model_path", "kokoro-v1.0.onnx")
TTS_VOICES_PATH = TTS_CONFIG.get("voices_path", "voices.json")
TTS_SAMPLE_RATE = TTS_CONFIG.get("sample_rate", 24000)
TTS_ENGLISH_VOICE = TTS_CONFIG.get("voices", {}).get("en", "af_heart")
TTS_SPANISH_VOICE = TTS_CONFIG.get("voices", {}).get("es", "ef_dora")
TTS_SPEED = float(TTS_CONFIG.get("speed", 0.95))
VOICE_PROFILE_ID = "warm"

# La preferencia guardada por el usuario manda sobre config.yaml.
if EMMA_STATE_AVAILABLE:
    try:
        _saved_voice = emma_state.get_voice_prefs()
        TTS_ENGLISH_VOICE = _saved_voice.get("voice_en") or TTS_ENGLISH_VOICE
        TTS_SPANISH_VOICE = _saved_voice.get("voice_es") or TTS_SPANISH_VOICE
        TTS_SPEED = float(_saved_voice.get("speed", TTS_SPEED))
        VOICE_PROFILE_ID = _saved_voice.get("profile", VOICE_PROFILE_ID)
    except Exception as _voice_prefs_error:
        print(f"[VOZ] No se pudo cargar la preferencia de voz: {_voice_prefs_error}")
print(
    f"[VOZ] Perfil: {VOICE_PROFILE_ID} | en={TTS_ENGLISH_VOICE} "
    f"| es={TTS_SPANISH_VOICE} | speed={TTS_SPEED:.2f}"
)
AUDIO_SAMPLE_RATE = AUDIO_CONFIG.get("sample_rate", 16000)
HALF_DUPLEX = AUDIO_CONFIG.get("half_duplex", True)
FULL_DUPLEX = bool(AUDIO_CONFIG.get("full_duplex", not HALF_DUPLEX))
BARGE_IN_ENABLED = bool(AUDIO_CONFIG.get("barge_in", True)) and FULL_DUPLEX
BARGE_IN_MIN_MS = int(AUDIO_CONFIG.get("barge_in_min_ms", 300))
BARGE_IN_ECHO_MARGIN = float(AUDIO_CONFIG.get("barge_in_echo_margin", 2.2))
BARGE_IN_WARMUP_MS = int(AUDIO_CONFIG.get("barge_in_warmup_ms", 250))
BARGE_IN_MIN_RMS = float(AUDIO_CONFIG.get("barge_in_min_rms", 0.012))
POST_TTS_DELAY_MS = AUDIO_CONFIG.get("post_tts_delay_ms", 500)

# Audio que el usuario ya ha dicho mientras Emma hablaba. Se reutiliza como
# inicio del siguiente turno para no perder sus primeras palabras.
_barge_prebuffer: List[np.ndarray] = []
_barge_lock = threading.Lock()
ACTIVE_MIC_STREAM = None

# ==========================================
# Data Classes
# ==========================================

@dataclass
class TurnResult:
    turn: int
    stt_ms: float
    llm_first_token_ms: float
    llm_full_ms: float
    tts_first_ms: float
    total_ms: float
    user_text: str
    assistant_spoken: str
    assistant_language: str
    corrections: List[Dict]
    vocabulary: List[Dict]
    user_language: str = "es"
    learning: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ConversationHistory:
    user_texts: Deque[str]
    assistant_responses: Deque[str]
    assistant_languages: Deque[str]
    turn_times: Deque[float]

# ==========================================
# MicStream - Audio input stream with queue
# ==========================================
class MicStream:
    def __init__(self, sample_rate=16000, block_size=512, device=None, channels=1):
        self.sample_rate = sample_rate
        self.block_size = block_size
        self.device = device
        self.channels = channels
        self._stream = None
        self._queue = collections.deque()
        self._running = False
        self._lock = threading.Lock()
    
    def _callback(self, indata, frames, time_info, status):
        if status:
            print(f"   [MicStream] Status: {status}")
        if self._running:
            with self._lock:
                self._queue.append(indata.copy())
    
    def start(self):
        if self._running:
            return
        import sounddevice as sd
        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            blocksize=self.block_size,
            channels=self.channels,
            dtype='float32',
            device=self.device,
            callback=self._callback
        )
        self._stream.start()
        self._running = True
        print("   [MicStream] Iniciado")
    
    def flush(self):
        """Vacia la cola de audio acumulada (usar al inicio de cada turno)."""
        with self._lock:
            self._queue.clear()
    
    def read(self, timeout=1.0):
        """Lee un bloque de audio de la cola."""
        import time
        t0 = time.perf_counter()
        while self._running:
            with self._lock:
                if self._queue:
                    return self._queue.popleft()
            if time.perf_counter() - t0 > timeout:
                return None
            time.sleep(0.001)
        return None
    
    def stop(self):
        if self._running:
            self._running = False
            if self._stream:
                self._stream.stop()
                self._stream.close()
                self._stream = None
            print("   [MicStream] Detenido")

# ==========================================
# Barge-in (full duplex)
# ==========================================
class BargeInDetector:
    """Detecta si el usuario habla mientras Emma esta hablando.

    El micro siempre capta parte del altavoz, asi que no basta con el VAD:
    exigimos que la voz supere el eco reciente por un margen configurable.
    Con auriculares el eco es minimo y la deteccion es casi inmediata.
    """

    def __init__(
        self,
        model,
        sample_rate=16000,
        threshold=0.5,
        min_speech_ms=300,
        echo_margin=2.2,
        warmup_ms=250,
        min_rms=0.012,
    ):
        self.model = model
        self.sample_rate = sample_rate
        self.threshold = float(threshold)
        self.min_speech_ms = int(min_speech_ms)
        self.echo_margin = float(echo_margin)
        self.warmup_ms = int(warmup_ms)
        self.min_rms = float(min_rms)
        self.frame_ms = 32
        self.rearm()

    def rearm(self):
        """Reinicia el detector al empezar una frase de Emma."""
        self.voice_ms = 0
        self.loud_ms = 0
        self.frames = []
        self.history = collections.deque(maxlen=32)
        self.warmup_left = self.warmup_ms
        try:
            self.model.reset_states()
        except Exception:
            pass

    def _prob(self, x):
        if self.model is None:
            return 1.0
        try:
            import torch
            with torch.no_grad():
                value = self.model(
                    torch.from_numpy(np.ascontiguousarray(x)), self.sample_rate
                )
            return float(value.item())
        except Exception:
            return 0.0

    def push(self, x) -> bool:
        """Anade un frame de 32 ms. Devuelve True si hay que interrumpir.

        Se exigen dos condiciones sostenidas: que el VAD reconozca voz y que
        esa voz supere el eco de Emma. Los microsilencios entre palabras no
        reinician el contador; solo lo hacen los silencios de verdad.
        """
        x = np.asarray(x, dtype=np.float32).reshape(-1)
        rms = float(np.sqrt(np.mean(x ** 2))) if x.size else 0.0

        # Los primeros milisegundos de cada frase solo sirven para medir el eco.
        if self.warmup_left > 0:
            self.warmup_left -= self.frame_ms
            self.history.append(rms)
            return False

        # Percentil bajo del ultimo segundo: el eco de Emma esta casi siempre,
        # la voz del usuario solo a ratos. Asi el umbral no se dispara con ella.
        echo_floor = (
            float(np.percentile(self.history, 25)) if self.history else 0.0
        )
        threshold_rms = max(self.min_rms, echo_floor * self.echo_margin)
        self.history.append(rms)

        is_voice = self._prob(x) >= self.threshold
        is_loud = rms > threshold_rms

        if is_voice:
            self.voice_ms += self.frame_ms
        else:
            self.voice_ms = max(0, self.voice_ms - self.frame_ms)

        if is_loud:
            self.loud_ms += self.frame_ms
        else:
            self.loud_ms = max(0, self.loud_ms - self.frame_ms)

        if self.voice_ms > 0 or self.loud_ms > 0:
            self.frames.append(x)
        else:
            self.frames = []

        return (
            self.voice_ms >= self.min_speech_ms
            and self.loud_ms >= self.min_speech_ms
        )

    def take_frames(self):
        frames = list(self.frames)
        self.frames = []
        self.voice_ms = 0
        self.loud_ms = 0
        return frames


def stash_barge_in_audio(frames):
    """Guarda lo que el usuario dijo mientras Emma hablaba."""
    global _barge_prebuffer
    with _barge_lock:
        limit = max(1, int(1500 / 32))
        _barge_prebuffer = list(frames)[-limit:]


def take_barge_in_audio():
    """Recupera y vacia el audio pendiente de un barge-in."""
    global _barge_prebuffer
    with _barge_lock:
        frames = list(_barge_prebuffer)
        _barge_prebuffer = []
    return frames

# ==========================================
# Inicializacion de componentes
# ==========================================

import torch
print(f"PyTorch {torch.__version__} - CUDA: {torch.cuda.is_available()}")

if not torch.cuda.is_available():
    print("Advertencia: CUDA no disponible, STT usara CPU (lento)")

# STT (faster-whisper)
print("Cargando STT (faster-whisper)...")
try:
    from stt_faster_whisper import FasterWhisperSTT
    stt = FasterWhisperSTT(
        model_size=STT_MODEL_SIZE,
        device=STT_DEVICE,
        compute_type=STT_COMPUTE_TYPE
    )
    print("STT cargado")
except Exception as e:
    print(f"Error cargando STT: {e}")
    sys.exit(1)

# LLM (Ollama local)
print(f"Verificando Ollama en {OLLAMA_URL}...")


def ensure_ollama_local(url: str, timeout_s: float = 20.0) -> bool:
    """Arranca Ollama si la URL es local y el servicio no responde.

    Evita que Emma se cierre al inicio cuando Ollama se ha apagado o no
    arranco con Windows. Solo actua sobre localhost/127.0.0.1.
    """
    import subprocess
    import urllib.parse

    host = (urllib.parse.urlparse(url).hostname or "").lower()
    if host not in ("localhost", "127.0.0.1", "::1"):
        return False

    candidates = [
        os.path.join(
            os.environ.get("LOCALAPPDATA", ""),
            "Programs", "Ollama", "ollama.exe",
        ),
        r"C:\Program Files\Ollama\ollama.exe",
        r"C:\Program Files (x86)\Ollama\ollama.exe",
    ]
    exe = next((p for p in candidates if p and os.path.isfile(p)), None)
    if exe is None:
        from shutil import which
        exe = which("ollama")
    if exe is None:
        return False

    print(f"   Ollama no responde. Arrancando: {exe} serve")
    try:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        subprocess.Popen(
            [exe, "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
        )
    except Exception as error:
        print(f"   No se pudo arrancar Ollama: {error}")
        return False

    import requests
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            if requests.get(f"{url}/api/tags", timeout=2).status_code == 200:
                print("   Ollama arrancado correctamente")
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


try:
    import requests
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
    except Exception:
        if ensure_ollama_local(OLLAMA_URL):
            resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        else:
            raise
    if resp.status_code == 200:
        models = [m["name"] for m in resp.json().get("models", [])]
        if OLLAMA_MODEL in models:
            print(f"LLM (Ollama) listo: {OLLAMA_MODEL}")
        else:
            print(f"Modelo {OLLAMA_MODEL} no encontrado. Disponibles: {models}")
            print(f"Ejecuta: ollama pull {OLLAMA_MODEL}")
            sys.exit(1)
    else:
        print("Ollama no responde. Ejecuta: ollama serve")
        sys.exit(1)
except Exception as e:
    print(f"Error conectando a Ollama: {e}")
    print("Asegúrate de que Ollama esté corriendo: ollama serve")
    sys.exit(1)

# TTS (Kokoro)
print("Cargando TTS (Kokoro)...")
try:
    from tts_kokoro import KokoroTTS
    tts = KokoroTTS(model_path=TTS_MODEL, voices_path=TTS_VOICES_PATH)
    tts.voices.update({
        "en": TTS_ENGLISH_VOICE, "es": TTS_SPANISH_VOICE,
        "es_male": TTS_CONFIG.get("voices", {}).get("es_male", "em_alex"),
        "en_male": TTS_CONFIG.get("voices", {}).get("en_male", "am_michael")
    })
    tts.speed = TTS_SPEED
    print("TTS cargado")
except Exception as e:
    print(f"Error cargando TTS: {e}")
    sys.exit(1)

# VAD (Silero)
BARGE_IN_DETECTOR = None
print("Cargando VAD (Silero)...")
try:
    from silero_vad import load_silero_vad, VADIterator
    vad_model = load_silero_vad()
    vad_iterator = VADIterator(
        vad_model,
        threshold=VAD_THRESHOLD,
        sampling_rate=STT_CONFIG.get("sample_rate", 16000),
        min_silence_duration_ms=VAD_MIN_SILENCE_MS
    )
    print("VAD cargado")

    if BARGE_IN_ENABLED:
        try:
            # Silero guarda estado interno en el modelo, asi que el barge-in
            # necesita su propia instancia para no corromper el VAD del turno.
            barge_vad_model = load_silero_vad()
            BARGE_IN_DETECTOR = BargeInDetector(
                barge_vad_model,
                sample_rate=STT_CONFIG.get("sample_rate", 16000),
                threshold=VAD_THRESHOLD,
                min_speech_ms=BARGE_IN_MIN_MS,
                echo_margin=BARGE_IN_ECHO_MARGIN,
                warmup_ms=BARGE_IN_WARMUP_MS,
                min_rms=BARGE_IN_MIN_RMS,
            )
            print("Barge-in listo (full duplex)")
        except Exception as barge_error:
            print(f"Barge-in no disponible: {barge_error}")
except ImportError:
    print("Silero VAD no disponible, usando deteccion simple")
    vad_iterator = None
except Exception as e:
    print(f"Error cargando VAD: {e}")
    vad_iterator = None

# History management
history = ConversationHistory(
    user_texts=deque(maxlen=MAX_HISTORY),
    assistant_responses=deque(maxlen=MAX_HISTORY),
    assistant_languages=deque(maxlen=MAX_HISTORY),
    turn_times=deque(maxlen=MAX_HISTORY)
)

# Timer
class Timer:
    def __init__(self):
        self.timings = []
        self.current_start = None
        self.stt_end = None
        self.llm_end = None
        self.tts_end = None
    
    def start(self):
        self.current_start = time.perf_counter()
    
    def mark_stt(self):
        self.stt_end = time.perf_counter()
    
    def mark_llm(self):
        self.llm_end = time.perf_counter()
    
    def mark_tts(self):
        self.tts_end = time.perf_counter()
    
    def finish_turn(self, turn: int):
        total_end = time.perf_counter()
        stt_ms = (self.stt_end - self.current_start) * 1000
        llm_ms = (self.llm_end - self.stt_end) * 1000
        tts_ms = (self.tts_end - self.llm_end) * 1000
        total_ms = (total_end - self.current_start) * 1000
        timing = TurnResult(
            turn=turn,
            stt_ms=stt_ms,
            llm_first_token_ms=llm_ms,
            llm_full_ms=llm_ms,
            tts_first_ms=tts_ms,
            total_ms=total_ms,
            user_text="",
            assistant_spoken="",
            assistant_language="",
            corrections=[],
            vocabulary=[]
        )
        self.timings.append(timing)
        print(f"\n{'='*50}")
        print(f"TURNO {turn} - TIEMPOS:")
        print(f"   STT (faster-whisper): {stt_ms:.1f}ms")
        print(f"   LLM (OpenRouter):      {llm_ms:.1f}ms")
        print(f"   TTS (Kokoro):          {tts_ms:.1f}ms")
        print(f"   TOTAL:                 {total_ms:.1f}ms")
        print(f"{'='*50}\n")
    
    def print_summary(self):
        if not self.timings:
            return
        print("\n" + "="*60)
        print("RESUMEN DE TURNOS")
        print("="*60)
        for t in self.timings:
            print(f"Turno {t.turn}: STT={t.stt_ms:.0f}ms LLM={t.llm_first_token_ms:.0f}ms TTS={t.tts_first_ms:.0f}ms Total={t.total_ms:.0f}ms")
        print("="*60)

timer = Timer()

# Statistics
turn_results = []
total_turns = 0
stop_loop = False

# Interfaz gráfica: el motor publica eventos y Tkinter los consume
UI_EVENTS = queue.Queue()
ENGINE_STOP_EVENT = threading.Event()
ENGINE_FINISHED_EVENT = threading.Event()

# Mensajes escritos en la ventana. El motor los consume como si fueran voz.
TEXT_INPUT_QUEUE = queue.Queue()
TEXT_INPUT_MAX_CHARS = 2000

def ui_emit(event_type: str, payload: str = ""):
    """Envía un evento a la ventana sin tocar Tkinter desde hilos secundarios."""
    UI_EVENTS.put((event_type, payload))

def submit_typed_text(text: str) -> bool:
    """Encola un mensaje escrito desde la ventana. Devuelve True si es válido."""
    text = (text or "").strip()
    if not text:
        return False
    if len(text) > TEXT_INPUT_MAX_CHARS:
        text = text[:TEXT_INPUT_MAX_CHARS]
    TEXT_INPUT_QUEUE.put(text)
    return True

def has_typed_text() -> bool:
    return not TEXT_INPUT_QUEUE.empty()

def take_typed_text():
    """Saca el siguiente mensaje escrito, o None si no hay ninguno."""
    try:
        return TEXT_INPUT_QUEUE.get_nowait()
    except queue.Empty:
        return None

# ==========================================
# Funciones auxiliares
# ==========================================

STORY_PROMPT_BLOCK = """MODO CUENTO (ACTIVO):
El usuario ha pedido un cuento. Escribe la PRIMERA PARTE de un relato que durará unos 2 minutos.
- Empieza directamente con la primera frase del cuento. No digas "voy a buscar", "aquí va", "prepárate" ni "¿listo?".
- Ignora cualquier promesa anterior de reproducir o poner un audio; no la repitas.
- Extensión de esta primera parte: 120-150 palabras.
- Presenta a los personajes y el problema, y termina en un momento de suspense. NO cierres el cuento ni escribas "Fin".
- Traduce al idioma de respuesta cualquier palabra o expresión que el usuario diga en otro idioma; no dejes términos en inglés dentro del cuento.
- Usa frases cortas y párrafos separados; el texto se leerá en voz alta.
- Tono cálido y cercano.
- Si piden una historia real o histórica, cuéntala como relato sin inventar datos falsos.
- Deja "corrections" y "vocabulary" vacíos, y "learning" con todos sus campos vacíos."""


def _fold_text(text: str) -> str:
    """Minúsculas y sin acentos, para comparar patrones con seguridad."""
    normalized = unicodedata.normalize("NFD", (text or "").lower())
    return "".join(c for c in normalized if unicodedata.category(c) != "Mn")


_STORY_PATTERNS = (
    r"\bcuentame\s+(un|una)\s+(cuento|historia)\b",
    r"\bcuentame\s+(el|la)\s+cuento\b",
    r"\b(dime|narra|leeme|lee|reproduce|reproduceme|pon|ponme|quiero)\b"
    r".*\b(un|una)\b.*\b(cuento|historia)\b",
    r"\b(un|una)\s+(cuento|historia)\s+(de|para|sobre)\b"
    r".*\b(minuto|minutos|dormir|nino|ninos|infantil)\b",
    r"\bcuento\b.*\b(de|para)\b.*\b(minuto|minutos|dormir|nino|ninos|infantil)\b",
    r"\b(tell|read|play|narrate)\s+(me\s+)?(a\s+)?"
    r"(short\s+|bedtime\s+|two[- ]minute\s+|2[- ]minute\s+)?story\b",
    r"\b(want|need)\s+(a\s+)?story\b",
    r"\b(find|search for|look for)\s+(me\s+)?(a\s+)?"
    r"(short\s+|bedtime\s+|two[- ]minute\s+|2[- ]minute\s+)?story\b",
    r"\bstory\s+(for|about)\s+\d+\s*(minute|minutes)\b",
    r"\b(busca|buscame|encuentra|encontrame)\s+(un|una)\s+(cuento|historia)\b",
)


def is_story_request(text: str) -> bool:
    """True si el usuario pide un cuento o una historia narrada."""
    folded = _fold_text(text)
    if not folded.strip():
        return False
    return any(re.search(pattern, folded) for pattern in _STORY_PATTERNS)


def detect_language(text: str) -> str:
    if not text:
        return "es"
    
    english_indicators = sum(1 for word in text.lower().split() 
                           if word in ['the', 'and', 'i', 'you', 'to', 'a', 'of', 'in', 'for', 'is'])
    spanish_indicators = sum(1 for word in text.lower().split() 
                            if word in ['el', 'la', 'y', 'lo', 'que', 'para', 'con', 'por', 'es', 'un'])
    
    if english_indicators > spanish_indicators * 1.5:
        return "en"
    elif spanish_indicators > english_indicators * 1.5:
        return "es"
    else:
        if history.assistant_languages:
            return history.assistant_languages[-1]
        return "es"

def select_voice(language: str) -> str:
    if language.lower().startswith("en"):
        return TTS_ENGLISH_VOICE
    else:
        return TTS_SPANISH_VOICE


def split_into_sentences(text: str) -> list:
    """Divide texto en oraciones para TTS streaming."""
    if not text:
        return []
    import re
    # Separar por . ! ? seguidos de espacio o fin de línea
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    # Filtrar oraciones vacías
    return [s.strip() for s in sentences if s.strip()]


def save_latency_csv(results: List[TurnResult], csv_path: str = "logs/latency.csv"):
    try:
        os.makedirs("logs", exist_ok=True)
        file_exists = os.path.exists(csv_path)
        
        with open(csv_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow([
                    "turn", "stt_ms", "llm_first_token_ms", "llm_full_ms", 
                    "tts_first_ms", "total_ms", "user_text", "assistant_spoken",
                    "assistant_language"
                ])
            for r in results:
                writer.writerow([
                    r.turn, r.stt_ms, r.llm_first_token_ms, r.llm_full_ms,
                    r.tts_first_ms, r.total_ms, 
                    (r.user_text[:50] if r.user_text else "").replace("\n", " ").replace("\r", " "),
                    (r.assistant_spoken[:50] if r.assistant_spoken else "").replace("\n", " ").replace("\r", " "),
                    r.assistant_language
                ])
    except Exception as e:
        print(f"   [WARN] Error guardando CSV: {e}")

def add_turn_to_history(user_text: str, assistant_spoken: str, assistant_language: str):
    history.user_texts.append(user_text)
    history.assistant_responses.append(assistant_spoken)
    history.assistant_languages.append(assistant_language)

def build_language_block(preference: Optional[str], detected_lang: str = "") -> str:
    """Reglas de idioma que se inyectan al principio y al final del prompt.

    Un modelo 7B se deja arrastrar por el idioma del prompt base, asi que la
    regla se repite y se explica en el propio idioma objetivo.
    """
    if preference == "en":
        return (
            "IDIOMA OBLIGATORIO: INGLES (ENGLISH ONLY).\n"
            "The user has explicitly asked you to speak ONLY English.\n"
            "Every single word you say out loud, including greetings, apologies, "
            "explanations, corrections and the \"spoken\" field, MUST be in English.\n"
            "Do NOT use Spanish, not even one word. If you make a mistake, apologise "
            "in English. If the user writes in Spanish, still answer in English.\n"
            "The \"language\" field MUST be \"en\"."
        )
    if preference == "es":
        return (
            "IDIOMA OBLIGATORIO: ESPAÑOL.\n"
            "El usuario ha pedido hablar solo en español.\n"
            "Todas las palabras que digas en voz alta, incluidas salutaciones, "
            "disculpas, explicaciones y correcciones, deben estar en español. "
            "No uses inglés salvo para citar la palabra o frase que estés enseñando.\n"
            "El campo \"language\" debe ser \"es\"."
        )
    lang = "inglés" if detected_lang == "en" else "español"
    return (
        f"IDIOMA: responde en {lang}, el idioma del usuario en este turno. "
        "No cambies de idioma a mitad de la respuesta."
    )


def get_system_prompt_with_context(
    user_text: str = "",
    detected_lang: str = "",
    story: bool = False,
    story_material: str = "",
) -> str:
    if not SYSTEM_PROMPT:
        base_prompt = (
            "Eres Emma, tutora bilingue de ingles/espanol amable. "
            "Responde con frases cortas (max 2-3 oraciones). "
            "Corrige errores de forma natural. Introduce 1-2 palabras nuevas por turno. "
            "Manten un tono conversacional y alentador. "
            "FORMATO JSON OBLIGATORIO: {\"spoken\": \"frase natural\", "
            "\"language\": \"en|es\", \"corrections\": [], \"vocabulary\": [], "
            "\"learning\": {\"focus\": \"\", \"challenge\": \"\", \"exercise\": \"\"}}"
        )
    else:
        base_prompt = SYSTEM_PROMPT

    language_block = build_language_block(LANGUAGE_PREFERENCE, detected_lang)
    context = language_block + "\n\n" + base_prompt

    # En modo cuento no arrastramos historial ni perfil: evita que el modelo
    # repita promesas anteriores ("I'll play it") o convierta el cuento en clase.
    if history.user_texts and not story:
        recent = list(history.user_texts)[-3:]
        context += "\n\nHistorial reciente:\n"
        for i, ut in enumerate(recent):
            context += f"Usuario: {ut}\n"

    if EMMA_STATE_AVAILABLE and not story:
        try:
            learning_block = emma_state.build_learning_block()
        except Exception as state_error:
            learning_block = ""
            print(f"[PERFIL] No se pudo leer el perfil: {state_error}")
        if learning_block:
            context += "\n\n" + learning_block

    if story:
        context += "\n\n" + STORY_PROMPT_BLOCK
        if story_material:
            context += story_material

    # Repetir la regla al final: es la ultima instruccion que lee el modelo.
    context += "\n\nRECORDATORIO FINAL. " + language_block
    return context


def extract_spoken_text(content: str) -> str:
    """Extrae el campo "spoken" de un JSON completo o truncado.

    El modelo a veces devuelve el JSON sin cerrar cuando el texto es largo.
    En ese caso rescatamos la cadena de "spoken" y descartamos los metadatos.
    """
    content = (content or "").strip()
    if not content:
        return ""

    start = content.find("{")
    end = content.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            parsed = json.loads(content[start:end])
            spoken = parsed.get("spoken")
            if isinstance(spoken, str) and spoken.strip():
                return spoken.strip()
        except json.JSONDecodeError:
            pass

    match = re.search(r'"spoken"\s*:\s*"(.*)', content, re.DOTALL)
    if not match:
        return content

    raw = match.group(1)
    raw = re.split(
        r'"\s*,\s*"(language|corrections|vocabulary|learning)"\s*:',
        raw,
        maxsplit=1,
    )[0]
    raw = raw.rstrip()
    if raw.endswith('"'):
        raw = raw[:-1]
    try:
        return json.loads('"' + raw + '"').strip()
    except Exception:
        return (
            raw.replace("\\n", "\n")
            .replace('\\"', '"')
            .replace("\\\\", "\\")
            .strip()
        )


_STORY_CHAT_MARKERS = (
    "hasta la vista", "hasta pronto", "hasta luego", "adios", "adiós",
    "goodbye", "see you", "que tengas un buen dia", "que tengas un buen día",
    "espero verte", "solo tendras que pedirmelo", "solo tendrás que pedírmelo",
    "si alguna vez necesitas", "hablar en espanol", "hablar en español",
    "if you ever need", "just let me know", "nos vemos", "eso es todo",
    "hasta la proxima", "hasta la próxima",
)
_STORY_END_MARKERS = (
    "fin del cuento", "fin de la historia", "the end",
    "colorin colorado", "colorín colorado",
)


def clean_story_text(text: str) -> str:
    """Quita despedidas y charla que el modelo añade después del cuento."""
    text = (text or "").strip()
    if not text:
        return text

    lower = text.lower()
    search_start = int(len(text) * 0.55)
    cut = len(text)
    for marker in _STORY_CHAT_MARKERS:
        index = lower.find(marker, search_start)
        if index < 0:
            continue
        sentence_start = max(
            lower.rfind(". ", 0, index),
            lower.rfind("! ", 0, index),
            lower.rfind("? ", 0, index),
            lower.rfind("\n", 0, index),
        )
        cut = min(cut, sentence_start + 1 if sentence_start >= 0 else index)
    text = text[:cut].strip()

    lower = text.lower()
    end_search_start = int(len(text) * 0.60)
    for marker in _STORY_END_MARKERS:
        index = lower.find(marker, end_search_start)
        if index >= 0:
            end = index + len(marker)
            while end < len(text) and text[end] in ".!¡?¿ ":
                end += 1
            text = text[:end].strip()
            break
    return text


def build_continuation_payload(
    story: str,
    language: str,
    target_words: int = 360,
    num_predict: int = 900,
    stream: bool = True,
) -> Dict[str, Any]:
    """Prompt y payload para añadir la parte que falta del cuento."""
    current_words = len((story or "").split())
    if current_words < 250:
        part_instruction = (
            "Escribe la SEGUNDA PARTE (nudo y giro). No cierres el cuento "
            "todavía: termina en un momento de suspense. Unas 150 palabras."
        )
    else:
        part_instruction = (
            "Escribe la TERCERA PARTE y el DESENLACE. Cierra el cuento con un "
            "final claro y termina con la palabra 'Fin'. Unas 120-150 palabras."
        )

    language_block = build_language_block(LANGUAGE_PREFERENCE, language)
    system_prompt = (
        f"{language_block}\n\n"
        "Eres Emma, narradora. Continúa exactamente el cuento que se te da, "
        "sin repetir nada de lo ya contado y sin reiniciar la historia. "
        f"{part_instruction} "
        "No añadas despedidas, resúmenes, moralejas ni frases fuera del cuento. "
        "Devuelve solo el texto de la continuación en el campo \"spoken\". "
        "Deja \"corrections\" y \"vocabulary\" vacíos y \"learning\" sin contenido."
    )
    return {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Cuento hasta ahora:\n\n" + story},
        ],
        "stream": stream,
        "format": LLM_RESPONSE_SCHEMA,
        "keep_alive": LLM_KEEP_ALIVE,
        "options": {
            "temperature": TEMPERATURE,
            "num_predict": num_predict,
            "num_ctx": LLM_NUM_CTX,
        },
    }


def continue_story(story: str, language: str, target_words: int = 360) -> str:
    """Pide al LLM una continuación si el cuento se quedó corto.

    Un modelo 7B suele cerrar el relato antes de las 250 palabras aunque el
    prompt se lo pida. Esta segunda pasada añade el tramo que falta sin
    reiniciar la historia.
    """
    current_words = len((story or "").split())
    if current_words >= target_words:
        return ""

    payload = build_continuation_payload(
        story, language, target_words=target_words, num_predict=900, stream=False
    )

    try:
        import requests

        response = requests.post(
            "http://localhost:11434/api/chat", json=payload, timeout=120
        )
        if response.status_code != 200:
            print(f"   [CUENTO] Error {response.status_code} al continuar")
            return ""
        content = response.json().get("message", {}).get("content", "")
        extra = extract_spoken_text(content)
        extra = re.sub(r"^```[a-zA-Z]*\s*", "", extra)
        extra = re.sub(r"\s*```$", "", extra).strip()
        extra = clean_story_text(extra)
        if not extra:
            print("   [CUENTO] Continuacion vacia")
            return ""
        max_extra = max(90, target_words - current_words + 30)
        words = extra.split()
        has_ending = any(
            marker in extra.lower() for marker in _STORY_END_MARKERS
        )
        if len(words) > max_extra and not has_ending:
            cut = " ".join(words[:max_extra])
            last_stop = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
            if last_stop > 0:
                cut = cut[:last_stop + 1]
            extra = cut
        print(f"   [CUENTO] Continuacion: {len(extra.split())} palabras")

        # Si el modelo arranca repitiendo la última frase, la quitamos.
        last_sentence = re.split(r"(?<=[.!?])\s+", story.strip())[-1].strip()
        if last_sentence and extra.startswith(last_sentence):
            extra = extra[len(last_sentence):].lstrip()
        return extra
    except Exception as error:
        print(f"   [CUENTO] No se pudo continuar el cuento: {error}")
        return ""

# ==========================================
# Pipeline principal
# ==========================================

def record_audio_vad(vad_iterator, stop_event, mic_stream, initial_chunks=None):
    """Graba hasta que el VAD marque fin de voz y pase un silencio de cierre.
    Devuelve (chunks, voice_detected, peak_rms), igual que antes.

    ``initial_chunks`` permite continuar un turno que empezo como barge-in
    mientras Emma hablaba: esas palabras ya estan capturadas y no se pierden.
    """
    FRAME_MS = 32            # 512 muestras a 16 kHz
    END_SILENCE_MS = 1200    # silencio tras 'end' para cerrar el turno
    MIN_SPEECH_MS = 400
    MAX_TURN_S = 20
    PRE_ROLL = 10            # ~320 ms previos al inicio de voz

    pending = [
        np.asarray(chunk, dtype=np.float32).reshape(-1)
        for chunk in (initial_chunks or [])
    ]
    vad_iterator.reset_states()
    # Primar el VAD con lo ya capturado para que detecte el final de la frase.
    for chunk in pending:
        try:
            vad_iterator(chunk, return_seconds=False)
        except Exception:
            break
    pre_roll = collections.deque(maxlen=PRE_ROLL)
    recorded_chunks = list(pending)
    speaking = bool(pending)
    end_pending = False
    frames_since_end = 0
    vad_seen = False
    peak_rms = 0.0
    for chunk in pending:
        peak_rms = max(peak_rms, float(np.sqrt(np.mean(chunk ** 2))))
    t_start = time.perf_counter() if speaking else None
    pending_deadline = time.perf_counter() + 3.0 if speaking else None
    if speaking:
        print(f"   [VAD] Continúo desde barge-in ({len(pending)} frames)")

    END_SILENCE_MS = VAD_END_SILENCE_MS

    print("   [VAD] Escuchando...")
    ui_emit("status", "Escuchando…")
    while not stop_event.is_set() and not ENGINE_STOP_EVENT.is_set():
        try:
            chunk = mic_stream.read(timeout=1.0)
        except Exception as e:
            print(f"   Error grabando: {e}")
            return None, False, 0.0
        if chunk is None:
            continue

        # Un mensaje escrito interrumpe la escucha: el texto tiene prioridad
        # sobre lo que se estuviera grabando.
        if has_typed_text():
            print("   [TEXTO] Mensaje escrito: dejo de escuchar")
            break

        x = chunk[:, 0] if chunk.ndim == 2 else chunk
        peak_rms = max(peak_rms, float(np.sqrt(np.mean(x ** 2))))

        ev = vad_iterator(x, return_seconds=False)
        if ev:
            vad_seen = True
            if "start" in ev:
                print(f"   [VAD] Inicio de voz: {ev}")
                if not speaking:
                    speaking = True
                    t_start = time.perf_counter()
                    recorded_chunks = list(pre_roll)
                end_pending = False
                frames_since_end = 0
            elif "end" in ev and speaking:
                print(f"   [VAD] Fin de voz: {ev}")
                end_pending = True
                frames_since_end = 0

        if speaking:
            recorded_chunks.append(x)
            if end_pending:
                frames_since_end += 1
                if frames_since_end * FRAME_MS >= END_SILENCE_MS:
                    print("   [VAD] Cerrando turno")
                    ui_emit("status", "Procesando tu voz…")
                    break
            if time.perf_counter() - t_start > MAX_TURN_S:
                print("   [VAD] Limite de 20 s, cerrando turno")
                break
            if (
                pending_deadline
                and not vad_seen
                and time.perf_counter() > pending_deadline
            ):
                # El barge-in pudo ser un falso positivo: no bloquear el turno.
                print("   [VAD] Sin voz clara tras el barge-in, cerrando")
                break
        else:
            pre_roll.append(x)

    if stop_event.is_set() or ENGINE_STOP_EVENT.is_set() or not speaking:
        return None, False, peak_rms
    if len(recorded_chunks) * FRAME_MS < MIN_SPEECH_MS:
        print("   [VAD] Demasiado corto, descartado")
        return [], False, peak_rms
    return recorded_chunks, True, peak_rms

def speak_text(text: str, language: str = "es", block: bool = True):
    """TTS tradicional: genera todo el audio y reproduce (bloqueante opcional)."""
    voice = select_voice(language)

    start = time.perf_counter()
    audio = tts.synthesize(text, lang=language, voice=select_voice(language))
    first_audio_start = time.perf_counter()

    import sounddevice as sd
    sd.play(audio, samplerate=TTS_SAMPLE_RATE)
    if block:
        sd.wait()

    end = time.perf_counter()
    tts_duration = (end - start) * 1000
    first_audio_duration = (first_audio_start - start) * 1000

    return tts_duration, first_audio_duration, audio


class StreamingTTS:
    """TTS streaming: reproduce oraciones mientras se generan."""
    
    def __init__(self, sample_rate=24000):
        self.sample_rate = sample_rate
        self.queue = queue.Queue()
        self.playing = False
        self.thread = None
        self.stop_event = threading.Event()
        self.interrupted = threading.Event()
        self.playback_started = threading.Event()
        self.playback_epoch = 0

    def start(self):
        """Inicia el hilo de reproducción."""
        self.stop_event.clear()
        self.interrupted.clear()
        self.playback_started.clear()
        self.playback_epoch = 0
        self.playing = True
        self.thread = threading.Thread(target=self._playback_loop, daemon=True)
        self.thread.start()

    def add_text(self, text: str, language: str):
        """Añade texto a la cola para síntesis y reproducción."""
        if not text.strip():
            return
        self.queue.put((text, language))

    def interrupt(self):
        """Corta la reproducción ya y descarta las frases pendientes."""
        self.interrupted.set()
        while True:
            try:
                self.queue.get_nowait()
            except queue.Empty:
                break
            self.queue.task_done()

    def stop(self, timeout=5.0):
        """Detiene la reproducción y espera a que termine."""
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=timeout)
        self.playing = False

    def is_done(self):
        """True cuando no quedan frases por sintetizar ni reproducir."""
        return self.queue.unfinished_tasks == 0

    def wait_until_done(self, timeout=60.0):
        """Espera hasta que todos los audios hayan terminado."""
        start = time.perf_counter()

        while not self.is_done():
            if time.perf_counter() - start > timeout:
                print("[TTS] Aviso: tiempo de espera agotado")
                return False

            time.sleep(0.02)

        return True

    def _play_audio(self, audio):
        """Reproduce un bloque de audio de forma interrumpible."""
        import sounddevice as sd

        audio = np.asarray(audio, dtype=np.float32).reshape(-1)
        if audio.size == 0:
            return

        self.playback_epoch += 1
        self.playback_started.set()

        block = 1024
        stream = sd.OutputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            device=getattr(tts, "output_device", None),
        )
        with stream:
            for start in range(0, audio.size, block):
                if self.stop_event.is_set() or self.interrupted.is_set():
                    break
                chunk = audio[start:start + block]
                stream.write(chunk.reshape(-1, 1))

    def _playback_loop(self):
        """Bucle de reproducción: saca texto de cola, sintetiza y reproduce."""
        try:
            while not self.stop_event.is_set() or not self.queue.empty():
                try:
                    text, language = self.queue.get(timeout=0.1)
                except queue.Empty:
                    continue
                try:
                    if self.interrupted.is_set():
                        continue
                    voice = select_voice(language)
                    audio = tts.synthesize(text, lang=language, voice=voice)
                    self._play_audio(audio)
                except Exception as e:
                    print(f"[TTS Streaming] Error: {e}")
                finally:
                    self.queue.task_done()
        finally:
            self.playing = False


class SpokenTextExtractor:
    """Extrae el campo ``spoken`` mientras el LLM todavía escribe el JSON.

    El modelo devuelve un JSON con ``spoken`` como primera clave. Leerlo en
    incremental permite empezar a hablar uno o dos segundos antes, sin esperar
    a que termine la respuesta completa.
    """

    _KEY_RE = re.compile(r'"spoken"\s*:\s*"')

    def __init__(self):
        self.buffer = ""
        self.pos = 0
        self.key_end = -1
        self.done = False
        self.plain = False
        self.decoded = ""

    def feed(self, delta: str) -> str:
        if self.done or not delta:
            return ""

        self.buffer += delta
        if self.key_end < 0:
            match = self._KEY_RE.search(self.buffer)
            if match:
                self.key_end = match.end()
                self.pos = self.key_end
            elif len(self.buffer) >= 400 and not self.buffer.lstrip().startswith("{"):
                # El modelo ignoró el esquema JSON y devolvió texto plano.
                self.plain = True
                self.key_end = 0
                self.pos = 0
            else:
                return ""

        out: List[str] = []
        index = self.pos
        length = len(self.buffer)
        while index < length:
            char = self.buffer[index]
            if not self.plain and char == '"':
                self.done = True
                self.pos = index + 1
                break
            if char == "\\":
                if index + 1 >= length:
                    break
                escaped = self.buffer[index + 1]
                if escaped == "u":
                    if index + 6 > length:
                        break
                    try:
                        out.append(chr(int(self.buffer[index + 2:index + 6], 16)))
                    except ValueError:
                        pass
                    index += 6
                    continue
                mapping = {
                    '"': '"', "\\": "\\", "/": "/",
                    "n": "\n", "t": "\t", "r": "\r",
                    "b": "\b", "f": "\f",
                }
                out.append(mapping.get(escaped, escaped))
                index += 2
                continue
            out.append(char)
            index += 1

        self.pos = index
        chunk = "".join(out)
        self.decoded += chunk
        return chunk


class LiveSpeech:
    """Reproduce frases en cuanto el LLM las produce.

    Mantiene la misma puerta de eco y el mismo barge-in que ``speak_text``,
    pero la cola de síntesis se alimenta desde el hilo del LLM.
    """

    _BOUNDARY_RE = re.compile(r'[.!?…]+["\'»”)]*(?=\s|$)')

    def __init__(self, language: str, story_mode: bool = False):
        self.language = language
        self.story_mode = story_mode
        self.stream = StreamingTTS(sample_rate=TTS_SAMPLE_RATE)
        self.stream.start()
        self.pending = ""
        self.first_audio_time: Optional[float] = None
        self.sentences = 0
        self.spoken_chars = 0
        self.muted = False

    def feed(self, text: str) -> None:
        if not text or self.muted:
            return
        self.spoken_chars += len(text)
        self.pending += text
        self._drain(final=False)

    def _drain(self, final: bool = False) -> None:
        while True:
            pending = self.pending
            if not pending.strip():
                self.pending = ""
                return

            if not final:
                matches = list(self._BOUNDARY_RE.finditer(pending))
                if matches:
                    cut = matches[-1].end()
                elif len(pending) > 240:
                    cut = pending.rfind(" ", 0, 220)
                    if cut <= 0:
                        cut = 220
                else:
                    return
            else:
                cut = len(pending)

            chunk = pending[:cut].strip()
            self.pending = pending[cut:].lstrip()
            if not chunk or self._is_noise(chunk):
                continue
            if self.first_audio_time is None:
                self.first_audio_time = time.perf_counter()
            self.stream.add_text(chunk, self.language)
            self.sentences += 1

    def _is_noise(self, text: str) -> bool:
        lowered = _fold_text(text).strip()
        if not lowered:
            return True
        # Metadatos que se colarían si el modelo ignora el esquema JSON.
        if any(
            marker in lowered
            for marker in (
                '"spoken"', '"language"', '"corrections"',
                '"vocabulary"', '"learning"',
            )
        ):
            return True
        # Despedidas cortas al final del cuento: no se leen en voz alta.
        if self.story_mode:
            words = lowered.split()
            if len(words) <= 14 and any(
                lowered.startswith(marker) for marker in _STORY_CHAT_MARKERS
            ):
                self.muted = True
                return True
        return False

    def flush(self, force: bool = True) -> None:
        self._drain(final=force)

    def play_until(
        self,
        done_event: threading.Event,
        cancel_event: threading.Event,
        timeout: float = 600.0,
    ) -> bool:
        """Reproduce y vigila barge-in hasta que el LLM y la cola terminan."""
        barge_triggered = False
        barge_frames: List[np.ndarray] = []
        epoch = 0
        detector = BARGE_IN_DETECTOR
        started = time.perf_counter()

        while True:
            if done_event.is_set() and self.stream.is_done():
                break
            if time.perf_counter() - started > timeout:
                print("[TTS] Aviso: tiempo de espera agotado")
                cancel_event.set()
                self.stream.interrupt()
                break
            if ENGINE_STOP_EVENT.is_set():
                cancel_event.set()
                self.stream.interrupt()
                break
            if has_typed_text():
                print("   [TEXTO] Mensaje escrito mientras hablo: corto el TTS")
                cancel_event.set()
                self.stream.interrupt()
                break
            if not (
                BARGE_IN_ENABLED
                and detector is not None
                and ACTIVE_MIC_STREAM is not None
            ):
                time.sleep(0.03)
                continue

            if self.stream.playback_epoch != epoch:
                epoch = self.stream.playback_epoch
                detector.rearm()

            frame = ACTIVE_MIC_STREAM.read(timeout=0.03)
            if frame is None:
                continue
            if not self.stream.playback_started.is_set():
                continue

            x = frame[:, 0] if frame.ndim == 2 else frame
            if detector.push(x):
                barge_triggered = True
                barge_frames = detector.take_frames()
                print("   [FULL DUPLEX] El usuario interrumpe: paro el TTS")
                cancel_event.set()
                self.stream.interrupt()
                ui_emit("status", "Te escucho…")
                break

        if barge_triggered:
            stash_barge_in_audio(barge_frames)
            self.stream.stop(timeout=2.0)
        else:
            self.stream.wait_until_done(timeout=15.0)
            self.stream.stop()
        return barge_triggered


def _stream_ollama_chat(
    payload: Dict[str, Any],
    speech: LiveSpeech,
    cancel_event: threading.Event,
) -> Dict[str, Any]:
    """Consume una respuesta de Ollama y la convierte en voz sobre la marcha."""
    import requests

    started = time.perf_counter()
    first_token: Optional[float] = None
    full = ""
    extractor = SpokenTextExtractor()
    error = ""
    response = None

    try:
        response = requests.post(
            "http://localhost:11434/api/chat",
            json=payload,
            stream=True,
            timeout=120,
        )
        if response.status_code != 200:
            raise RuntimeError(f"Ollama HTTP {response.status_code}")
        for line in response.iter_lines():
            if cancel_event.is_set():
                break
            if not line:
                continue
            try:
                chunk = json.loads(line.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                continue
            delta = chunk.get("message", {}).get("content", "")
            if delta:
                if first_token is None:
                    first_token = time.perf_counter()
                full += delta
                decoded = extractor.feed(delta)
                if decoded:
                    speech.feed(decoded)
            if chunk.get("done", False):
                break
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    finally:
        if response is not None:
            try:
                response.close()
            except Exception:
                pass

    return {
        "full": full,
        "first_token_s": (
            (first_token - started) if first_token is not None else None
        ),
        "full_s": time.perf_counter() - started,
        "error": error,
    }


# Ajustes autonomos: los que Emma aplica ella misma cuando detecta que un
# cuento salio mal o un recurso fallo. Se editan en caliente desde su propio
# flujo de mejora, sin necesidad de un reinicio manual.
SELF_ADJUSTMENTS: Dict[str, Any] = {
    "story_continuation_attempts": 2,
    "story_min_final_words": 340,
    "story_max_final_words": 420,
}
SELF_ADJUSTMENT_LOG: List[str] = []


def apply_self_adjustment(key: str, value: Any, reason: str = "") -> None:
    """Aplica un ajuste autonomo y lo registra."""
    SELF_ADJUSTMENTS[key] = value
    SELF_ADJUSTMENT_LOG.append(f"{key}={value} ({reason})")
    print(f"[AUTO] Emma ajusto '{key}' a {value} ({reason})")


def get_self_adjustment(key: str, default: Any) -> Any:
    return SELF_ADJUSTMENTS.get(key, default)


def _produce_response(
    payload: Dict[str, Any],
    speech: LiveSpeech,
    cancel_event: threading.Event,
    done_event: threading.Event,
    holder: Dict[str, Any],
    story_language: Optional[str] = None,
) -> None:
    """Hilo productor: LLM -> frases -> cola de TTS."""
    try:
        first = _stream_ollama_chat(payload, speech, cancel_event)
        holder.update(first)
        holder["passes"] = 1

        if cancel_event.is_set():
            return

        if story_language:
            spoken = clean_story_text(extract_spoken_text(first.get("full", "")))
            print(f"   [CUENTO] {len(spoken.split())} palabras en la primera pasada")
            speech.flush(force=False)

            attempts = 0
            while (
                len(spoken.split()) < get_self_adjustment("story_min_final_words", 340)
                and attempts < int(get_self_adjustment("story_continuation_attempts", 2))
                and not cancel_event.is_set()
            ):
                attempts += 1
                continuation = build_continuation_payload(
                    spoken, story_language, num_predict=900, stream=True
                )
                part = _stream_ollama_chat(continuation, speech, cancel_event)
                holder["full_s"] = holder.get("full_s", 0.0) + part.get(
                    "full_s", 0.0
                )
                holder["passes"] = holder.get("passes", 1) + 1
                extra = clean_story_text(
                    extract_spoken_text(part.get("full", ""))
                )
                if not extra:
                    break
                max_extra = max(90, 340 - len(spoken.split()) + 30)
                words = extra.split()
                has_ending = any(
                    marker in extra.lower() for marker in _STORY_END_MARKERS
                )
                if len(words) > max_extra and not has_ending:
                    cut = " ".join(words[:max_extra])
                    last_stop = max(
                        cut.rfind(". "),
                        cut.rfind("! "),
                        cut.rfind("? "),
                    )
                    if last_stop > 0:
                        cut = cut[:last_stop + 1]
                    extra = cut
                last_sentence = re.split(
                    r"(?<=[.!?])\s+", spoken.strip()
                )[-1].strip()
                if last_sentence and extra.startswith(last_sentence):
                    extra = extra[len(last_sentence):].lstrip()
                spoken = (spoken.rstrip() + "\n\n" + extra).strip()
                speech.flush(force=False)
                if any(
                    marker in extra.lower() for marker in _STORY_END_MARKERS
                ):
                    break
            holder["story_spoken"] = clean_story_text(spoken)
            final_story = clean_story_text(spoken)
            final_words = len(final_story.split())
            if final_words > int(get_self_adjustment("story_max_final_words", 420)):
                # Un cuento de dos minutos no debe pasarse: recortamos en un
                # punto final sin perder la resolucion.
                final_words_list = final_story.split()
                final_story = " ".join(final_words_list[:420])
                last_stop = max(
                    final_story.rfind(". "),
                    final_story.rfind("! "),
                    final_story.rfind("? "),
                )
                if last_stop > 0:
                    final_story = final_story[:last_stop + 1]
                holder["story_spoken"] = final_story
            spoken = final_story
            print(
                f"   [CUENTO] {len(final_story.split())} palabras finales"
            )

        if not cancel_event.is_set():
            speech.flush(force=True)
    finally:
        done_event.set()


def speak_text(spoken: str, language: str):
    """Sintetiza y reproduce una respuesta. Devuelve (primer audio ms, total ms)."""
    tts_start = time.perf_counter()
    streaming_tts = StreamingTTS(sample_rate=TTS_SAMPLE_RATE)
    streaming_tts.start()

    sentences = split_into_sentences(spoken)
    if not sentences:
        sentences = [spoken]

    print(f"   [TTS] {len(sentences)} oraciones para sintetizar")
    first_audio_time = None
    for index, sentence in enumerate(sentences):
        sentence = sentence.strip()
        if not sentence:
            continue
        print(f"   [TTS] Oración {index + 1}/{len(sentences)}: '{sentence[:50]}...'")
        streaming_tts.add_text(sentence, language)
        if first_audio_time is None:
            first_audio_time = time.perf_counter()

    # Full duplex: seguimos leyendo el micro mientras Emma habla. Si el usuario
    # habla de forma sostenida, cortamos el TTS y guardamos sus primeras
    # palabras para el siguiente turno.
    barge_triggered = False
    barge_frames = []
    epoch = 0
    detector = BARGE_IN_DETECTOR

    while not streaming_tts.is_done():
        if ENGINE_STOP_EVENT.is_set():
            streaming_tts.interrupt()
            break
        if has_typed_text():
            print("   [TEXTO] Mensaje escrito mientras hablo: corto el TTS")
            streaming_tts.interrupt()
            break
        if not (
            BARGE_IN_ENABLED
            and detector is not None
            and ACTIVE_MIC_STREAM is not None
        ):
            time.sleep(0.03)
            continue

        if streaming_tts.playback_epoch != epoch:
            epoch = streaming_tts.playback_epoch
            detector.rearm()

        frame = ACTIVE_MIC_STREAM.read(timeout=0.03)
        if frame is None:
            continue
        if not streaming_tts.playback_started.is_set():
            continue

        x = frame[:, 0] if frame.ndim == 2 else frame
        if detector.push(x):
            barge_triggered = True
            barge_frames = detector.take_frames()
            print("   [FULL DUPLEX] El usuario interrumpe: paro el TTS")
            streaming_tts.interrupt()
            ui_emit("status", "Te escucho…")
            break

    if barge_triggered:
        stash_barge_in_audio(barge_frames)
        streaming_tts.stop(timeout=2.0)
    else:
        streaming_tts.wait_until_done(timeout=60.0)
        streaming_tts.stop()

    tts_end = time.perf_counter()
    tts_ms = (tts_end - tts_start) * 1000
    tts_first_ms = (first_audio_time - tts_start) * 1000 if first_audio_time else 0.0
    print(f"   TTS first audio: {tts_first_ms:.0f}ms, total: {tts_ms:.0f}ms")
    return tts_first_ms, tts_ms


def apply_voice_prefs(prefs: Dict[str, Any]) -> Dict[str, Any]:
    """Activa un perfil de voz en caliente, sin reiniciar Emma."""
    global TTS_ENGLISH_VOICE, TTS_SPANISH_VOICE, TTS_SPEED, VOICE_PROFILE_ID
    TTS_ENGLISH_VOICE = prefs.get("voice_en") or TTS_ENGLISH_VOICE
    TTS_SPANISH_VOICE = prefs.get("voice_es") or TTS_SPANISH_VOICE
    TTS_SPEED = float(prefs.get("speed", TTS_SPEED))
    VOICE_PROFILE_ID = prefs.get("profile", VOICE_PROFILE_ID)
    if "tts" in globals():
        tts.voices["en"] = TTS_ENGLISH_VOICE
        tts.voices["es"] = TTS_SPANISH_VOICE
        tts.speed = TTS_SPEED
    print(
        f"   [VOZ] Perfil {VOICE_PROFILE_ID}: en={TTS_ENGLISH_VOICE}, "
        f"es={TTS_SPANISH_VOICE}, speed={TTS_SPEED:.2f}"
    )
    return prefs


def build_voice_reply(
    action: str, profile: Dict[str, Any], language: str, already_natural: bool = False
) -> str:
    label = emma_state.voice_profile_label(profile.get("profile"), language)
    if language == "en":
        if action == "like":
            return "I'm glad you like it. I'll keep this voice."
        if action == "natural" and already_natural:
            return (
                "I'm already using my warmest, most natural voice. "
                "If you want, ask me for another one."
            )
        if action == "slow":
            return "Okay, I'll speak a little slower. Is this better?"
        if action == "fast":
            return "Okay, I'll speak a little faster. Is this better?"
        return (
            f"Okay, I've changed my voice. This is my {label} voice now. "
            "Do you like it?"
        )

    if action == "like":
        return "Me alegra que te guste. Me quedo con esta voz."
    if action == "natural" and already_natural:
        return (
            "Ya estoy usando mi voz más natural y cálida. "
            "Si quieres, pídeme otra diferente."
        )
    if action == "slow":
        return "Vale, voy a hablar un poco más despacio. ¿Así está mejor?"
    if action == "fast":
        return "Vale, voy a hablar un poco más rápido. ¿Así está mejor?"
    return (
        f"Vale, he cambiado mi voz. Ahora es mi voz {label}. "
        "¿Te gusta o pruebo otra?"
    )


def handle_voice_request(
    user_text: str,
    stt_ms: float,
    user_language: str,
    active_language: str,
    turn_num: int,
    turn_start: float,
):
    """Cambia la voz si el usuario lo pide, sin pasar por el LLM."""
    if not EMMA_STATE_AVAILABLE:
        return None
    try:
        request = emma_state.detect_voice_request(user_text)
    except Exception as voice_error:
        print(f"   [VOZ] Error detectando la peticion: {voice_error}")
        return None
    if not request:
        return None

    language = LANGUAGE_PREFERENCE or active_language or user_language or "es"
    action = request.get("action", "")
    old = emma_state.get_voice_prefs()
    already_natural = action == "natural" and old.get("profile") == "warm"

    try:
        if action == "next":
            new = emma_state.cycle_voice_profile(1, language=user_language)
        elif action == "set":
            new = emma_state.set_voice_profile(request.get("profile", ""))
        elif action == "natural":
            new = emma_state.set_voice_profile("warm")
        elif action == "reset":
            new = emma_state.reset_voice_prefs()
        elif action == "slow":
            new = emma_state.set_voice_speed(float(old.get("speed", 0.95)) - 0.05)
        elif action == "fast":
            new = emma_state.set_voice_speed(float(old.get("speed", 0.95)) + 0.05)
        elif action == "like":
            new = old
        else:
            return None
    except Exception as voice_error:
        print(f"   [VOZ] Error aplicando el cambio: {voice_error}")
        return None

    apply_voice_prefs(new)
    spoken = build_voice_reply(action, new, language, already_natural)
    print(f"   [VOZ] Peticion '{action}' -> '{spoken[:70]}...' ({language})")

    ui_emit("assistant", spoken)
    ui_emit("status", "Emma está hablando…")
    try:
        tts_first_ms, _tts_ms = speak_text(spoken, language)
    except Exception as tts_error:
        print(f"   [VOZ] Error hablando la confirmacion: {tts_error}")
        return None

    if not FULL_DUPLEX:
        time.sleep(POST_TTS_DELAY_MS / 1000.0)

    total_ms = (time.perf_counter() - turn_start) * 1000
    result = TurnResult(
        turn=turn_num,
        stt_ms=stt_ms,
        llm_first_token_ms=0.0,
        llm_full_ms=0.0,
        tts_first_ms=tts_first_ms,
        total_ms=total_ms,
        user_text=user_text,
        assistant_spoken=spoken,
        assistant_language=language,
        corrections=[],
        vocabulary=[],
        user_language=user_language,
        learning={},
    )
    add_turn_to_history(user_text, spoken, language)
    turn_results.append(result)
    return result


def handle_song_request(
    user_text: str,
    stt_ms: float,
    user_language: str,
    active_language: str,
    turn_num: int,
    mic_stream,
    turn_start: float,
):
    """Graba unos segundos, identifica la cancion y responde sin pasar por el LLM."""
    if not SONG_ENABLED or song_recognizer is None:
        return None
    try:
        if not song_recognizer.is_song_request(user_text):
            return None
    except Exception:
        return None

    language = LANGUAGE_PREFERENCE or active_language or user_language or "es"
    if language == "en":
        cue = "Okay. Whistle or hum the chorus for a few seconds."
        listen_error = "I couldn't listen to the melody. Please try again."
    else:
        cue = "Vale. Silba o tararea el estribillo durante unos segundos."
        listen_error = "No he podido escuchar la melodía. Inténtalo otra vez."

    print("   [CANCIONES] Petición detectada; pido la melodía y grabo")
    ui_emit("status", "Escuchando la canción…")

    try:
        speak_text(cue, language)
        mic_stream.flush()
        time.sleep(0.15)
        wav_bytes = song_recognizer.record_from_stream(mic_stream, SONG_SECONDS)
        os.makedirs("logs", exist_ok=True)
        with open(os.path.join("logs", "ultima_cancion.wav"), "wb") as handle:
            handle.write(wav_bytes)
        ui_emit("status", "Identificando la canción…")
        match = song_recognizer.identify(wav_bytes)
        spoken = song_recognizer.describe(match, language)
        if match:
            print(
                f"   [CANCIONES] {match.get('source')}: "
                f"{match.get('title')} - {match.get('artist')}"
            )
        else:
            print("   [CANCIONES] Sin coincidencia")
    except Exception as exc:
        print(f"   [CANCIONES] Error: {exc}")
        spoken = listen_error

    ui_emit("assistant", spoken)
    ui_emit("status", "Emma está hablando…")
    try:
        tts_first_ms, tts_ms = speak_text(spoken, language)
    except Exception as exc:
        print(f"   [CANCIONES] Error en TTS: {exc}")
        tts_first_ms, tts_ms = 0.0, 0.0

    total_ms = (time.perf_counter() - turn_start) * 1000
    result = TurnResult(
        turn=turn_num,
        stt_ms=stt_ms,
        llm_first_token_ms=0.0,
        llm_full_ms=0.0,
        tts_first_ms=tts_first_ms,
        total_ms=total_ms,
        user_text=user_text,
        assistant_spoken=spoken,
        assistant_language=language,
        corrections=[],
        vocabulary=[],
        user_language=user_language,
        learning={},
    )
    add_turn_to_history(user_text, spoken, language)
    turn_results.append(result)
    print(f"   [CANCIONES] Respuesta: '{spoken[:80]}'")
    return result


def run_turn(turn_num: int, mic_stream, memoria):
    global stop_loop, LANGUAGE_PREFERENCE
    
    print(f"\n{'='*60}")
    print(f"TURNO {turn_num} INICIANDO")
    print(f"{'='*60}")
    
    turn_start = time.perf_counter()
    
    # --- ETAPA 1: Capturar audio con VAD o texto escrito ---
    print("1. Escuchando... (di algo y haz una pausa)")

    typed_text = take_typed_text()
    recorded_chunks = None
    voice_detected = False
    peak_rms = 0.0
    user_text = ""
    detected_lang = None
    stt_ms = 0.0

    if typed_text:
        print(f"1. Texto escrito: '{typed_text[:80]}'")
        user_text = typed_text
        detected_lang = detect_language(user_text)
    else:
        # Si el turno nace de una interrupcion, esas palabras ya estan capturadas.
        pending = take_barge_in_audio()
        if pending:
            print(f"   [FULL DUPLEX] Continúo con {len(pending)} frames ya capturados")
        else:
            mic_stream.flush()
        stop_event = ENGINE_STOP_EVENT
        recorded_chunks, voice_detected, peak_rms = record_audio_vad(
            vad_iterator, stop_event, mic_stream, initial_chunks=pending
        )

        # Puede haber llegado texto mientras escuchabamos: el texto gana.
        typed_text = take_typed_text()
        if typed_text:
            print(f"1. Texto escrito: '{typed_text[:80]}'")
            user_text = typed_text
            detected_lang = detect_language(user_text)
        elif not voice_detected or not recorded_chunks:
            print(f"   No se detecto voz (pico RMS: {peak_rms:.6f})")
            return None

    # --- ETAPA 2: Transcripcion (STT) ---
    if user_text:
        print("2. Texto directo: sin STT")
    else:
        print("2. Transcribiendo con faster-whisper...")

    try:
        if not user_text:
            full_audio = np.concatenate(recorded_chunks).astype(np.float32)

            timer.start()
            timer.mark_stt()

            user_text, detected_lang, _forced = stt.transcribe(
                full_audio, language=STT_LANGUAGE, beam_size=STT_BEAM_SIZE,
                vad_filter=STT_VAD_FILTER,
                fallback_languages=STT_FALLBACK_LANGUAGES
            )
            stt_end = time.perf_counter()
            stt_ms = (stt_end - turn_start) * 1000

            if not user_text or user_text.strip() == "":
                print("   Transcripcion vacia")
                return None

        print(f"   Usuario: '{user_text}' (idioma: {detected_lang})")

        # Preferencia de idioma explicita ("speak in English", "no Spanish"...)
        requested_language = None
        if EMMA_STATE_AVAILABLE:
            try:
                requested_language = emma_state.detect_language_request(user_text)
                if requested_language and requested_language != LANGUAGE_PREFERENCE:
                    LANGUAGE_PREFERENCE = requested_language
                    emma_state.set_language_preference(requested_language)
                    label = "INGLÉS" if requested_language == "en" else "ESPAÑOL"
                    print(f"   [IDIOMA] El usuario pide {label}; preferencia guardada")
            except Exception as lang_error:
                print(f"   [IDIOMA] Error detectando peticion: {lang_error}")

        user_language = requested_language or detected_lang or detect_language(user_text)
        active_language = LANGUAGE_PREFERENCE or detected_lang or user_language
        if LANGUAGE_PREFERENCE:
            print(f"   [IDIOMA] Respuesta forzada en: {LANGUAGE_PREFERENCE}")

        ui_emit("user", user_text)

        # Cambio de voz bajo demanda: respuesta directa, sin pasar por el LLM.
        voice_result = handle_voice_request(
            user_text,
            stt_ms,
            user_language,
            active_language,
            turn_num,
            turn_start,
        )
        if voice_result is not None:
            return voice_result

        # Reconocimiento de cancion bajo demanda: no pasa por el LLM.
        if SONG_ENABLED:
            song_result = handle_song_request(
                user_text,
                stt_ms,
                user_language,
                active_language,
                turn_num,
                mic_stream,
                turn_start,
            )
            if song_result is not None:
                return song_result

        ui_emit("status", "Emma está pensando…")
        
    except Exception as e:
        print(f"Error en STT: {e}")
        import traceback
        traceback.print_exc()
        return None
    
# --- ETAPA 3: LLM Streaming ---
    print("3. LLM streaming...")

    try:
        story_mode = is_story_request(user_text)
        web_sources = []
        story_material = ""

        if story_mode:
            print("   [CUENTO] Peticion detectada: busco material curado")
            ui_emit("status", "Buscando material para el cuento…")
            story_context = None
            if WEB_ENABLED:
                try:
                    story_context = web_tools.gather_story_context(
                        user_text,
                        lang=active_language,
                        config=WEB_CONFIG,
                    )
                except Exception as story_error:
                    print(f"   [CUENTO] Error buscando material: {story_error}")
            if story_context and story_context.get("sources"):
                story_material = web_tools.build_story_prompt_block(story_context)
                web_sources = story_context["sources"]
                first_source = web_sources[0]
                print(
                    "   [CUENTO] Fuente curada: "
                    f"{first_source['site']} - {first_source['title']}"
                )
            else:
                print("   [CUENTO] Sin material curado; narro con conocimiento propio")
            ui_emit("status", "Emma está pensando…")

        system_prompt = get_system_prompt_with_context(
            user_text,
            active_language,
            story=story_mode,
            story_material=story_material,
        )

        # --- ETAPA 3a: contexto web (solo si la pregunta lo requiere) ---
        if WEB_ENABLED and not story_mode and web_tools.should_search(user_text):
            print("   [WEB] Consultando fuentes...")
            ui_emit("status", "Consultando fuentes…")
            web_started = time.perf_counter()
            try:
                web_context = web_tools.gather_context(
                    user_text,
                    lang=detected_lang or "es",
                    previous=(history.user_texts[-1] if history.user_texts else ""),
                    config=WEB_CONFIG,
                )
            except Exception as web_error:
                print(f"   [WEB] Error: {web_error}")
                web_context = None

            if web_context and web_context.get("sources"):
                system_prompt += web_tools.build_prompt_block(web_context)
                web_sources = web_context["sources"]
                web_ms = (time.perf_counter() - web_started) * 1000
                print(f"   [WEB] {len(web_sources)} fuentes consultadas en {web_ms:.0f} ms")
            else:
                print("   [WEB] Sin resultados; respondo con conocimiento propio")
            ui_emit("status", "Emma está pensando…")

        messages = [{"role": "system", "content": system_prompt}]

        for ut, ar, al in zip(
            list(history.user_texts)[-3:],
            list(history.assistant_responses)[-3:],
            list(history.assistant_languages)[-3:]
        ):
            messages.append({"role": "user", "content": ut})
            messages.append({"role": "assistant", "content": ar})

        messages.append({"role": "user", "content": user_text})

        llm_start = time.perf_counter()
        tts_start = time.perf_counter()
        speech_language = LANGUAGE_PREFERENCE or active_language
        speech = LiveSpeech(speech_language, story_mode=story_mode)
        cancel_event = threading.Event()
        done_event = threading.Event()
        holder: Dict[str, Any] = {}

        payload = {
            "model": OLLAMA_MODEL,
            "messages": messages,
            "stream": True,
            "format": LLM_RESPONSE_SCHEMA,
            "keep_alive": LLM_KEEP_ALIVE,
            "options": {
                "temperature": TEMPERATURE,
                "num_predict": STORY_FIRST_PASS_TOKENS if story_mode else MAX_TOKENS,
                "num_ctx": LLM_NUM_CTX,
            },
        }

        print(f"   [LLM] Usando modelo local (Ollama): {OLLAMA_MODEL}")

        producer = threading.Thread(
            target=_produce_response,
            args=(
                payload,
                speech,
                cancel_event,
                done_event,
                holder,
                speech_language if story_mode else None,
            ),
            daemon=True,
        )
        producer.start()

        ui_emit("status", "Emma está hablando…")
        barge_triggered = speech.play_until(
            done_event=done_event, cancel_event=cancel_event
        )
        producer.join(timeout=10.0)

        full_response = holder.get("full", "")
        llm_error = holder.get("error", "")
        llm_end = time.perf_counter()
        llm_full_ms = (llm_end - llm_start) * 1000
        if holder.get("first_token_s") is not None:
            first_token_time = llm_start + holder["first_token_s"]
        else:
            first_token_time = llm_start
        llm_first_token_ms = (first_token_time - llm_start) * 1000

        if llm_error and not full_response:
            raise Exception(f"Ollama error: {llm_error}")

        # Parsear respuesta JSON
        corrections = []
        vocabulary = []
        learning = {}
        assistant_language = LANGUAGE_PREFERENCE or "es"
        parsed_spoken = extract_spoken_text(full_response)

        spoken = parsed_spoken
        if story_mode:
            spoken = clean_story_text(holder.get("story_spoken") or parsed_spoken)

        try:
            json_start = full_response.find('{')
            json_end = full_response.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = full_response[json_start:json_end]
                parsed = json.loads(json_str)
                parsed_spoken = parsed.get("spoken", full_response)
                corrections = parsed.get("corrections", []) or []
                vocabulary = parsed.get("vocabulary", []) or []
                learning = parsed.get("learning") or {}
                if not isinstance(learning, dict):
                    learning = {}
                # La preferencia explicita manda sobre lo que diga el modelo.
                assistant_language = LANGUAGE_PREFERENCE or detect_language(parsed_spoken)
            else:
                parsed_spoken = extract_spoken_text(full_response)
                assistant_language = LANGUAGE_PREFERENCE or detect_language(parsed_spoken)
        except json.JSONDecodeError:
            parsed_spoken = extract_spoken_text(full_response)
            assistant_language = LANGUAGE_PREFERENCE or detect_language(parsed_spoken)

        spoken = parsed_spoken
        if story_mode:
            spoken = clean_story_text(holder.get("story_spoken") or parsed_spoken)

        if not isinstance(spoken, str) or not spoken.strip():
            spoken = extract_spoken_text(full_response)
        if not isinstance(spoken, str) or not spoken.strip():
            raise Exception("Respuesta del LLM vacia")

        if LANGUAGE_PREFERENCE and assistant_language != LANGUAGE_PREFERENCE:
            assistant_language = LANGUAGE_PREFERENCE
        if story_mode and not LANGUAGE_PREFERENCE:
            assistant_language = speech_language
        elif not story_mode:
            assistant_language = LANGUAGE_PREFERENCE or detect_language(spoken)

        print(f"   LLM: '{spoken[:60]}...' ({assistant_language})")
        ui_emit("assistant", spoken)
        if web_sources:
            ui_emit("sources", json.dumps(web_sources, ensure_ascii=False))
        ui_emit("status", "Emma está hablando…")
        print(f"   LLM first token: {llm_first_token_ms:.0f}ms, full: {llm_full_ms:.0f}ms")

    except Exception as e:
        print(f"Error en LLM: {e}")
        import traceback
        traceback.print_exc()
        return None

    # --- ETAPA 4: TTS Streaming (ya en marcha desde el hilo del LLM) ---
    print("4. TTS con Kokoro en streaming...")

    tts_ms = max(0.0, (time.perf_counter() - tts_start) * 1000)
    tts_first_ms = (
        (speech.first_audio_time - tts_start) * 1000
        if speech.first_audio_time is not None
        else 0.0
    )
    print(f"   TTS: '{spoken[:50]}...' ({assistant_language})")
    speech.stream.stop()

    # --- ETAPA 5: Pausa entre turnos ---
    if not FULL_DUPLEX:
        print("5. Pausa half-duplex...")
        print("   Microfono desactivado durante la reproduccion TTS")
        time.sleep(POST_TTS_DELAY_MS / 1000.0)
    else:
        # Respiro minimo para descartar el eco final de Emma.
        time.sleep(0.10)
    
    # --- COMPLETAR TURNO ---
    turn_total = time.perf_counter() - turn_start
    total_ms = turn_total * 1000
    
    result = TurnResult(
        turn=turn_num,
        stt_ms=stt_ms,
        llm_first_token_ms=llm_first_token_ms,
        llm_full_ms=llm_full_ms,
        tts_first_ms=tts_first_ms,
        total_ms=total_ms,
        user_text=user_text,
        assistant_spoken=spoken,
        assistant_language=assistant_language,
        corrections=corrections,
        vocabulary=vocabulary,
        user_language=user_language,
        learning=learning
    )

    # Registrar el turno en el perfil de aprendizaje persistente.
    if EMMA_STATE_AVAILABLE:
        try:
            profile = emma_state.load_learning()
            emma_state.record_turn(
                profile,
                corrections=corrections,
                learning=learning,
                user_text=user_text,
                assistant_text=spoken,
            )
            totals = profile.get("totals", {})
            print(
                f"   [PERFIL] Turnos: {totals.get('turns', 0)} | "
                f"correcciones: {totals.get('corrections', 0)}"
            )
        except Exception as profile_error:
            print(f"   [PERFIL] Error registrando el turno: {profile_error}")
    
    add_turn_to_history(user_text, spoken, assistant_language)
    turn_results.append(result)
    
    print(f"\n{'='*60}")
    print(f"TURNO {turn_num} - TIEMPOS:")
    print(f"   STT:          {stt_ms:.0f}ms")
    print(f"   LLM first:    {llm_first_token_ms:.0f}ms")
    print(f"   LLM full:     {llm_full_ms:.0f}ms")
    print(f"   TTS first:    {tts_first_ms:.0f}ms")
    print(f"   TOTAL:        {total_ms:.0f}ms")
    print(f"{'='*60}")
    
    return result


def main():
    global stop_loop, total_turns, ACTIVE_MIC_STREAM
    
    def signal_handler(signum, frame):
        global stop_loop
        print("\nCtrl+C detectado. Finalizando...")
        stop_loop = True
    
    if threading.current_thread() is threading.main_thread():
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    print("="*60)
    print("Emma Bilingue - Voice Loop Starting")
    print("="*60)
    print(f"Model: {OLLAMA_MODEL} (local Ollama)")
    print(f"History: {MAX_HISTORY} turns")
    print(f"VAD threshold: {VAD_THRESHOLD}")
    print(f"TTS voices: en={TTS_ENGLISH_VOICE}, es={TTS_SPANISH_VOICE} (perfil {VOICE_PROFILE_ID}, speed {TTS_SPEED:.2f})")
    print(f"Modo: {'full-duplex (barge-in)' if FULL_DUPLEX else 'half-duplex'}, Post-TTS delay: {POST_TTS_DELAY_MS}ms")
    print("="*60)
    print("Speak and the system will transcribe -> LLM -> voice")
    print("Press Ctrl+C to stop after current turn")
    print("="*60)
    
    os.makedirs("logs", exist_ok=True)
    
    # --- Cargar memoria persistente al iniciar ---
    memoria = cargar_memoria()
    
    # --- Inicializar MicStream una sola vez ---
    input_device = AUDIO_CONFIG.get("input_device", 1)
    mic_stream = MicStream(
        sample_rate=AUDIO_SAMPLE_RATE,
        block_size=AUDIO_CONFIG.get("block_size", 512),
        device=input_device,
        channels=AUDIO_CONFIG.get("channels", 1)
    )
    mic_stream.start()
    ACTIVE_MIC_STREAM = mic_stream
    
    turn_num = 0

    # Precarga en segundo plano las fuentes narrativas curadas para cuentos.
    def _prefetch_story_sources_task() -> None:
        try:
            web_tools.prefetch_story_sources(langs=("es", "en"))
        except Exception as prefetch_error:
            print(f"[CUENTO] Precarga de fuentes fallo: {prefetch_error}")

    _prefetch_thread = threading.Thread(
        target=_prefetch_story_sources_task, daemon=True
    )
    _prefetch_thread.start()

    try:
        while not stop_loop and not ENGINE_STOP_EVENT.is_set():
            turn_num += 1
            if ENGINE_STOP_EVENT.is_set():
                break
            if turn_num > MAX_CONVERSATION_TURNS:
                print(f"Limite de {MAX_CONVERSATION_TURNS} turnos alcanzado")
                break
            
            try:
                result = run_turn(turn_num, mic_stream, memoria)
            except Exception as e:
                print(f"[ERROR] Turno {turn_num} falló: {e}")
                import traceback
                traceback.print_exc()
                print("Continuando con siguiente turno...")
                # Guardar memoria aunque fallen los turns
                if MEMORY_ENABLED:
                    guardar_memoria(memoria)
                continue
            
            if ENGINE_STOP_EVENT.is_set():
                break
            if result is None:
                print("Turn incomplete, continuing...")
                # Guardar memoria aún si el turno está incompleto
                if MEMORY_ENABLED:
                    # Añadir entrada vacía o skip
                    pass
                continue
            
            # Guardar memoria después de cada turno exitoso
            if MEMORY_ENABLED:
                memoria.append({
                    "turno": result.turn,
                    "usuario": result.user_text,
                    "asistente": result.assistant_spoken,
                    "idioma_usuario": result.user_language,
                    "marcas_voz": result.corrections if result.corrections else [],
                    "aprendizaje": result.learning if result.learning else {},
                })
                guardar_memoria(memoria)
            
            # Guardar CSV al final (solo si hay resultados acumulados)
            # save_latency_csv(turn_results, "logs/latency.csv")
            
            if not has_typed_text():
                print("Pause between turns...")
                ui_emit("status", "Preparada para escucharte…")
                # Full duplex: el respiro minimo es suficiente; no hace falta
                # la pausa de half-duplex de un segundo.
                pause_s = 0.2 if FULL_DUPLEX else 1.0
                ENGINE_STOP_EVENT.wait(pause_s)
    except KeyboardInterrupt:
        print("\nKeyboard interrupt")
    finally:
        mic_stream.stop()
        ENGINE_FINISHED_EVENT.set()
        ui_emit("status", "Emma se ha detenido.")
    
    # Guardar memoria final y reporte
    if MEMORY_ENABLED and memoria:
        guardar_memoria(memoria)
        print(f"\nMemoria guardada: {len(memoria)} turnos en {MEMORY_PATH}")
    
    # ==========================================
    # Final summary
    # ==========================================
    
    print("\n" + "="*60)
    print("FINAL SUMMARY - Conversation Ended")
    print("="*60)
    
    if turn_results:
        avg_stt = sum(r.stt_ms for r in turn_results) / len(turn_results)
        avg_llm_first = sum(r.llm_first_token_ms for r in turn_results) / len(turn_results)
        avg_llm_full = sum(r.llm_full_ms for r in turn_results) / len(turn_results)
        avg_tts_first = sum(r.tts_first_ms for r in turn_results) / len(turn_results)
        avg_total = sum(r.total_ms for r in turn_results) / len(turn_results)
        
        print(f"Total turns: {len(turn_results)}")
        print(f"   Avg STT:          {avg_stt:.0f}ms")
        print(f"   Avg LLM first:    {avg_llm_first:.0f}ms")
        print(f"   Avg LLM full:     {avg_llm_full:.0f}ms")
        print(f"   Avg TTS first:    {avg_tts_first:.0f}ms")
        print(f"   Avg TOTAL:        {avg_total:.0f}ms")
        
        save_latency_csv(turn_results, "logs/latency.csv")
        print(f"\nData saved to: logs/latency.csv")
    else:
        print("No turns completed")
    
    print("\nTurn details:")
    for r in turn_results:
        print(f"   Turn {r.turn}: STT={r.stt_ms:.0f}ms LLM1={r.llm_first_token_ms:.0f}ms LLMF={r.llm_full_ms:.0f}ms TTS1={r.tts_first_ms:.0f}ms Tot={r.total_ms:.0f}ms | '{r.user_text[:30]}...' -> '{r.assistant_spoken[:30]}...' ({r.assistant_language})")
    
    print("="*60)


class ConversationWindow:
    """Interfaz ligera de Emma. Tkinter se actualiza solo desde el hilo principal."""
    def __init__(self):
        import tkinter as tk
        from tkinter import ttk

        self.tk = tk
        self.root = tk.Tk()
        self.root.title("Emma | Asistente personal")
        self.root.geometry("1180x800")
        self.root.minsize(760, 560)
        self.root.configure(bg="#f4f6f9")
        self.root.option_add("*Font", ("Segoe UI", 10))
        self.closing = False
        self._finished_handled = False
        self._welcome_visible = True
        self._message_cards = []  # (tarjeta, etiqueta de texto, tipo)
        self._next_row = 0

        self.colors = {
            "window": "#f4f6f9",
            "white": "#ffffff",
            "border": "#e1e6ed",
            "text": "#172033",
            "muted": "#64748b",
            "blue": "#1769aa",
            "user_card": "#eaf3fc",
            "emma_card": "#ffffff",
        }

        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure(
            "Emma.Vertical.TScrollbar",
            background="#d5dde7", troughcolor="#f4f6f9",
            bordercolor="#f4f6f9", arrowcolor="#64748b",
        )

        # Cabecera compacta.
        header = tk.Frame(self.root, bg=self.colors["white"], height=68)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header, text="Emma", bg=self.colors["white"], fg="#152238",
            font=("Segoe UI", 20, "bold")
        ).pack(side="left", padx=(28, 8), pady=12)
        tk.Label(
            header, text="ASISTENTE DE VOZ Y TEXTO", bg=self.colors["white"],
            fg="#64748b", font=("Segoe UI", 8, "bold")
        ).pack(side="left", pady=(18, 12))
        self.header_status = tk.Label(
            header, text="●  INICIANDO", bg="#edf4fb", fg="#155d96",
            padx=13, pady=7, font=("Segoe UI", 9, "bold")
        )
        self.header_status.pack(side="right", padx=26, pady=15)
        tk.Frame(self.root, bg=self.colors["border"], height=1).pack(fill="x")

        # Área principal: un único panel de conversación con scroll.
        body = tk.Frame(self.root, bg=self.colors["window"])
        body.pack(fill="both", expand=True, padx=24, pady=(18, 14))
        title_row = tk.Frame(body, bg=self.colors["window"])
        title_row.pack(fill="x", pady=(0, 10))
        tk.Label(
            title_row, text="Conversación", bg=self.colors["window"],
            fg="#1e293b", font=("Segoe UI", 12, "bold")
        ).pack(side="left")
        tk.Label(
            title_row, text="  ·  Historial de voz", bg=self.colors["window"],
            fg=self.colors["muted"], font=("Segoe UI", 9)
        ).pack(side="left", pady=(2, 0))

        chat_shell = tk.Frame(
            body, bg=self.colors["white"],
            highlightthickness=1, highlightbackground=self.colors["border"]
        )
        chat_shell.pack(fill="both", expand=True)
        chat_shell.rowconfigure(0, weight=1)
        chat_shell.columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(
            chat_shell, bg=self.colors["white"], highlightthickness=0,
            borderwidth=0
        )
        scrollbar = ttk.Scrollbar(
            chat_shell, orient="vertical", command=self.canvas.yview,
            style="Emma.Vertical.TScrollbar"
        )
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns", padx=(0, 4), pady=5)

        self.messages_frame = tk.Frame(self.canvas, bg=self.colors["white"])
        self.messages_window = self.canvas.create_window(
            (0, 0), window=self.messages_frame, anchor="nw"
        )
        self.messages_frame.grid_columnconfigure(0, weight=1)
        self.messages_frame.bind("<Configure>", self._update_scroll_region)
        self.canvas.bind("<Configure>", self._resize_messages)
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        self.welcome = tk.Label(
            self.messages_frame,
            text=(
                "Bienvenido a Emma\n\n"
                "Habla conmigo en español o inglés.\n"
                "También puedes escribirme aquí abajo y pulsar Enter.\n"
                "Silba o tararea una canción y te digo cuál es.\n"
                "Pídeme cambiar de voz si no te gusta cómo suena."
            ),
            bg=self.colors["white"], fg="#64748b",
            font=("Segoe UI", 12), justify="center"
        )
        self.welcome.grid(row=0, column=0, pady=90, padx=20)

        # Pie discreto con estado operativo y salida.
        footer = tk.Frame(self.root, bg=self.colors["white"], height=54)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)
        tk.Frame(self.root, bg=self.colors["border"], height=1).pack(
            fill="x", side="bottom"
        )
        self.status_var = tk.StringVar(value="Iniciando los componentes de Emma…")
        self.status_dot = tk.Label(
            footer, text="●", bg=self.colors["white"], fg="#1769aa",
            font=("Segoe UI", 10)
        )
        self.status_dot.pack(side="left", padx=(26, 9))
        self.status_label = tk.Label(
            footer, textvariable=self.status_var, bg=self.colors["white"],
            fg="#475569", font=("Segoe UI", 9), anchor="w"
        )
        self.status_label.pack(side="left", fill="x", expand=True)
        self.close_button = tk.Button(
            footer, text="Cerrar Emma", command=self.request_close,
            bg="#1769aa", fg="#ffffff", activebackground="#12578f",
            activeforeground="#ffffff", relief="flat", borderwidth=0,
            padx=17, pady=8, font=("Segoe UI", 9, "bold"), cursor="hand2"
        )
        self.close_button.pack(side="right", padx=22, pady=8)

        # Barra de escritura: misma conversación que la voz, sin micrófono.
        composer = tk.Frame(self.root, bg=self.colors["white"])
        composer.pack(fill="x", side="bottom")
        tk.Label(
            composer, text="ESCRIBIR", bg=self.colors["white"],
            fg=self.colors["muted"], font=("Segoe UI", 8, "bold")
        ).pack(side="left", padx=(26, 10), pady=13)
        self.text_entry = tk.Entry(
            composer, bg="#f7f9fc", fg=self.colors["text"],
            insertbackground=self.colors["text"], relief="flat",
            highlightthickness=1, highlightbackground=self.colors["border"],
            highlightcolor="#1769aa", font=("Segoe UI", 11)
        )
        self.text_entry.pack(
            side="left", fill="x", expand=True, ipady=8, pady=10
        )
        self.text_entry.bind("<Return>", self.send_typed_message)
        self.send_button = tk.Button(
            composer, text="Enviar", command=self.send_typed_message,
            bg="#1769aa", fg="#ffffff", activebackground="#12578f",
            activeforeground="#ffffff", relief="flat", borderwidth=0,
            padx=18, pady=7, font=("Segoe UI", 9, "bold"), cursor="hand2"
        )
        self.send_button.pack(side="right", padx=(10, 26), pady=10)
        tk.Label(
            composer, text="Enter para enviar", bg=self.colors["white"],
            fg=self.colors["muted"], font=("Segoe UI", 8)
        ).pack(side="right", pady=10)

        self.root.protocol("WM_DELETE_WINDOW", self.request_close)
        self.root.after(150, self.poll_events)
        self.root.after(300, self.text_entry.focus_set)

    def send_typed_message(self, _event=None):
        """Envía el texto escrito al mismo motor que procesa la voz."""
        text = self.text_entry.get().strip()
        if not text:
            return "break"
        if not submit_typed_text(text):
            return "break"

        self.text_entry.delete(0, "end")
        self.status_var.set("Mensaje enviado. Emma lo está procesando…")
        try:
            self.header_status.configure(
                text="●  PROCESANDO", fg="#8a5a00", bg="#fff4d9"
            )
            self.status_dot.configure(fg="#c58a16")
        except Exception:
            pass
        self.text_entry.focus_set()
        return "break"

    def _update_scroll_region(self, _event=None):
        try:
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        except Exception:
            pass

    def _card_padding(self, width, kind):
        """Margenes laterales de la tarjeta segun quien habla."""
        side = max(70, int(width * 0.14))
        if kind == "user":
            return side, 24
        return 24, side

    def _card_wraplength(self, width, kind):
        """Ancho util real del texto dentro de la tarjeta."""
        left, right = self._card_padding(width, kind)
        return max(200, width - left - right - 34)

    def _resize_messages(self, event):
        width = max(event.width, 320)
        self.canvas.itemconfigure(self.messages_window, width=width)
        for card, label, kind in self._message_cards:
            left, right = self._card_padding(width, kind)
            try:
                card.grid_configure(padx=(left, right))
                label.configure(wraplength=self._card_wraplength(width, kind))
            except Exception:
                continue
        self.root.after_idle(self._update_scroll_region)

    def _on_mousewheel(self, event):
        if self.canvas.winfo_exists():
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def append_message(self, speaker, message):
        message = (message or "").strip()
        if not message:
            return
        if self._welcome_visible:
            self.welcome.destroy()
            self._welcome_visible = False

        row = self._next_row
        self._next_row += 1
        is_user = speaker == "TÚ"
        is_sources = speaker == "FUENTES"
        kind = "user" if is_user else ("sources" if is_sources else "emma")
        label_text = {"TÚ": "TÚ", "FUENTES": "FUENTES WEB"}.get(speaker, "EMMA")
        if is_sources:
            card_bg = "#f7f9fc"
            card_fg = "#475569"
            accent = "#64748b"
            card_border = "#e5eaf1"
            body_font = ("Segoe UI", 9)
        else:
            card_bg = self.colors["user_card"] if is_user else self.colors["emma_card"]
            card_fg = "#18324b" if is_user else self.colors["text"]
            accent = "#1769aa" if is_user else "#16806a"
            card_border = "#d7e6f4" if is_user else self.colors["border"]
            body_font = ("Segoe UI", 11)

        width = self.canvas.winfo_width()
        if width < 200:
            width = 1100
        left, right = self._card_padding(width, kind)

        card = self.tk.Frame(
            self.messages_frame, bg=card_bg,
            highlightthickness=1,
            highlightbackground=card_border,
        )
        card.grid(
            row=row, column=0, sticky="e" if is_user else "w",
            padx=(left, right), pady=(10, 3),
        )

        tk = self.tk
        tk.Label(
            card, text=label_text,
            bg=card_bg, fg=accent, font=("Segoe UI", 8, "bold"),
            anchor="w",
        ).pack(fill="x", padx=14, pady=(9, 2))
        body_label = tk.Label(
            card, text=message, bg=card_bg, fg=card_fg,
            font=body_font, justify="left", anchor="w",
            wraplength=self._card_wraplength(width, kind),
            padx=14, pady=0,
        )
        body_label.pack(fill="x", pady=(0, 10))
        self._message_cards.append((card, body_label, kind))
        self.canvas.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self.canvas.yview_moveto(1.0)

    def poll_events(self):
        """Consume eventos sin permitir que un fallo visual detenga el sondeo."""
        try:
            while True:
                try:
                    event_type, payload = UI_EVENTS.get_nowait()
                except queue.Empty:
                    break

                try:
                    if event_type == "user":
                        self.append_message("TÚ", payload)
                    elif event_type == "assistant":
                        self.append_message("EMMA", payload)
                    elif event_type == "sources":
                        try:
                            sources = json.loads(payload)
                            lines = []
                            for source in sources:
                                site = source.get("site") or "web"
                                title = (source.get("title") or "").strip()
                                url = (source.get("url") or "").strip()
                                if len(url) > 85:
                                    url = url[:82] + "…"
                                lines.append(f"- {site}: {title}\n  {url}")
                            if lines:
                                self.append_message("FUENTES", "\n".join(lines))
                        except Exception as source_error:
                            print(f"[UI] Error mostrando fuentes: {source_error}")
                    elif event_type == "status":
                        self.status_var.set(payload)
                        lower = payload.lower()
                        if "escuch" in lower or "preparada" in lower:
                            self.header_status.configure(
                                text="●  ESCUCHANDO", fg="#155d96", bg="#edf4fb"
                            )
                            self.status_dot.configure(fg="#1769aa")
                        elif "pens" in lower or "proces" in lower or "consult" in lower or "busc" in lower:
                            self.header_status.configure(
                                text="●  PROCESANDO", fg="#8a5a00", bg="#fff4d9"
                            )
                            self.status_dot.configure(fg="#c58a16")
                        elif "hablando" in lower:
                            self.header_status.configure(
                                text="●  HABLANDO", fg="#176b55", bg="#e4f5ef"
                            )
                            self.status_dot.configure(fg="#16806a")
                except Exception as event_error:
                    # Un error al dibujar un mensaje no debe detener futuros eventos.
                    print(f"[UI] Error mostrando evento '{event_type}': {event_error}")
                    try:
                        self.status_var.set("Aviso: no se pudo mostrar un mensaje.")
                    except Exception:
                        pass

            if ENGINE_FINISHED_EVENT.is_set() and not self._finished_handled:
                self._finished_handled = True
                self.status_var.set("Emma se ha detenido. Puedes cerrar esta ventana.")
                self.header_status.configure(
                    text="●  DETENIDA", fg="#a33b3b", bg="#fdecec"
                )
                self.close_button.configure(
                    text="Salir", command=self.root.destroy
                )
        except Exception as poll_error:
            print(f"[UI] Error en el sondeo de eventos: {poll_error}")
        finally:
            # Mantener vivo el sondeo aunque falle un evento o un widget.
            try:
                if self.root.winfo_exists():
                    self.root.after(150, self.poll_events)
            except Exception:
                pass

    def request_close(self):
        if ENGINE_FINISHED_EVENT.is_set():
            self.root.destroy()
            return
        if not self.closing:
            self.closing = True
            self.status_var.set("Cerrando Emma al terminar la operación actual…")
            self.header_status.configure(
                text="●  CERRANDO", fg="#8a5a00", bg="#fff4d9"
            )
            self.close_button.configure(state="disabled")
            global stop_loop
            stop_loop = True
            ENGINE_STOP_EVENT.set()


def run_engine():
    try:
        main()
    except Exception as exc:
        print(f"[FATAL] Emma terminó con un error: {exc}")
        import traceback
        traceback.print_exc()
        ui_emit("status", f"Error de Emma: {exc}")
        ENGINE_FINISHED_EVENT.set()


def cargar_memoria():
    """Carga la memoria persistente desde memoria_emma.json si existe."""
    memoria_path = MEMORY_PATH
    if os.path.exists(memoria_path):
        try:
            with open(memoria_path, "r", encoding="utf-8") as f:
                memoria = json.load(f)
            print(f"Memoria cargada: {len(memoria)} turnos previos")
            return memoria
        except Exception as e:
            print(f"[WARN] No se pudo cargar memoria: {e}")
    return []


def guardar_memoria(memoria):
    """Guarda el historial de conversaciones en memoria_emma.json."""
    memoria_path = MEMORY_PATH
    try:
        target = Path(memoria_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_suffix(target.suffix + ".tmp")
        with open(temp, "w", encoding="utf-8") as f:
            json.dump(memoria, f, ensure_ascii=False, indent=4)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, target)
    except Exception as e:
        print(f"[WARN] No se pudo guardar memoria: {e}")


def cambiar_voz(nueva_voz: str):
    """Compatibilidad: cambia la voz por perfil o por nombre de voz Kokoro."""
    if not EMMA_STATE_AVAILABLE:
        print("[VOZ] El estado persistente no esta disponible")
        return None

    key = str(nueva_voz or "").strip().lower()
    aliases = {
        "warm": "warm", "natural": "warm", "calida": "warm", "cálida": "warm",
        "af_heart": "warm", "ef_dora": "warm",
        "soft": "soft", "suave": "soft", "af_nicole": "soft",
        "bright": "bright", "alegre": "bright", "af_bella": "bright",
        "british": "british", "britanica": "british", "británica": "british",
        "bf_emma": "british",
        "male": "male", "masculino": "male", "hombre": "male",
        "am_michael": "male", "em_alex": "male",
        "male_deep": "male_deep", "grave": "male_deep",
        "am_onyx": "male_deep", "em_santa": "male_deep",
        "en": "warm", "es": "warm", "ingles": "warm", "inglés": "warm",
        "espanol": "warm", "español": "warm",
    }
    profile_id = aliases.get(key)
    if not profile_id:
        print(f"[VOZ] Opcion no reconocida: {nueva_voz}")
        return None
    prefs = emma_state.set_voice_profile(profile_id)
    apply_voice_prefs(prefs)
    return prefs


def consultar_memoria(texto_usuario: str) -> str:
    """Consulta la memoria de conversaciones previas para no repetir información."""
    resultados = []
    for entrada in memoria_emma:
        if texto_usuario.lower() in entrada.get("usuario", "").lower():
            resultados.append(entrada)
    return resultados


# Cargar memoria persistente al iniciar
memoria_emma = cargar_memoria()
historial_path = "memoria_emma.json"

if __name__ == "__main__":
    try:
        conversation_window = ConversationWindow()
        engine_thread = threading.Thread(target=run_engine, name="EmmaEngine", daemon=True)
        engine_thread.start()
        conversation_window.root.mainloop()
    except Exception as exc:
        print(f"No se pudo iniciar la ventana de Emma: {exc}")
        raise