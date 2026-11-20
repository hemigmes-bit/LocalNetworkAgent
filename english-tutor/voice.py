import asyncio
import collections
import os
import tempfile
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import sounddevice as sd

BASE_DIR = Path(__file__).resolve().parent

_model = None
_model_name = None
_kokoro = None

_noise = None
_calibrated = False
_paused = None
_fallback_notify = None


def set_fallback_notifier(fn):
    """Registra callback para avisar cuando el TTS cambia de voz por un fallo."""
    global _fallback_notify
    _fallback_notify = fn


def _notify_fallback(msg):
    fn = _fallback_notify
    if fn is not None:
        try:
            fn(msg)
        except Exception:
            pass

def _get_pause():
    global _paused
    if _paused is None:
        import threading
        _paused = threading.Event()
    return _paused

def pause_listening():
    _get_pause().set()

def resume_listening():
    _get_pause().clear()

def _poll_key():
    try:
        import msvcrt
        if msvcrt.kbhit():
            ch = msvcrt.getwch()
            return ch
    except Exception:
        pass
    return None

def _beep(freq, ms):
    try:
        import winsound
        winsound.Beep(freq, ms)
    except Exception:
        pass

def _load_model(name):
    global _model, _model_name
    if _model is None or _model_name != name:
        from faster_whisper import WhisperModel
        _model = WhisperModel(name, device="cpu", compute_type="int8")
        _model_name = name
    return _model

def _resample(audio, orig_rate, target_rate=16000):
    if orig_rate == target_rate or audio.size == 0:
        return audio
    n = max(1, int(round(audio.size * target_rate / orig_rate)))
    idx = np.linspace(0, audio.size - 1, n)
    return np.interp(idx, np.arange(audio.size), audio).astype(np.float32)

def _calibrate_noise(stream, block_len, n=8):
    ambient = []
    for _ in range(n):
        data, _ = stream.read(block_len)
        ambient.append(float(np.sqrt(np.mean(data ** 2))))
    return float(np.median(ambient)) if ambient else 0.0

def listen_auto(cfg, ignore_pause=False):
    if not ignore_pause and _get_pause().is_set():
        return ("noise", None)
    samplerate = 16000
    block = 0.05
    block_len = int(samplerate * block)
    max_speech = float(cfg.get("voice_max_seconds", 20))
    voiced_needed = 4
    silence_needed = 1.2
    pre_roll = 8

    global _noise, _calibrated
    _beep(880, 80)
    time.sleep(0.2)

    with sd.InputStream(
        samplerate=samplerate, channels=1, dtype="float32", blocksize=block_len
    ) as stream:
        if not _calibrated:
            _noise = _calibrate_noise(stream, block_len)
            _calibrated = True
        threshold = max(0.008, _noise * 3.5)

        frames = []
        pre = collections.deque(maxlen=pre_roll)
        voiced = 0
        silent = 0.0
        started = False
        t0 = time.time()

        while time.time() - t0 < max_speech:
            if not ignore_pause and _get_pause().is_set():
                return ("noise", None)
            ch = _poll_key()
            if ch is not None:
                return ("key", ch)
            data, _ = stream.read(block_len)
            rms = float(np.sqrt(np.mean(data ** 2)))
            pre.append(data.copy())
            if rms > threshold:
                voiced += 1
                if not started and voiced >= voiced_needed:
                    started = True
                    frames = list(pre)
                    silent = 0.0
                if started:
                    frames.append(data.copy())
                    silent = 0.0
            else:
                voiced = 0
                if started:
                    silent += block
                    frames.append(data.copy())
                    if silent >= silence_needed:
                        break
            if not started and time.time() - t0 > 6.0:
                return ("noise", None)

    if not frames:
        return ("noise", None)
    _beep(660, 80)
    audio = np.concatenate(frames).flatten()
    return ("speech", audio)

def record(cfg):
    samplerate = 16000
    block = 0.05
    block_len = int(samplerate * block)
    max_secs = float(cfg.get("voice_max_seconds", 20))
    start_timeout = 6.0
    silence_needed = 1.4

    _beep(880, 80)
    time.sleep(0.2)
    with sd.InputStream(
        samplerate=samplerate, channels=1, dtype="float32", blocksize=block_len
    ) as stream:
        ambient = []
        for _ in range(6):
            data, _ = stream.read(block_len)
            ambient.append(float(np.sqrt(np.mean(data ** 2))))
        noise = float(np.median(ambient)) if ambient else 0.0
        threshold = max(0.008, noise * 3.5)

        frames = []
        started = False
        silent = 0.0
        t0 = time.time()
        while time.time() - t0 < max_secs:
            data, _ = stream.read(block_len)
            rms = float(np.sqrt(np.mean(data ** 2)))
            if rms > threshold:
                started = True
                silent = 0.0
                frames.append(data.copy())
            elif started:
                silent += block
                frames.append(data.copy())
                if silent >= silence_needed:
                    break
            elif time.time() - t0 > start_timeout:
                return None
    if not frames:
        return None
    _beep(660, 80)
    return np.concatenate(frames).flatten()

