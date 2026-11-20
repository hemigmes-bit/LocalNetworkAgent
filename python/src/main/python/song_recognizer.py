#!/usr/bin/env python3
"""Reconocimiento de canciones para Emma.

Dos capas complementarias:

- Shazam (``shazamio``) para musica grabada que suena cerca del microfono.
- ``melody_matcher`` para silbidos y tarareos de un catalogo de melodias famosas.

Shazam no reconoce silbidos (su huella exige la grabacion original), por eso el
modulo intenta primero la huella y despues la melodia.
"""

from __future__ import annotations

import asyncio
import io
import re
import time
import wave
from typing import Any, Dict, Optional
from unicodedata import normalize

import numpy as np

try:
    from shazamio import Shazam

    SHAZAM_AVAILABLE = True
except Exception as _shazam_error:
    Shazam = None
    SHAZAM_AVAILABLE = False
    print(f"[CANCIONES] Shazam no disponible: {_shazam_error}")

try:
    import melody_matcher

    MELODY_AVAILABLE = True
except Exception as _melody_error:
    melody_matcher = None
    MELODY_AVAILABLE = False
    print(f"[CANCIONES] Comparador de melodias no disponible: {_melody_error}")

SAMPLE_RATE = 16000
DEFAULT_SECONDS = 9.0
SHAZAM_TIMEOUT = 14.0

_TRIGGERS = (
    "que cancion es esta",
    "que cancion es",
    "que cancion suena",
    "cual es esta cancion",
    "como se llama esta cancion",
    "como se llama la cancion",
    "reconoce esta cancion",
    "reconoces esta cancion",
    "identifica esta cancion",
    "adivina la cancion",
    "sabes que cancion",
    "te voy a silbar",
    "te silbo",
    "voy a silbar",
    "voy a tararear",
    "te tarareo",
    "escucha esta melodia",
    "reconocimiento de canciones",
    "shazam",
    "what song is this",
    "what's this song",
    "whats this song",
    "what is this song",
    "which song is this",
    "recognize this song",
    "recognise this song",
    "identify this song",
    "name this song",
    "guess this song",
    "do you know this song",
    "can you recognize this song",
    "i'll whistle",
    "i will whistle",
    "i'm going to whistle",
    "im going to whistle",
    "i'll hum",
    "i will hum",
    "listen to this melody",
    "song recognition",
)


def _norm(text: str) -> str:
    text = normalize("NFKD", text or "").encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", text.lower()).strip()


def is_song_request(text: str) -> bool:
    """True si el usuario pide identificar una cancion o avisa de que va a silbar."""
    norm = _norm(text)
    if not norm:
        return False
    if any(trigger in norm for trigger in _TRIGGERS):
        return True
    # Variantes que produce el STT: "what song is it", "which song is playing"...
    patterns = (
        r"\b(what|which)\b[^.]{0,25}\bsong\b",
        r"\b(recognize|recognise|identify|name|guess)\b[^.]{0,25}\bsong\b",
        r"\b(que|cual)\b[^.]{0,25}\bcancion\b",
        r"\b(reconoce|reconoces|identifica|adivina)\b[^.]{0,25}\bcancion\b",
        r"\b(como se llama)\b[^.]{0,25}\bcancion\b",
        r"\b(whistle|whistling|hum|humming)\b",
        r"\b(silbar|silbo|silbas|tararear|tarareo|tarareas)\b",
    )
    return any(re.search(pattern, norm) for pattern in patterns)


def audio_to_wav(samples: np.ndarray, rate: int = SAMPLE_RATE) -> bytes:
    audio = np.asarray(samples, dtype=np.float32).reshape(-1)
    pcm = (np.clip(audio, -1.0, 1.0) * 32767.0).astype("<i2").tobytes()
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(pcm)
    return buffer.getvalue()


