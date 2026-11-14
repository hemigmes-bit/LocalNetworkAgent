"""Wrapper for Kokoro TTS.

Kokoro necesita que se le indique el idioma de fonemizacion (``lang``). Antes
se usaba el valor por defecto ``en-us`` tambien para el espanol, lo que hacia
que las frases en espanol sonaran con fonemas ingleses. Ahora el idioma se
deduce de la voz elegida.
"""
import numpy as np
import time
import os
from kokoro_onnx import Kokoro


# Prefijo de la voz -> idioma que espera el fonemizador de Kokoro.
_VOICE_LANGS = {
    "af": "en-us", "am": "en-us",
    "bf": "en-gb", "bm": "en-gb",
    "ef": "es", "em": "es",
    "ff": "fr-fr", "fm": "fr-fr",
    "hf": "hi", "hm": "hi",
    "if": "it", "im": "it",
    "jf": "ja", "jm": "ja",
    "pf": "pt-br", "pm": "pt-br",
    "zf": "zh", "zm": "zh",
}


class KokoroTTS:
    def __init__(self, model_path: str = None, voices_path: str = None, output_device: int = None):
        base = r"C:\Users\Usuario\LocalNetworkAgent"
        model_path = model_path or os.getenv("KOKORO_MODEL", os.path.join(base, "kokoro-v1.0.onnx"))
        voices_path = voices_path or os.getenv("KOKORO_VOICES", os.path.join(base, "voices-v1.0.bin"))
        
        print(f"[LOAD] Cargando Kokoro TTS...")
        print(f"  Model path: {model_path}")
        print(f"  Voices path: {voices_path}")
        print(f"  Model exists: {os.path.exists(model_path)}")
        print(f"  Voices exists: {os.path.exists(voices_path)}")
        self.kokoro = Kokoro(model_path, voices_path)
        print("[OK] Kokoro TTS cargado")
        
        # Detectar dispositivo de auriculares si no se especifica
        if output_device is None:
            output_device = self._find_headphones_device()
        self.output_device = output_device
        print(f"  Output device: {output_device}")
        
        # Voces disponibles
        self.voices = {
            "es": "ef_dora",
            "en": "af_heart",
            "es_male": "em_alex",
            "en_male": "am_michael"
        }
        # Velocidad global: algo mas lenta que 1.0 suena mas cercana y humana.
        self.speed = 0.95

    def _voice_lang(self, voice: str, fallback: str = "en-us") -> str:
        if isinstance(voice, str) and len(voice) >= 2:
            return _VOICE_LANGS.get(voice[:2], fallback)
        return fallback

    def available_voices(self):
        try:
            return list(self.kokoro.get_voices())
        except Exception:
            return []

    def _find_headphones_device(self) -> int:
        """Detectar dispositivo de auriculares automáticamente."""
        import sounddevice as sd
        try:
            # Usar dispositivo por defecto (más confiable)
            default_out = sd.default.device[1]
            print(f"  Usando dispositivo por defecto: {default_out}")
            return default_out
        except Exception as e:
            print(f"  Error detectando auriculares: {e}, usando default")
            return sd.default.device[1]

    def synthesize(self, text: str, lang: str = "es", voice: str = None,
                   speed: float = None) -> np.ndarray:
        start = time.perf_counter()
        voice = voice or self.voices.get(lang, self.voices["es"])
        speed = self.speed if speed is None else float(speed)
        # El idioma de fonemizacion depende de la voz, no del idioma pedido.
        voice_lang = self._voice_lang(voice)
        audio, _ = self.kokoro.create(
            text, voice=voice, speed=speed, lang=voice_lang
        )
        elapsed = (time.perf_counter() - start) * 1000
        print(
            f"   [TTS] Kokoro: {elapsed:.0f}ms - {len(audio)} samples "
            f"(voice={voice}, lang={voice_lang}, speed={speed:.2f})"
        )
        return audio
    
    def play(self, audio: np.ndarray, sample_rate: int = 24000):
        import sounddevice as sd
        sd.play(audio, sample_rate, device=self.output_device)
        sd.wait()
