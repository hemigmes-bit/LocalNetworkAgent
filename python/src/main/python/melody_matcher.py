#!/usr/bin/env python3
"""Reconocimiento de melodias silbadas o tarareadas, sin dependencias externas.

Shazam (via ``shazamio``) reconoce musica grabada, pero no silbidos. Este
modulo cubre ese hueco con una comparacion de contornos melodicos:

1. Estima la frecuencia fundamental (f0) de cada fragmento con autocorrelacion.
2. Convierte la melodia a intervalos entre notas (invariante a la tonalidad).
3. Compara con un catalogo de melodias conocidas usando DTW (invariante al
   tempo y permitiendo tararear solo un fragmento).

El catalogo vive en ``melodias.json`` (raiz del proyecto) y se puede ampliar
sin tocar el codigo: cada entrada tiene ``title``, ``artist`` y ``notes``
(notas separadas por espacios, por ejemplo ``"G4 G4 A4 G4 C5 B4"``).
"""

from __future__ import annotations

import io
import json
import re
import wave
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

SAMPLE_RATE = 16000
FRAME_SIZE = 1024
HOP_SIZE = 256
MIN_F0 = 120.0
MAX_F0 = 2500.0
MIN_RMS = 0.004
MIN_CONFIDENCE = 0.35
MIN_NOTE_FRAMES = 3
MIN_INTERVALS = 5
MATCH_THRESHOLD = 0.9
AMBIGUITY_MARGIN = 0.15

CATALOG_PATH = Path(__file__).resolve().parents[4] / "melodias.json"

_NOTE_RE = re.compile(r"^([A-Ga-g])([#b]?)(-?\d+)$")
_SEMITONES = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def note_to_midi(name: str) -> int:
    """Convierte 'C#4', 'Bb3' o 'G4' a numero MIDI."""
    match = _NOTE_RE.match(name.strip())
    if not match:
        raise ValueError(f"Nota no valida: {name!r}")
    letter, accidental, octave = match.groups()
    value = _SEMITONES[letter.upper()]
    if accidental == "#":
        value += 1
    elif accidental == "b":
        value -= 1
    return value + (int(octave) + 1) * 12


def midi_to_note(midi: int) -> str:
    names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    value = int(round(midi))
    return f"{names[value % 12]}{value // 12 - 1}"


