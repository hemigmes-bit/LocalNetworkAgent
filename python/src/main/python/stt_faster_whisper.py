"""Wrapper for faster-whisper to provide FasterWhisperSTT interface."""
from faster_whisper import WhisperModel
import numpy as np
import time

class FasterWhisperSTT:
    def __init__(self, model_size="base", device="cuda", compute_type="float16"):
        self.model = WhisperModel(model_size, device=device, compute_type=compute_type)
    
    def transcribe(self, audio: np.ndarray, language="es") -> str:
        """Transcribe audio array to text."""
        start = time.perf_counter()
        
        # faster-whisper expects float32, 16kHz mono
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)
        
        segments, info = self.model.transcribe(
            audio,
            language=language,
            beam_size=5,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500)
        )
        
        text = " ".join([seg.text for seg in segments]).strip()
        
        elapsed = (time.perf_counter() - start) * 1000
        print(f"   [STT] {elapsed:.0f}ms - '{text[:50]}...'")
        
        return text