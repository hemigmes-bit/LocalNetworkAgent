#!/usr/bin/env python3
"""
Emma Bilingüe - Voice Loop (Sesión 3+6)

Pipeline completo: VAD → STT → LLM streaming → TCS → Altavoz
Repite hasta Ctrl+C.

Flujo: Silero VAD detecta fin de frase → faster-whisper (GPU) transcribe → 
OpenRouter LLM streaming → Kokoro TTS reproduce → altavoz.
Hasta que el usuario pulse Ctrl+C.

⚠️ REQUERIMIENTOS CRÍTICOS:
- API key SOLO desde OPENROUTER_API_KEY (nunca en código)
- Media duplex: ignorar mic mientras suena el altavoz
- time.perf_counter por turno: user_speech_end → transcription_ready → first_llm_token → full_response → first_audio_played
- Guardar logs/latency.csv
- Historial de últimos N turnos (configurable)
- Voces: inglés y español configurables, selección por idioma de respuesta
- Prompt sistema: tutora bilingüe, frases cortas, puede español
- Modular: cambiar solo la voz (TTS) sin reescribir pipeline completo
"""

import sys
import os
import json
import signal
import time
import csv
import threading
from pathlib import Path
from collections import deque
from dataclasses import dataclass, asdict
from typing import Deque, List, Optional, Dict, Any, Tuple

# Añadir path del proyecto
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent  # emma_bilingue padre
sys.path.insert(0, str(PROJECT_ROOT / "python" / "src" / "main" / "python"))

# Cargar configuración YAML
try:
    import yaml
    with open(PROJECT_ROOT / "config.yaml", "r", encoding="utf-8") as f:
        CONFIG = yaml.safe_load(f)
except Exception as e:
    print(f"❌ Error cargando config.yaml: {e}")
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

# Configuraciones por defecto
MODEL_ID = LLM_CONFIG.get("model", "openrouter/auto")
TEMPERATURE = LLM_CONFIG.get("temperature", 0.7)
MAX_TOKENS = LLM_CONFIG.get("max_tokens", 500)
MAX_HISTORY = HISTORY_CONFIG.get("max_turns", 10)
STT_MODEL_SIZE = STT_CONFIG.get("model_size", "base")
STT_DEVICE = STT_CONFIG.get("device", "cuda")
STT_COMPUTE_TYPE = STT_CONFIG.get("compute_type", "float16")
STT_LANGUAGE = STT_CONFIG.get("language", "es")
VAD_THRESHOLD = VAD_CONFIG.get("threshold", 0.5)
VAD_MIN_SILENCE_MS = VAD_CONFIG.get("min_silence_duration_ms", 400)
VAD_MIN_SPEECH_MS = VAD_CONFIG.get("min_speech_duration_ms", 250)
TTS_MODEL = TTS_CONFIG.get("model_path", "kokoro-v1.0.onnx")
TTS_VOICES_PATH = TTS_CONFIG.get("voices_path", "voices.json")
TTS_SAMPLE_RATE = TTS_CONFIG.get("sample_rate", 24000)
TTS_ENGLISH_VOICE = TTS_CONFIG.get("voices", {}).get("en", "af_bella")
TTS_SPANISH_VOICE = TTS_CONFIG.get("voices", {}).get("es", "ef_dora")
AUDIO_SAMPLE_RATE = AUDIO_CONFIG.get("sample_rate", 16000)
HALF_DUPLEX = AUDIO_CONFIG.get("half_duplex", True)

# Variable de entorno para API key
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    print("❌ ERROR: OPENROUTER_API_KEY no encontrada en variables de entorno")
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
print(f"🔧 PyTorch {torch.__version__} - CUDA: {torch.cuda.is_available()}")

if not torch.cuda.is_available():
    print("⚠️ Advertencia: CUDA no disponible, STT usará CPU (lento)")

# STT (faster-whisper)
print("📥 Cargando STT (faster-whisper)...")
stt = __import__('emma_core.python.src.main.python.stt_faster_whisper').stt_faster_whisper.FasterWhisperSTT(
    model_size=STT_MODEL_SIZE,
    device=STT_DEVICE,
    compute_type=STT_COMPUTE_TYPE
)
print("✅ STT cargado")

# LLM (OpenRouter)
print("📥 Cargando LLM (OpenRouter)...")
from emma_core.python.src.main.python.llm_openrouter import OpenRouterLLM
llm = OpenRouterLLM(api_key=OPENROUTER_API_KEY, model=MODEL_ID)
print("✅ LLM cargado")