def _resample(audio, orig_rate, target_rate=16000):
    if orig_rate == target_rate or audio.size == 0:
        return audio
    n = max(1, int(round(audio.size * target_rate / orig_rate)))
    idx = np.linspace(0, audio.size - 1, n)
    return np.interp(idx, np.arange(audio.size), audio).astype(np.float32)

_ALLOWED_LANGS = ("en", "es")
_LATIN_OK = set(
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789"
    " \t\n"
    "áéíóúüñÁÉÍÓÚÜÑ"
    "¿¡.,;:!?'\"()-–—…&%$#@+*/=[]{}<>_|~^`"
)


def _looks_valid(text):
    """Rechaza textos con caracteres no latinos o bucles de alucinacion."""
    if not text or len(text.strip()) < 1:
        return False
    # Caracteres raros (islandes, cirilico, etc.)
    bad = sum(1 for ch in text if ch not in _LATIN_OK)
    if bad / max(1, len(text)) > 0.03:
        return False
    # Bucle: misma secuencia de 3+ palabras repetida 3+ veces
    words = text.lower().split()
    if len(words) >= 9:
        for n in (3, 4, 5):
            grams = [" ".join(words[i:i + n]) for i in range(len(words) - n + 1)]
            for g in set(grams):
                if len(g.split()) == n and grams.count(g) >= 3:
                    return False
    return True


def _collect(segments):
    parts = []
    logprobs = []
    for seg in segments:
        if seg.no_speech_prob > 0.6 and seg.avg_logprob < -1.0:
            continue
        t = seg.text.strip()
        if t:
            parts.append(t)
            logprobs.append(seg.avg_logprob)
    text = " ".join(parts).strip()
    avg = sum(logprobs) / len(logprobs) if logprobs else -9.0
    return text, avg


def transcribe(audio, cfg, sample_rate=16000):
    audio = _resample(np.asarray(audio, dtype=np.float32).flatten(), sample_rate)
    if audio.size == 0:
        return "", "en"
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    if 0.0 < peak < 0.5:
        audio = audio * (0.9 / peak)

    model = _load_model(cfg.get("stt_model", "small"))
    forced = cfg.get("stt_language")
    dual = [l for l in (cfg.get("stt_languages") or []) if l in _ALLOWED_LANGS]

    kwargs = dict(vad_filter=True, beam_size=5, condition_on_previous_text=False,
                  no_speech_threshold=0.6)

    def run(language):
        segs, info = model.transcribe(audio, language=language, **kwargs)
        text, avg = _collect(segs)
        return text, avg, getattr(info, "language", language or "en"), \
            getattr(info, "language_probability", 0.0)

    # Idioma unico forzado
    if forced in _ALLOWED_LANGS:
        text, avg, _, _ = run(forced)
        return (text, forced) if _looks_valid(text) else ("", forced)

    # Modo fijo multi-idioma (ES + EN): transcribe con cada uno y elige el mejor
    if dual:
        best = None
        for trylang in dual:
            t2, a2, _, _ = run(trylang)
            if not _looks_valid(t2):
                continue
            if best is None or a2 > best[0]:
                best = (a2, t2, trylang)
        if best:
            return best[1], best[2]
        return "", dual[0]

    text, avg, lang, prob = run(None)
    if lang in _ALLOWED_LANGS and prob >= 0.55 and _looks_valid(text):
        return text, lang

    # Fallback: probar espanol e ingles y quedarse con el mejor valido
    best = None
    for trylang in _ALLOWED_LANGS:
        t2, a2, _, _ = run(trylang)
        if not _looks_valid(t2):
            continue
        score = a2
        if best is None or score > best[0]:
            best = (score, t2, trylang)

    if best:
        return best[1], best[2]
    if _looks_valid(text):
        return text, lang
    return "", "en"

def _get_kokoro():
    global _kokoro
    if _kokoro is None:
        import onnxruntime
        onnxruntime.set_default_logger_severity(3)
        from kokoro_onnx import Kokoro
        model_path = str(BASE_DIR / "data" / "tts" / "kokoro-v1.0.fp16.onnx")
        voices_path = str(BASE_DIR / "data" / "tts" / "voices-v1.0.bin")
        _kokoro = Kokoro(model_path, voices_path)
    return _kokoro