def _read_wav_bytes(data: bytes) -> Tuple[np.ndarray, int]:
    with wave.open(io.BytesIO(data), "rb") as handle:
        channels = handle.getnchannels()
        width = handle.getsampwidth()
        rate = handle.getframerate()
        frames = handle.readframes(handle.getnframes())
    if width == 2:
        samples = np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0
    elif width == 1:
        samples = (np.frombuffer(frames, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
    elif width == 4:
        samples = np.frombuffer(frames, dtype="<i4").astype(np.float32) / 2147483648.0
    else:
        raise ValueError(f"Ancho de muestra no soportado: {width}")
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)
    return samples, rate


def _resample(samples: np.ndarray, rate: int, target: int = SAMPLE_RATE) -> np.ndarray:
    if rate == target or len(samples) == 0:
        return samples
    duration = len(samples) / float(rate)
    count = int(duration * target)
    if count <= 1:
        return samples
    source = np.linspace(0.0, duration, len(samples), endpoint=False)
    dest = np.linspace(0.0, duration, count, endpoint=False)
    return np.interp(dest, source, samples).astype(np.float32)


def _frame_pitch(frame: np.ndarray, rate: int) -> Optional[float]:
    """f0 estimada por autocorrelacion; None si el fragmento no es tonal."""
    frame = frame - float(np.mean(frame))
    rms = float(np.sqrt(np.mean(frame * frame)))
    if rms < MIN_RMS:
        return None

    windowed = frame * np.hanning(len(frame))
    spectrum = np.fft.rfft(windowed, n=2 * len(frame))
    corr = np.fft.irfft(np.abs(spectrum) ** 2)[: len(frame)]
    if corr[0] <= 0:
        return None
    corr = corr / corr[0]

    min_lag = max(2, int(rate / MAX_F0))
    max_lag = min(len(corr) - 2, int(rate / MIN_F0))
    if max_lag <= min_lag:
        return None
    segment = corr[min_lag : max_lag + 1]

    peaks = []
    for index in range(1, len(segment) - 1):
        if (
            segment[index] > segment[index - 1]
            and segment[index] >= segment[index + 1]
            and segment[index] > MIN_CONFIDENCE
        ):
            peaks.append((float(segment[index]), index + min_lag))
    if not peaks:
        return None

    best = max(value for value, _ in peaks)
    # El primer pico suficientemente alto evita saltar de octava.
    lag = min(lag for value, lag in peaks if value >= best * 0.9)

    if 1 <= lag < len(corr) - 1:
        left, center, right = corr[lag - 1], corr[lag], corr[lag + 1]
        denom = left - 2.0 * center + right
        if abs(denom) > 1e-9:
            lag = lag + 0.5 * (left - right) / denom

    f0 = rate / float(lag)
    if not (MIN_F0 <= f0 <= MAX_F0):
        return None
    return 69.0 + 12.0 * float(np.log2(f0 / 440.0))


def _median_filter(values: List[Optional[float]], radius: int = 2) -> List[Optional[float]]:
    result: List[Optional[float]] = []
    for index in range(len(values)):
        window = [
            value
            for value in values[max(0, index - radius) : index + radius + 1]
            if value is not None
        ]
        result.append(float(np.median(window)) if window else None)
    return result


def extract_notes(samples: np.ndarray, rate: int = SAMPLE_RATE) -> List[int]:
    """Secuencia de notas MIDI (sin repetidas consecutivas) de un silbido."""
    samples = np.asarray(samples, dtype=np.float32)
    if rate != SAMPLE_RATE:
        samples = _resample(samples, rate)
        rate = SAMPLE_RATE
    if len(samples) < FRAME_SIZE:
        return []

    pitches: List[Optional[float]] = []
    for start in range(0, len(samples) - FRAME_SIZE + 1, HOP_SIZE):
        pitches.append(_frame_pitch(samples[start : start + FRAME_SIZE], rate))

    pitches = _median_filter(pitches, radius=2)
    notes: List[int] = []
    for value in pitches:
        if value is None:
            continue
        midi = int(round(value))
        if notes:
            # Corregir saltos de octava del detector, no la melodia real.
            while midi - notes[-1] > 12:
                midi -= 12
            while notes[-1] - midi > 12:
                midi += 12
        notes.append(midi)

    # Eliminar notas de muy corta duracion (ruido) y repetidas consecutivas.
    if not notes:
        return []
    runs: List[Tuple[int, int]] = []
    current = notes[0]
    count = 1
    for note in notes[1:]:
        if note == current:
            count += 1
        else:
            runs.append((current, count))
            current = note
            count = 1
    runs.append((current, count))

    cleaned: List[int] = []
    for note, length in runs:
        if length < MIN_NOTE_FRAMES:
            continue
        if not cleaned or cleaned[-1] != note:
            cleaned.append(note)
    return cleaned


def notes_to_intervals(notes: List[int]) -> List[int]:
    intervals = []
    for first, second in zip(notes, notes[1:]):
        distance = int(second - first)
        if distance != 0:
            intervals.append(distance)
    return intervals


def _dtw(query: List[int], reference: List[int]) -> float:
    """DTW clasico normalizado por la longitud del camino."""
    n, m = len(query), len(reference)
    if n == 0 or m == 0:
        return float("inf")
    previous = np.full(m + 1, np.inf)
    previous[0] = 0.0
    for i in range(1, n + 1):
        current = np.full(m + 1, np.inf)
        for j in range(1, m + 1):
            cost = abs(query[i - 1] - reference[j - 1])
            current[j] = cost + min(previous[j], current[j - 1], previous[j - 1])
        previous = current
    return float(previous[m] / max(n, m))


def _windowed_dtw(query: List[int], reference: List[int]) -> float:
    """Compara la consulta con ventanas de longitud parecida del catalogo.

    Evita que un fragmento corto del catalogo "explique" una melodia larga:
    la ventana debe tener un numero de notas similar al tarareado.
    """
    n = len(query)
    best = float("inf")
    longest = min(len(reference), n + 2)
    for length in range(max(MIN_INTERVALS, n - 2), longest + 1):
        for start in range(0, len(reference) - length + 1):
            distance = _dtw(query, reference[start : start + length])
            if distance < best:
                best = distance
    return best


class MelodyCatalog:
    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path) if path else CATALOG_PATH
        self.songs: List[Dict] = []
        self._intervals: List[List[int]] = []
        self.reload()

    def reload(self) -> None:
        self.songs = []
        self._intervals = []
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except FileNotFoundError:
            print(f"[MELODIA] No existe el catalogo {self.path}")
            return
        except Exception as exc:
            print(f"[MELODIA] Error leyendo {self.path}: {exc}")
            return

        for entry in data if isinstance(data, list) else []:
            try:
                notes = [note_to_midi(item) for item in str(entry.get("notes", "")).split()]
                intervals = notes_to_intervals(notes)
                if len(intervals) < MIN_INTERVALS:
                    continue
                self.songs.append(
                    {
                        "title": str(entry.get("title") or "Desconocida"),
                        "artist": str(entry.get("artist") or ""),
                    }
                )
                self._intervals.append(intervals)
            except Exception as exc:
                print(f"[MELODIA] Entrada ignorada ({entry.get('title')}): {exc}")
        print(f"[MELODIA] Catalogo cargado: {len(self.songs)} melodias")

    def match(
        self, samples: np.ndarray, rate: int = SAMPLE_RATE, limit: int = 3
    ) -> List[Dict]:
        notes = extract_notes(samples, rate)
        intervals = notes_to_intervals(notes)
        if len(intervals) < MIN_INTERVALS:
            return []

        scored = []
        for song, reference in zip(self.songs, self._intervals):
            distance = _windowed_dtw(intervals, reference)
            if np.isfinite(distance):
                scored.append(
                    {
                        "title": song["title"],
                        "artist": song["artist"],
                        "score": float(distance),
                    }
                )
        scored.sort(key=lambda item: item["score"])
        return scored[:limit]


_CATALOG: Optional[MelodyCatalog] = None


def get_catalog() -> MelodyCatalog:
    global _CATALOG
    if _CATALOG is None:
        _CATALOG = MelodyCatalog()
    return _CATALOG


def match_wav_bytes(data: bytes) -> List[Dict]:
    try:
        samples, rate = _read_wav_bytes(data)
    except Exception as exc:
        print(f"[MELODIA] WAV no valido: {exc}")
        return []
    return get_catalog().match(samples, rate)


def best_match_wav_bytes(data: bytes) -> Optional[Dict]:
    candidates = match_wav_bytes(data)
    if not candidates:
        return None
    best = candidates[0]
    if best["score"] > MATCH_THRESHOLD:
        return None
    if (
        len(candidates) > 1
        and candidates[1]["score"] - best["score"] < AMBIGUITY_MARGIN
    ):
        best = dict(best)
        best["ambiguous_with"] = candidates[1]["title"]
    return best