# TTS (Kokoro)
print("📥 Cargando TTS (Kokoro)...")
from emma_core.python.src.main.python.tts_kokoro import KokoroTTS
tts = KokoroTTS(model_path=TTS_MODEL, voices_path=TTS_VOICES_PATH)
print("✅ TTS cargado")

# VAD (Silero)
print("📥 Cargando VAD (Silero)...")
try:
    from silero_vad import load_silero_vad, VADIterator
    vad_model = load_silero_vad()
    vad_iterator = VADIterator(vad_model, threshold=VAD_THRESHOLD,
                              sampling_rate=STT_CONFIG.get("sample_rate", 16000),
                              min_silence_duration_ms=VAD_MIN_SILENCE_MS,
                              min_speech_duration_ms=VAD_MIN_SPEECH_MS)
    print("✅ VAD cargado")
except ImportError:
    print("⚠️ Silero VAD no disponible, usando detección_simple")
    vad_iterator = None

# History management
history: ConversationHistory = ConversationHistory(
    user_texts=deque(maxlen=MAX_HISTORY),
    assistant_responses=deque(maxlen=MAX_HISTORY),
    assistant_languages=deque(maxlen=MAX_HISTORY),
    turn_times=deque(maxlen=MAX_HISTORY)
)

# Timer
timer = Timer()

# Statistics
turn_results: List[TurnResult] = []
total_turns = 0
stop_loop = False

# ==========================================
# Funciones auxiliares
# ==========================================

def detect_language(text: str) -> str:
    """Detecta si el texto es principalmente inglés o español."""
    if not text:
        return "es"
    
    # Contar palabras que parecen inglés vs español
    english_indicators = sum(1 for word in text.lower().split() 
                           if word in ['the', 'and', 'i', 'you', 'to', 'a', 'of', 'in', 'for', 'is'])
    spanish_indicators = sum(1 for word in text.lower().split() 
                            if word in ['el', 'la', 'y', 'lo', 'que', 'para', 'con', 'por', 'es', 'un'])
    
    if english_indicators > spanish_indicators * 1.5:
        return "en"
    elif spanish_indicators > english_indicators * 1.5:
        return "es"
    else:
        # Si mixto, retornar el idioma de la voz anterior o 'es' por defecto
        if history.assistant_languages:
            return history.assistant_languages[-1]
        return "es"

def select_voice(language: str) -> str:
    """Selecciona la voz de Kokoro según el idioma."""
    if language.lower().startswith("en"):
        return TTS_ENGLISH_VOICE
    else:
        return TTS_SPANISH_VOICE

def save_latency_csv(results: List[TurnResult], csv_path: str = "logs/latency.csv"):
    """Guardar tiempos de latencia en CSV."""
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
    """Añadir turno al historial."""
    history.user_texts.append(user_text)
    history.assistant_responses.append(assistant_spoken)
    history.assistant_languages.append(assistant_language)

def get_system_prompt_with_context() -> str:
    """Retorna prompt del sistema + contexto de historial reciente."""
    if not SYSTEM_PROMPT:
        # Prompt por defecto si no hay config
        return """Eres Emma, tutora bilingüe de inglés/español amable.
Responde con frases cortas (máx 2-3 oraciones).
Puedes hablar español si el usuario lo necesita.
Corrige errores de forma natural.
Introduce 1-2 palabras nuevas por turno.
Mantén tono conversacional y alentador."""
    
    # Añadir contexto de historial
    context = SYSTEM_PROMPT
    if history.user_texts:
        recent = list(history.user_texts)[-3:]  # Últimos 3 turnos
        context += "\n\nHistorial reciente:\n"
        for i, ut in enumerate(recent):
            context += f"Usuario: {ut}\n"
    
    return context

# ==========================================
# Pipeline principal
# ==========================================

