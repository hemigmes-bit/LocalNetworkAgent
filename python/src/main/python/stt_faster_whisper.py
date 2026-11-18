"""Wrapper configurable para faster-whisper.

La autodeteccion de idioma de Whisper falla con acentos marcados y ruido:
llego a transcribir espanol como griego. Cuando el idioma detectado no es
espanol ni ingles se reintenta forzando ambos idiomas y se queda con la
transcripcion con mejor puntuacion.
"""
from faster_whisper import WhisperModel
import numpy as np
import re
import sys
import time
import unicodedata

# Frases que Whisper inventa cuando le llega silencio o ruido. Solo se
# descartan si la confianza acustica es mala: si el usuario las dice de
# verdad, no_speech_prob es bajo y avg_logprob alto, y se respetan.
_HALLUCINATION_PHRASES = (
    "thank you very much",
    "thanks for watching",
    "thank you for watching",
    "have a nice day",
    "please subscribe",
    "subtitles by",
    "subtitles created by",
    "subtitulos realizados por",
    "subtitulos hechos por",
    "gracias por ver el video",
    "gracias por ver este video",
    "hasta luego",
    "adios",
    "bye",
)


def _normalize_for_filter(text: str) -> str:
    value = unicodedata.normalize("NFKD", str(text or "").lower())
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[^a-z0-9 ]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def is_hallucination(
    text: str,
    avg_logprob: float = -1.0,
    no_speech_prob: float = 1.0,
) -> bool:
    """True si la transcripcion parece inventada por Whisper sobre ruido."""
    normalized = _normalize_for_filter(text)
    if not normalized:
        return True

    # Buena confianza acustica: es habla real, aunque el texto sea una formula.
    if avg_logprob > -0.45 and no_speech_prob < 0.2:
        return False

    # Silencio claro para el modelo y mala confianza: no habia voz.
    if no_speech_prob >= 0.75 and avg_logprob <= -0.85:
        return True

    low_confidence = no_speech_prob >= 0.3 or avg_logprob <= -0.6
    if not low_confidence:
        return False

    words = normalized.split()
    for phrase in _HALLUCINATION_PHRASES:
        phrase_words = phrase.split()
        if normalized == phrase:
            return True
        if (
            normalized.startswith(phrase + " ")
            or normalized.endswith(" " + phrase)
        ) and len(words) <= len(phrase_words) + 5:
            return True
    return False


def _safe_text(text: str, limit: int = 50) -> str:
    """Recorta texto sin romper la consola.

    La salida de Emma puede acabar en una consola cp1252 (o en un archivo
    redirigido). Whisper a veces devuelve caracteres fuera de Latin-1; si se
    imprimen tal cual, Python lanza UnicodeEncodeError y mata el motor.
    """
    value = str(text or "")[:limit]
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    try:
        value.encode(encoding)
        return value
    except (UnicodeEncodeError, LookupError):
        return value.encode(encoding, "replace").decode(encoding, "replace")


def _selftest() -> None:
    # Alucinaciones tipicas: poca voz y mala confianza.
    for text in (
        "Thank you very much. Have a nice day.",
        "Thanks for watching!",
        "Subtítulos realizados por la comunidad de Amara.org",
        "Gracias por ver el video",
        "keeP a good eye on you",
    ):
        assert is_hallucination(text, -0.95, 0.82), text

    # Habla real: no se toca aunque coincida con una formula.
    assert not is_hallucination("Thank you very much, have a nice day", -0.2, 0.05)
    assert not is_hallucination("¿Qué hora es?", -0.2, 0.02)
    assert not is_hallucination("Me llamo Henry", -0.3, 0.05)
    assert not is_hallucination("Hasta luego, Emma", -0.25, 0.04)
    assert not is_hallucination("The weather in Madrid is sunny", -0.35, 0.08)

    # Texto vacio nunca llega al LLM.
    assert is_hallucination("", -1.0, 1.0)
    assert is_hallucination("   ", -1.0, 1.0)
    print("STT SELFTEST OK")


class FasterWhisperSTT:
    def __init__(self, model_size="base", device="cuda", compute_type="float16"):
        self.model = WhisperModel(model_size, device=device, compute_type=compute_type)

    def _decode(self, audio, language, beam_size, vad_filter, hotwords=None):
        segments, info = self.model.transcribe(
            audio, language=language, vad_filter=vad_filter,
            condition_on_previous_text=False, beam_size=max(1, int(beam_size)),
            hotwords=hotwords
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

        if is_hallucination(text, avg_logprob, no_speech):
            if text.strip():
                print(
                    "   [STT] Descartado (alucinacion): "
                    f"'{_safe_text(text)}...'"
                )
            text = ""
            score = -10.0

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
        hotwords=None,
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
        first = self._decode(audio, language, beam_size, vad_filter, hotwords)
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
                variant = self._decode(audio, candidate_lang, beam_size, vad_filter, hotwords)
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
        print(f"   [STT] {elapsed:.0f}ms - '{_safe_text(text)}...' ({mode}: {detected_language})")
        return text, detected_language, forced


if __name__ == "__main__":
    _selftest()
