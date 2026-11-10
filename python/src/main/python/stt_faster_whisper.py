"""Wrapper configurable para faster-whisper."""
from faster_whisper import WhisperModel
import numpy as np
import time

class FasterWhisperSTT:
    def __init__(self, model_size="base", device="cuda", compute_type="float16"):
        self.model = WhisperModel(model_size, device=device, compute_type=compute_type)

    def transcribe(self, audio: np.ndarray, language=None, beam_size=1, vad_filter=True):
        """Devuelve (texto, idioma_detectado, idioma_forzado). language=None activa autodetección."""
        start = time.perf_counter()
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)
        forced = language is not None
        segments, info = self.model.transcribe(
            audio, language=language, vad_filter=vad_filter,
            condition_on_previous_text=False, beam_size=max(1, int(beam_size))
        )
        text = " ".join(seg.text for seg in segments).strip()
        detected_language = info.language
        elapsed = (time.perf_counter() - start) * 1000
        mode = "forzado" if forced else "detectado"
        print(f"   [STT] {elapsed:.0f}ms - '{text[:50]}...' ({mode}: {detected_language})")
        return text, detected_language, forced