def record_audio_chunk(microphone_stream, vad_iterator, audio_queue, stop_event):
    """Grabar audio en hilo separado con detección VAD."""
    import sounddevice as sd
    
    sample_rate = AUDIO_SAMPLE_RATE
    channels = AUDIO_CONFIG.get("channels", 1)
    
    print("🎤 Iniciando captura de audio (di una frase y aguarde)...")
    
    while not stop_event.is_set():
        try:
            # Grabar audio hasta que VAD detecte silencio
            if vad_iterator:
                chunks = vad_iterator.collect_chunks()
                if chunks:
                    audio_array = np.concatenate(chunks)
                    # Normalizar a float32
                    if audio_array.dtype != np.float32:
                        audio_array = audio_array.astype(np.float32) / 32768.0
                    audio_queue.put(audio_array)
            else:
                # Sin VAD: grabar bloque simple
                recording = sd.rec(int(sample_rate * 3), samplerate=sample_rate, 
                                  channels=channels)
                sd.wait()
                audio_queue.put(recording[:, 0] if channels > 1 else recording)
        except Exception as e:
            if not stop_event.is_set():
                print(f"⚠️ Error grabando audio: {e}")
    
    print("🎤 Grabación finalizada")

def speak_text(text: str, language: str = "es", block: bool = True) -> float:
    """Reproducir texto con Kokoro TTS. Retorna tiempo hasta primer audio."""
    import sounddevice as sd
    import time
    
    # Seleccionar voz según idioma
    voice = select_voice(language)
    
    start = time.perf_counter()
    audio = tts.synthesize(text, lang=language)
    first_audio_start = time.perf_counter()
    
    # Reproducir
    tts.play(audio, sample_rate=TTS_SAMPLE_RATE)
    end = time.perf_counter()
    
    duration = (end - start) * 1000
    first_audio_duration = (first_audio_start - start) * 1000
    
    return duration, first_audio_duration

