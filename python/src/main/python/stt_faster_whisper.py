"""Wrapper configurable para faster-whisper.

La autodeteccion de idioma de Whisper falla con acentos marcados y ruido:
llego a transcribir espanol como griego. Cuando el idioma detectado no es
espanol ni ingles se reintenta forzando ambos idiomas y se queda con la
transcripcion con mejor puntuacion.
"""
from faster_whisper import WhisperModel
import numpy as np
import time


class FasterWhisperSTT:
    def __init__(self, model_size="base", device="cuda", compute_type="float16"):
        self.model = WhisperModel(model_size, device=device, compute_type=compute_type)

    def _decode(self, audio, language, beam_size, vad_filter):
        segments, info = self.model.transcribe(
            audio, language=language, vad_filter=vad_filter,
            condition_on_previous_text=False, beam_size=max(1, int(beam_size))
        )
        segment_list = list(segments)
        text = " ".join(seg.text for seg in segment_list).strip()

        if segment_list:
            avg_logprob = sum(
                float(getattr(seg, "avg_logprob", -1.0)) for seg in segment_list
            ) / len(segment_list)
            no_speech = sum(
                float(getattr(seg, "no_speech_prob", 0.0)) for seg in segment_list
            ) / len(segment_list)
        else:
            avg_logprob = -1.0
            no_speech = 1.0

        # Cuanto mas alto, mejor: buena confianza, poco silencio y texto util.
        score = avg_logprob - (0.5 * no_speech) + (min(len(text), 160) / 1000.0)
        return {
            "text": text,
            "info": info,
            "language": getattr(info, "language", None),
            "avg_logprob": avg_logprob,
            "score": score,
        }

    def transcribe(
        self,
        audio: np.ndarray,
        language=None,
        beam_size=1,
        vad_filter=True,
        fallback_languages=("es", "en"),
        auto_fallback=True,
    ):
        """Devuelve (texto, idioma_detectado, idioma_forzado).

        ``language=None`` activa la autodeteccion. Si Whisper detecta un
        idioma fuera de ``fallback_languages`` (griego, ruso, arabe...), se
        retranscribe forzando espanol e ingles y se elige la mejor variante.
        """
        start = time.perf_counter()
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)

        forced = language is not None
        first = self._decode(audio, language, beam_size, vad_filter)
        detected_language = first["language"]
        chosen = first
        fallback_used = None

        allowed = tuple(fallback_languages or ())
        needs_fallback = (
            auto_fallback
            and not forced
            and allowed
            and detected_language not in allowed
        )

        if needs_fallback:
            candidates = []
            for candidate_lang in allowed:
                variant = self._decode(audio, candidate_lang, beam_size, vad_filter)
                variant["language"] = candidate_lang
                candidates.append(variant)
            if candidates:
                chosen = max(candidates, key=lambda item: item["score"])
                # Si el reintento no produce nada, conservar la primera pasada.
                if not chosen["text"]:
                    chosen = first
                else:
                    fallback_used = chosen["language"]
                    detected_language = fallback_used

        text = chosen["text"]
        elapsed = (time.perf_counter() - start) * 1000
        if forced:
            mode = "forzado"
        elif fallback_used:
            mode = f"detectado ({first['language']}), corregido a {fallback_used}"
        else:
            mode = "detectado"
        print(f"   [STT] {elapsed:.0f}ms - '{text[:50]}...' ({mode}: {detected_language})")
        return text, detected_language, forced