def _speak_kokoro(text, cfg, lang="en"):
    kokoro = _get_kokoro()
    if lang == "es":
        voice = cfg.get("tts_kokoro_es_voice", "ef_dora")
        klang = "es"
        speed = float(cfg.get("tts_speed_es", cfg.get("tts_speed", 1.0)))
    else:
        voice = cfg.get("tts_voice", "af_heart")
        klang = "en-us"
        speed = float(cfg.get("tts_speed", 1.0))
    samples, rate = kokoro.create(text, voice=voice, speed=speed, lang=klang)
    sd.play(samples, rate)
    sd.wait()

async def _synth_edge(text, path, voice, rate):
    import edge_tts
    await edge_tts.Communicate(text, voice, rate=rate).save(str(path))

def _speak_edge(text, cfg):
    import miniaudio
    voice = cfg.get("tts_edge_voice", "en-US-AvaMultilingualNeural")
    rate = cfg.get("tts_rate", "+40%")
    pitch = cfg.get("tts_pitch", "+10Hz")
    with tempfile.TemporaryDirectory() as tmp:
        mp3 = Path(tmp) / "reply.mp3"
        asyncio.run(_synth_edge(text, mp3, voice, rate))
        if not mp3.exists() or mp3.stat().st_size == 0:
            return
        decoded = miniaudio.decode_file(
            str(mp3), output_format=miniaudio.SampleFormat.SIGNED16
        )
        samples = np.array(decoded.samples, dtype=np.int16)
        sd.play(samples, decoded.sample_rate)
        sd.wait()

def _speak_edge_lang(text, cfg, lang):
    import miniaudio
    if lang == "es":
        voice = cfg.get("tts_es_voice", "es-ES-ElviraNeural")
        rate = cfg.get("tts_rate_es", "+40%")
    else:
        voice = cfg.get("tts_edge_voice", "en-US-AvaMultilingualNeural")
        rate = cfg.get("tts_rate", "+40%")
    with tempfile.TemporaryDirectory() as tmp:
        mp3 = Path(tmp) / "reply.mp3"
        asyncio.run(_synth_edge(text, mp3, voice, rate))
        if not mp3.exists() or mp3.stat().st_size == 0:
            return
        decoded = miniaudio.decode_file(
            str(mp3), output_format=miniaudio.SampleFormat.SIGNED16
        )
        samples = np.array(decoded.samples, dtype=np.int16)
        sd.play(samples, decoded.sample_rate)
        sd.wait()

def _speak_groq(text, cfg):
    import miniaudio
    from openai import OpenAI

    client = OpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=os.environ.get("GROQ_API_KEY", ""),
        timeout=120,
    )
    model = cfg.get("tts_model", "canopylabs/orpheus-v1-english")
    voice = cfg.get("tts_groq_voice", "hannah")
    speed = float(cfg.get("tts_speed", 1.2))
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "reply.wav"
        resp = client.audio.speech.create(
            model=model, voice=voice, input=text, response_format="wav", speed=speed
        )
        resp.write_to_file(str(wav))
        decoded = miniaudio.decode_file(
            str(wav), output_format=miniaudio.SampleFormat.SIGNED16
        )
        samples = np.array(decoded.samples, dtype=np.int16)
        sd.play(samples, decoded.sample_rate)
        sd.wait()

def speak(text, cfg, lang="en"):
    """Voz UNICA y consistente: no cambia segun el idioma.
    - provider edge: usa siempre tts_edge_voice (voz multilingue)
    - provider kokoro: voz Kokoro (solo ingles)
    - provider groq: voz Groq
    """
    if not text or not cfg.get("voice", True):
        return
    provider = cfg.get("tts_provider", "kokoro")
    try:
        if provider == "kokoro":
            _speak_kokoro(text, cfg, lang)
        elif provider == "groq":
            _speak_groq(text, cfg)
        else:
            _speak_edge(text, cfg)
    except Exception as e:
        try:
            with open(BASE_DIR / "data" / "tts_fallback.log", "a", encoding="utf-8") as f:
                f.write(f"{datetime.now().isoformat(timespec='seconds')} | {provider}->edge | {e}\n")
        except Exception:
            pass
        _notify_fallback("Voz: fallo en " + str(provider) + " (" + str(e)[:120] + "). Usando voz alternativa.")
        try:
            _speak_edge(text, cfg)
        except Exception:
            pass