def run_turn(turn_num: int) -> Optional[TurnResult]:
    """Ejecutar un turno completo del pipeline."""
    global stop_loop
    
    print(f"\n{'='*60}")
    print(f"🔄 TURNO {turn_num} INICIANDO")
    print(f"{'='*60}")
    
    turn_start = time.perf_counter()
    
    # --- ETAPA 1: Capturar audio con VAD ---
    print("⏺️ 1. Escuchando... (di algo y haga pause)")
    
    audio_queue = None
    stop_event = threading.Event()
    audio_thread = None
    
    try:
        # Iniciar captura con VAD
        audio_queue = []
        stop_event = threading.Event()
        
        if vad_iterator:
            # Usar VAD para detectar fin de frase
            print("   👂 VAD activo - escuchando hasta silencio...")
            
            # Bucle simple de VAD
            recorded_chunks = []
            silence_count = 0
            max_silence_frames = 30  # ~2 segundos de silencio
            
            while True:
                # Microfono stream
                import sounddevice as sd
                recording = sd.rec(int(AUDIO_SAMPLE_RATE * 0.5), samplerate=AUDIO_SAMPLE_RATE, channels=1)
                sd.wait()
                recorded_chunks.append(recording[:, 0])
                
                # Simplified VAD check - check energy
                rms = np.sqrt(np.mean(recording[:, 0]**2))
                if rms < 0.01:  # Silencio
                    silence_count += 1
                else:
                    silence_count = 0
                
                if silence_count > 20:  # 2s de silencio, fin de frase
                    break
                
                if stop_event.is_set():
                    return None
        
        except Exception as e:
            print(f"❌ Error en captura: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    # --- ETAPA 2: Transcripción (STT) ---
    print("📝 2. Transcribiendo con faster-whisper...")
    
    try:
        # Concatenar audio grabado
        if not recorded_chunks:
            print("   ⚠️ No se grabbed audio")
            return None
            
        full_audio = np.concatenate(recorded_chunks).astype(np.float32)
        
        # Marcar inicio de timer - STT start
        timer.start()
        timer.mark_stt()
        
        user_text = stt.transcribe(full_audio, language=STT_LANGUAGE)
        stt_end = time.perf_counter()
        stt_ms = (stt_end - turn_start) * 1000
        
        if not user_text or user_text.strip() == "":
            print("   ⚠️ Transcripción vacía")
            return None
            
        print(f"   👤 Usuario: '{user_text}'")
        
    except Exception as e:
        print(f"❌ Error en STT: {e}")
        import traceback
        traceback.print_exc()
        return None
    
    # --- ETAPA 3: LLM Streaming ---
    print("🧠 3. LLM streaming...")
    
    try:
        # Construir mensajes con historial y prompt del sistema
        system_prompt = get_system_prompt_with_context()
        
        messages = [{"role": "system", "content": system_prompt}]
        
        # Añadir historial reciente
        for i, (user_text_prev, assistant_prev, lang_prev) in enumerate(
            zip(history.user_texts, history.assistant_responses, history.assistant_languages)
        ):
            if i >= 3:  # Solo últimos 3 turnos
                break
            messages.append({"role": "user", "content": user_text_prev})
            messages.append({"role": "assistant", "content": assistant_prev})
        
        # Última frase del usuario
        messages.append({"role": "user", "content": user_text})
        
        # Marcar inicio LLM timer
        llm_start = time.perf_counter()
        first_token_time = None
        full_response = ""
        corrections = []
        vocabulary = []
        assistant_language = "es"  # default
        
        # Llamada streaming
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
                            # Marcar primer token
                            if first_token_time is None:
                                first_token_time = time.perf_counter()
                                llm_first_token_ms = (first_token_time - llm_start) * 1000
                        
                        # Intentar parsear JSON estructurado al final
                        try:
                            json_start = full_response.find('{')
                            json_end = full_response.rfind('}') + 1
                            if json_start >= 0 and json_end > json_start:
                                json_str = full_response[json_start:json_end]
                                parsed = json.loads(json_str)
                                spoken = parsed.get("spoken", full_response)
                                corrections = parsed.get("corrections", [])
                                vocabulary = parsed.get("vocabulary", [])
                                # Determinar idioma de la respuesta
                                assistant_language = detect_language(spoken)
                        except json.JSONDecodeError:
                            spoken = full_response
                        }
                        
        # Marcar fin LLM timer
        llm_end = time.perf_counter()
        llm_full_ms = (llm_end - llm_start) * 1000
        
        if first_token_time is None:
            first_token_time = llm_start
            llm_first_token_ms = llm_full_ms
        
        print(f"   🤖 LLM: '{spoken[:60]}...' ({assistant_language})")
        print(f"   ⏱️ LLM first token: {llm_first_token_ms:.0f}ms, full: {llm_full_ms:.0f}ms")
        
    except Exception as e:
        print(f"❌ Error en LLM: {e}")
        import traceback
        traceback.print_exc()
        return None
    
    # --- ETAPA 4: TTS ---
    print("🔊 4. Sintetizando voz con Kokoro...")
    
    try:
        # Seleccionar voz según idioma de respuesta
        voice = select_voice(assistant_language)
        
        # Medir tiempo hasta primer audio
        tts_start = time.perf_counter()
        tts_full_duration, tts_first_ms = speak_text(
            full_response if 'full_response' in dir() else spoken,
            language=assistant_language,
            block=False  # No bloquear para medir tiempos
        )
        
        # Si block=False no nos dio el tiempo completo, medirlo aquí
        if 'full_response' in dir():
            spoken = full_response
        
        tts_end = time.perf_counter()
        tts_ms = (tts_end - tts_start) * 1000
        
        print(f"   🔊 TTS: '{spoken[:50]}...' ({assistant_language})")
        print(f"   ⏱️ TTS first audio: {tts_first_ms:.0f}ms, total: {tts_ms:.0f}ms")
        
    except Exception as e:
        print(f"❌ Error en TTS: {e}")
        import traceback
        traceback.print_exc()
        return None
    
    # --- ETAPA 5: Half-duplex pause ---
    print("⏸️ 5. Pausa half-duplex (ignorando mic mientras suena)...")
    if HALF_DUPLEX:
        print("   🔇 Micrófono desactivado durante la reproducción TTS")
        time.sleep(0.5)  # Pequeña pausa para estabilidad
    
    # --- COMPLETAR TURNO ---
    turn_total = time.perf_counter() - turn_start
    total_ms = turn_total * 1000
    
    # Crear resultado
    result = TurnResult(
        turn=turn_num,
        stt_ms=stt_ms,
        llm_first_token_ms=llm_first_token_ms,
        llm_full_ms=llm_full_ms,
        tts_first_ms=tts_first_ms,
        total_ms=total_ms,
        user_text=user_text,
        assistant_spoken=spoken if 'spoken' in dir() else "",
        assistant_language=assistant_language,
        corrections=corrections,
        vocabulary=vocabulary
    )
    
    # Añadir al historial
    add_turn_to_history(user_text, spoken, assistant_language)
    
    # Guardar en resultados
    turn_results.append(result)
    total_turns += 1
    
    # Imprimir tabla por turno
    print(f"\n{'='*60}")
    print(f"📊 TURNO {turn_num} - TIEMPOS:")
    print(f"   STT:          {stt_ms:.0f}ms")
    print(f"   LLM first:    {llm_first_token_ms:.0f}ms")
    print(f"   LLM full:     {llm_full_ms:.0f}ms")
    print(f"   TTS first:    {tts_first_ms:.0f}ms")
    print(f"   TOTAL:        {total_ms:.0f}ms")
    print(f"{'='*60}")
    
    return result

