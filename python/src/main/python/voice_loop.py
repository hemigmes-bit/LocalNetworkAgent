#!/usr/bin/env python3
"""
Emma Bilingüe - Voice Loop

Pipeline completo: VAD -> STT -> LLM streaming -> TTS -> Altavoz
Repite hasta Ctrl+C.

Flujo: Silero VAD detecta fin de frase -> faster-whisper (GPU) transcribe ->
OpenRouter LLM streaming -> Kokoro TTS reproduce -> altavoz.
Hasta que el usuario pulse Ctrl+C.

REQUISITOS:
- API key SOLO desde OPENROUTER_API_KEY (nunca en código)
- Media duplex: ignorar mic mientras suena el altavoz
- time.perf_counter por turno: user_speech_end -> transcription_ready -> first_llm_token -> full_response -> first_audio_played
- Guardar logs/latency.csv
- Historial de últimos N turnos (configurable)
- Voces: inglés y español configurables, selección por idioma de respuesta
- Prompt sistema: tutora bilingüe, frases cortas, puede español
- Modular: cambiar solo la voz (TTS) sin reescribir pipeline completo
"""

import sys
import os
import json
import time
import signal
import threading
import numpy as np
from pathlib import Path
from collections import deque
from dataclasses import dataclass, asdict
from typing import Deque, List, Dict, Any, Optional

# Añadir path del proyecto
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "python" / "src" / "main" / "python"))

# Cargar configuración YAML
try:
    import yaml
    with open(PROJECT_ROOT / "config.yaml", "r", encoding="utf-8") as f:
        CONFIG = yaml.safe_load(f)
except Exception as e:
    print(f"Error cargando config.yaml: {e}")
    sys.exit(1)

# Configuración
CONFIG = CONFIG or {}
SYSTEM_PROMPT = CONFIG.get("system_prompt", "")
LLM_CONFIG = CONFIG.get("llm", {})
STT_CONFIG = CONFIG.get("stt", {})
VAD_CONFIG = CONFIG.get("vad", {})
TTS_CONFIG = CONFIG.get("tts", {})
HISTORY_CONFIG = CONFIG.get("history", {})
AUDIO_CONFIG = CONFIG.get("audio", {})

MODEL_ID = LLM_CONFIG.get("model", "google/gemma-4-12b")
TEMPERATURE = LLM_CONFIG.get("temperature", 0.7)
MAX_TOKENS = LLM_CONFIG.get("max_tokens", 500)
MAX_HISTORY = HISTORY_CONFIG.get("max_turns", 10)
STT_MODEL_SIZE = STT_CONFIG.get("model_size", "base")
STT_DEVICE = STT_CONFIG.get("device", "cuda")
STT_COMPUTE_TYPE = STT_CONFIG.get("compute_type", "float16")
STT_LANGUAGE = STT_CONFIG.get("language", "es")
VAD_THRESHOLD = VAD_CONFIG.get("threshold", 0.5)
VAD_MIN_SILENCE_MS = VAD_CONFIG.get("min_silence_duration_ms", 400)
TTS_MODEL = TTS_CONFIG.get("model_path", "kokoro-v1.0.onnx")
TTS_VOICES_PATH = TTS_CONFIG.get("voices_path", "voices.json")
TTS_SAMPLE_RATE = TTS_CONFIG.get("sample_rate", 24000)
TTS_ENGLISH_VOICE = TTS_CONFIG.get("voices", {}).get("en", "af_bella")
TTS_SPANISH_VOICE = TTS_CONFIG.get("voices", {}).get("es", "ef_dora")
AUDIO_SAMPLE_RATE = AUDIO_CONFIG.get("sample_rate", 16000)
HALF_DUPLEX = AUDIO_CONFIG.get("half_duplex", True)
POST_TTS_DELAY_MS = AUDIO_CONFIG.get("post_tts_delay_ms", 500)

# Variable de entorno para API key
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    print("ERROR: OPENROUTER_API_KEY no encontrada en variables de entorno")
    print("   Ejecuta: export OPENROUTER_API_KEY='tu-clave-aqui'")
    sys.exit(1)

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

@dataclass
class ConversationHistory:
    user_texts: Deque[str]
    assistant_responses: Deque[str]
    assistant_languages: Deque[str]
    turn_times: Deque[float]

# ==========================================
# Inicialización de componentes
# ==========================================

import torch
print(f"PyTorch {torch.__version__} - CUDA: {torch.cuda.is_available()}")

if not torch.cuda.is_available():
    print("Advertencia: CUDA no disponible, STT usará CPU (lento)")

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

# LLM (OpenRouter)
print("Cargando LLM (OpenRouter)...")
try:
    from llm_openrouter import OpenRouterLLM
    llm = OpenRouterLLM(api_key=OPENROUTER_API_KEY, model=MODEL_ID)
    print("LLM cargado")