def record_from_stream(mic_stream, seconds: float = DEFAULT_SECONDS) -> bytes:
    """Graba ``seconds`` segundos del MicStream que ya usa Emma."""
    mic_stream.flush()
    chunks = []
    started = time.perf_counter()
    while time.perf_counter() - started < seconds:
        block = mic_stream.read(timeout=1.0)
        if block is None:
            continue
        chunks.append(np.asarray(block, dtype=np.float32).reshape(-1))
    if not chunks:
        return audio_to_wav(np.zeros(SAMPLE_RATE, dtype=np.float32))
    return audio_to_wav(np.concatenate(chunks))


def _parse_shazam(result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    track = (result or {}).get("track") or {}
    title = (track.get("title") or "").strip()
    if not title:
        return None
    return {
        "source": "shazam",
        "title": title,
        "artist": (track.get("subtitle") or "").strip(),
        "genre": ((track.get("genres") or {}).get("primary") or "").strip(),
        "url": (track.get("url") or "").strip(),
        "score": 0.0,
        "alternatives": [],
    }


async def _recognize_shazam(data: bytes) -> Optional[Dict[str, Any]]:
    shazam = Shazam()
    try:
        result = await asyncio.wait_for(
            shazam.recognize(data, max_skew=0.01), timeout=SHAZAM_TIMEOUT
        )
        return _parse_shazam(result)
    finally:
        try:
            await shazam.close()
        except Exception:
            pass


def recognize_shazam(wav_bytes: bytes) -> Optional[Dict[str, Any]]:
    if not SHAZAM_AVAILABLE:
        return None
    try:
        return asyncio.run(_recognize_shazam(wav_bytes))
    except Exception as exc:
        print(f"[CANCIONES] Shazam sin resultado: {exc}")
        return None


def recognize_melody(wav_bytes: bytes) -> Optional[Dict[str, Any]]:
    if not MELODY_AVAILABLE:
        return None
    try:
        candidates = melody_matcher.match_wav_bytes(wav_bytes)
    except Exception as exc:
        print(f"[CANCIONES] Error comparando melodia: {exc}")
        return None
    if not candidates:
        return None
    best = candidates[0]
    if best.get("score", 99.0) > melody_matcher.MATCH_THRESHOLD:
        return None
    alternatives = [
        item
        for item in candidates[1:]
        if item.get("score", 99.0) - best.get("score", 0.0) <= 0.25
    ]
    return {
        "source": "melody",
        "title": best.get("title") or "",
        "artist": best.get("artist") or "",
        "genre": "",
        "url": "",
        "score": float(best.get("score") or 0.0),
        "alternatives": alternatives,
    }


def identify(wav_bytes: bytes) -> Optional[Dict[str, Any]]:
    """Intenta Shazam y, si no hay huella, compara la melodia."""
    match = recognize_shazam(wav_bytes)
    if match:
        return match
    return recognize_melody(wav_bytes)


def describe(match: Optional[Dict[str, Any]], language: str = "es") -> str:
    """Frase hablada con el resultado (o con una explicacion honesta)."""
    if not match:
        if language == "en":
            return (
                "I can't identify it. Shazam needs the recorded song, and for "
                "whistles I only have a catalog of famous melodies. Try whistling "
                "the best-known chorus for five to ten seconds, or play me the recording."
            )
        return (
            "No consigo reconocerla. Shazam necesita la canción grabada y, para "
            "silbidos, solo tengo un catálogo de melodías famosas. Prueba a silbar "
            "el estribillo más conocido durante cinco o diez segundos, o ponme la grabación."
        )

    title = match.get("title") or ""
    artist = match.get("artist") or ""
    alternatives = match.get("alternatives") or []

    if language == "en":
        if artist:
            spoken = f"That's \"{title}\" by {artist}."
        else:
            spoken = f"That's \"{title}\"."
        if alternatives:
            alt = alternatives[0].get("title")
            if alt:
                spoken += f" It could also be \"{alt}\"."
        return spoken

    if artist:
        spoken = f"Es «{title}» de {artist}."
    else:
        spoken = f"Es «{title}»."
    if alternatives:
        alt = alternatives[0].get("title")
        if alt:
            spoken += f" También podría ser «{alt}»."
    return spoken