def main():
    """Función principal - bucle de voz hasta Ctrl+C."""
    global stop_loop, total_turns
    
    # Configurar handler para Ctrl+C
    def signal_handler(signum, frame):
        global stop_loop
        print("\n⚡ Ctrl+C detectado. Finalizando conversación...")
        stop_loop = True
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Verificar que componentes cargaron
    print("="*60)
    print("🎤 Emma Bilingüe - Voice Loop Starting")
    print("="*60)
    print(f"📝 Config: modelo={MODEL_ID}, historial={MAX_HISTORY} turnos")
    print(f"🎯 VAD threshold={VAD_THRESHOLD}, TTS voice en: en={TTS_ENGLISH_VOICE}, es={TTS_SPANISH_VOICE}")
    print(f"🌐 OPENROUTER_API_KEY: {'Configurada' if OPENROUTER_API_KEY else 'NO configurada'}")
    print(f"💾 Logs de latencia: logs/latency.csv")
    print("="*60)
    print("💡 Habla y el sistema transcribirá → LLM → voz")
    print("🛑 Presiona Ctrl+C para finalizar después del turno actual")
    print("="*60)
    
    # Asegurar que logs/ existe
    os.makedirs("logs", exist_ok=True)
    
    # Inicializar CSV de latencia
    csv_path = "logs/latency.csv"
    if os.path.exists(csv_path):
        os.remove(csv_path)  # Empieza fresco cada corrida
    
    # Ejecutar bucle de turnos
    turn_num = 0
    
    try:
        while not stop_loop:
            turn_num += 1
            if turn_num > 20:  # Safety limit
                print("🔢 Límite de 20 turnos alcanzado")
                break
            
            result = run_turn(turn_num)
            
            if result is None:
                print("⚠️ Turno incompleto, continuando...")
                continue
            
            # Guardar latency CSV después de cada turno
            save_latency_csv(turn_results, csv_path)
            
            # Pequeña pausa entre turnos
            print("⏳ Pausa entre turnos (1s)...")
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n⚡ Interrupción del teclado")
    
    # ==========================================
    # Resumen final
    # ==========================================
    
    print("\n" + "="*60)
    print("📊 RESUMEN FINAL - Conversación Terminada")
    print("="*60)
    
    if turn_results:
        # Calcular promedios
        avg_stt = sum(r.stt_ms for r in turn_results) / len(turn_results)
        avg_llm_first = sum(r.llm_first_token_ms for r in turn_results) / len(turn_results)
        avg_llm_full = sum(r.llm_full_ms for r in turn_results) / len(turn_results)
        avg_tts_first = sum(r.tts_first_ms for r in turn_results) / len(turn_results)
        avg_total = sum(r.total_ms for r in turn_results) / len(turn_results)
        
        print(f"📈 Total de turnos: {len(turn_results)}")
        print(f"   📉 Promedio STT:          {avg_stt:.0f}ms")
        print(f"   📉 Promedio LLM first:    {avg_llm_first:.0f}ms")
        print(f"   📉 Promedio LLM full:     {avg_llm_full:.0f}ms")
        print(f"   📉 Promedio TTS first:    {avg_tts_first:.0f}ms")
        print(f"   📉 Promedio TOTAL:        {avg_total:.0f}ms")
        
        # Guardar CSV final
        save_latency_csv(turn_results, csv_path)
        print(f"\n💾 Datos guardados en: {csv_path}")
    else:
        print("⚠️ No se completaron turnos")
    
    # Imprimir detalles por turno
    print("\n📋 Detalle por turno:")
    for r in turn_results:
        print(f"   Turno {r.turn}: STT={r.stt_ms:.0f}ms LLM1={r.llm_first_token_ms:.0f}ms LLMF={r.llm_full_ms:.0f}ms TTS1={r.tts_first_ms:.0f}ms Tot={r.total_ms:.0f}ms | '{r.user_text[:30]}...' → '{r.assistant_spoken[:30]}...' ({r.assistant_language})")
    
    print("="*60)
    print("👋 Voice Loop finalizado. Hasta la próxima!")
    print("="*60)

if __name__ == "__main__":
    main()