except Exception as e:
    print(f"Error cargando LLM: {e}")
    sys.exit(1)

# TTS (Kokoro)
print("Cargando TTS (Kokoro)...")
try:
    from tts_kokoro import KokoroTTS
    tts = KokoroTTS(model_path=TTS_MODEL, voices_path=TTS_VOICES_PATH)
    print("TTS cargado")
except Exception as e:
    print(f"Error cargando TTS: {e}")
    sys.exit(1)

# VAD (Silero)
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
except ImportError:
    print("Silero VAD no disponible, usando detección simple")
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

# ==========================================
# Funciones auxiliares
# ==========================================

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

def save_latency_csv(results: List[TurnResult], csv_path: str = "logs/latency.csv"):
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
                r.user_text[:50] if r.user_text else "",
                r.assistant_spoken[:50] if r.assistant_spoken else "",
                r.assistant_language
            ])

def add_turn_to_history(user_text: str, assistant_spoken: str, assistant_language: str):
    history.user_texts.append(user_text)
    history.assistant_responses.append(assistant_spoken)
    history.assistant_languages.append(assistant_language)

def get_system_prompt_with_context() -> str:
    if not SYSTEM_PROMPT:
        return "Eres Emma, tutora bilingüe de inglés/español amable. Responde con frases cortas (máx 2-3 oraciones). Puedes hablar español si el usuario lo necesita. Corrige errores de forma natural. Introduce 1-2 palabras nuevas por turno. Mantén un tono conversacional y alentador. FORMATO JSON OBLIGATORIO: {\"spoken\": \"frase natural\", \"language\": \"en|es\", \"corrections\": [], \"vocabulary\": []}"
    
    context = SYSTEM_PROMPT
    if history.user_texts:
        recent = list(history.user_texts)[-3:]
        context += "\n\nHistorial reciente:\n"
        for i, ut in enumerate(recent):
            context += f"Usuario: {ut}\n"
    
    return context

# ==========================================
# Pipeline principal
# ==========================================

def record_audio_vad(vad_iterator, stop_event):
    recorded_chunks = []
    silence_count = 0
    max_silence_frames = int(VAD_MIN_SILENCE_MS / 50)  # 50ms frames
    
    while not stop_event.is_set():
        try:
            import sounddevice as sd
            recording = sd.rec(
                int(AUDIO_SAMPLE_RATE * 0.05), 
                samplerate=AUDIO_SAMPLE_RATE, 
                channels=1
            )
            sd.wait()
            chunk = recording[:, 0]
            recorded_chunks.append(chunk)
            
            rms = np.sqrt(np.mean(chunk**2))
            if rms < 0.01:
                silence_count += 1
            else:
                silence_count = 0
            
            if silence_count > max_silence_frames:
                break
            
            if stop_event.is_set():
                return None
        except Exception as e:
            if not stop_event.is_set():
                print(f"Error grabando: {e}")
            return None
    
    return recorded_chunks

def speak_text(text: str, language: str = "es", block: bool = True):
    voice = select_voice(language)
    
    start = time.perf_counter()
    audio = tts.synthesize(text, lang=language)
    first_audio_start = time.perf_counter()
    
    import sounddevice as sd
    sd.play(audio, samplerate=TTS_SAMPLE_RATE)
    if block:
        sd.wait()
    
    end = time.perf_counter()
    tts_duration = (end - start) * 1000
    first_audio_duration = (first_audio_start - start) * 1000
    
    return tts_duration, first_audio_duration, audio

