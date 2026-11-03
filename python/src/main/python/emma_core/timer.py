"""Timer utility for measuring execution times."""
import time
from dataclasses import dataclass
from typing import List

@dataclass
class TurnTiming:
    turn: int
    stt_ms: float
    llm_ms: float
    tts_ms: float
    total_ms: float

class Timer:
    def __init__(self):
        self.timings = []
        self.current_start = None
    
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
        timing = TurnTiming(turn, stt_ms, llm_ms, tts_ms, total_ms)
        self.timings.append(timing)
        print(f"\n{'='*50}")
        print(f"📊 TURNO {turn} - TIEMPOS:")
        print(f"   STT (faster-whisper): {stt_ms:.1f}ms")
        print(f"   LLM (OpenRouter):      {llm_ms:.1f}ms")
        print(f"   TTS (Kokoro):          {tts_ms:.1f}ms")
        print(f"   TOTAL:                 {total_ms:.1f}ms")
        print(f"{'='*50}\n")
    
    def print_summary(self):
        if not self.timings:
            return
        print("\n" + "="*60)
        print("📊 RESUMEN DE 5 TURNOS")
        print("="*60)
        for t in self.timings:
            print(f"Turno {t.turn}: STT={t.stt_ms:.0f}ms LLM={t.llm_ms:.0f}ms TTS={t.tts_ms:.0f}ms Total={t.total_ms:.0f}ms")
        print("="*60)