def run_turn(turn_num: int):
    global stop_loop
    
    print(f"\n{'='*60}")
    print(f"TURNO {turn_num} INICIANDO")
    print(f"{'='*60}")
    
    turn_start = time.perf_counter()
    
    # --- ETAPA 1: Capturar audio con VAD ---
    print("1. Escuchando... (di algo y haz una pausa)")
    
    stop_event = threading.Event()
    recorded_chunks = record_audio_vad(vad_iterator, stop_event)
    
    if not recorded_chunks:
        print("   No se grabó audio / silencio")
        return None
    
    # --- ETAPA 2: Transcripción (STT) ---
    print("2. Transcribiendo con faster-whisper...")
    
    try:
        full_audio = np.concatenate(recorded_chunks).astype(np.float32)
        
        timer.start()
        timer.mark_stt()
        
        user_text = stt.transcribe(full_audio, language=STT_LANGUAGE)
        stt_end = time.perf_counter()
        stt_ms = (stt_end - turn_start) * 1000
        
        if not user_text or user_text.strip() == "":
            print("   Transcripción vacía")
            return None
            
        print(f"   Usuario: '{user_text}'")
        
    except Exception as e:
        print(f"Error en STT: {e}")
        import traceback
        traceback.print_exc()
        return None
    
    # --- ETAPA 3: LLM Streaming ---
    print("3. LLM streaming...")
    
    try:
        system_prompt = get_system_prompt_with_context()
        
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
        first_token_time = None
        full_response = ""
        
        import requests
        
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost",
            "X-Title": "Emma Bilingüe"
        }
        
        payload = {
            "model": MODEL_ID,
            "messages": messages,
            "stream": True,
            "temperature": TEMPERATURE,
            "max_tokens": MAX_TOKENS
        }
        
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            stream=True,
            timeout=60
        )
        response.raise_for_status()
        
        for line in response.iter_lines():
            if line:
                line = line.decode('utf-8')
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                        if delta:
                            full_response += delta
                            if first_token_time is None:
                                first_token_time = time.perf_counter()
                    except json.JSONDecodeError:
                        pass
        
        llm_end = time.perf_counter()
        llm_full_ms = (llm_end - llm_start) * 1000
        
        if first_token_time is None:
            first_token_time = llm_start
        llm_first_token_ms = (first_token_time - llm_start) * 1000
        
        # Parsear respuesta JSON
        corrections = []
        vocabulary = []
        assistant_language = "es"
        spoken = full_response
        
        try:
            json_start = full_response.find('{')
            json_end = full_response.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = full_response[json_start:json_end]
                parsed = json.loads(json_str)
                spoken = parsed.get("spoken", full_response)
                corrections = parsed.get("corrections", [])
                vocabulary = parsed.get("vocabulary", [])
                assistant_language = detect_language(spoken)
        except json.JSONDecodeError:
            spoken = full_response
            assistant_language = detect_language(spoken)
        
        print(f"   LLM: '{spoken[:60]}...' ({assistant_language})")
        print(f"   LLM first token: {llm_first_token_ms:.0f}ms, full: {llm_full_ms:.0f}ms")
        
    except Exception as e:
        print(f"Error en LLM: {e}")
        import traceback
        traceback.print_exc()
        return None
    
    # --- ETAPA 4: TTS ---
    print("4. Sintetizando voz con Kokoro...")
    
    try:
        tts_start = time.perf_counter()
        tts_duration, tts_first_ms, audio = speak_text(
            spoken,
            language=assistant_language,
            block=False
        )
        
        # Delay post-TTS para que el eco se disipe
        delay_ms = int(POST_TTS_DELAY_MS)
        print(f"   Esperando {delay_ms}ms para que el eco se disipe...")
        time.sleep(delay_ms / 1000)
        
        tts_end = time.perf_counter()
        tts_ms = (tts_end - tts_start) * 1000
        
        print(f"   TTS: '{spoken[:50]}...' ({assistant_language})")
        print(f"   TTS first audio: {tts_first_ms:.0f}ms, total: {tts_ms:.0f}ms")
        
    except Exception as e:
        print(f"Error en TTS: {e}")
        import traceback
        traceback.print_exc()
        return None
    
    # --- ETAPA 5: Half-duplex pause ---
    print("5. Pausa half-duplex...")
    if HALF_DUPLEX:
        print("   Micrófono desactivado durante la reproducción TTS")
        time.sleep(0.5)
    
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
        vocabulary=vocabulary
    )
    
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
    global stop_loop, total_turns
    
    def signal_handler(signum, frame):
        global stop_loop
        print("\nCtrl+C detectado. Finalizando...")
        stop_loop = True
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("="*60)
    print("Emma Bilingüe - Voice Loop Starting")
    print("="*60)
    print(f"Model: {MODEL_ID}")
    print(f"History: {MAX_HISTORY} turns")
    print(f"VAD threshold: {VAD_THRESHOLD}")
    print(f"TTS voices: en={TTS_ENGLISH_VOICE}, es={TTS_SPANISH_VOICE}")
    print(f"Half-duplex: {HALF_DUPLEX}, Post-TTS delay: {POST_TTS_DELAY_MS}ms")
    print(f"OPENROUTER_API_KEY: {'Set' if OPENROUTER_API_KEY else 'NOT SET'}")
    print("="*60)
    print("Speak and the system will transcribe -> LLM -> voice")
    print("Press Ctrl+C to stop after current turn")
    print("="*60)
    
    os.makedirs("logs", exist_ok=True)
    
    turn_num = 0
    
    try:
        while not stop_loop:
            turn_num += 1
            if turn_num > 20:
                print("Limit of 20 turns reached")
                break
            
            result = run_turn(turn_num)
            
            if result is None:
                print("Turn incomplete, continuing...")
                continue
            
            save_latency_csv(turn_results, "logs/latency.csv")
            
            print("Pause between turns (1s)...")
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nKeyboard interrupt")
    
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
    print("Voice Loop ended. Goodbye!")
    print("="*60)

if __name__ == "__main__":
    main()