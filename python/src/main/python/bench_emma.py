"""Banco de pruebas de razonamiento de Emma contra Ollama.

Uso:  python bench_emma.py <modelo> [--think]
Compara calidad (a ojo) y latencia (medida) con el prompt real de config.yaml.
"""
import json
import sys
import time
import urllib.request

CONFIG_PATH = r"C:\Users\Usuario\LocalNetworkAgent\config.yaml"


def load_system_prompt():
    text = open(CONFIG_PATH, encoding="utf-8").read()
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.strip() == "system_prompt: |":
            start = i + 1
            break
    if start is None:
        raise SystemExit("No encuentro system_prompt en config.yaml")
    block = []
    for line in lines[start:]:
        if line.strip() and not line.startswith("  "):
            break
        block.append(line[2:] if line.startswith("  ") else "")
    return "\n".join(block).strip()


SCHEMA = {
    "type": "object",
    "properties": {
        "spoken": {"type": "string"},
        "language": {"type": "string", "enum": ["en", "es"]},
        "corrections": {"type": "array", "items": {"type": "object", "properties": {
            "original": {"type": "string"}, "corrected": {"type": "string"},
            "type": {"type": "string", "enum": ["grammar", "vocabulary", "pronunciation"]},
            "explanation": {"type": "string"}},
            "required": ["original", "corrected", "type", "explanation"]}},
        "vocabulary": {"type": "array", "items": {"type": "object", "properties": {
            "word": {"type": "string"}, "translation": {"type": "string"},
            "example": {"type": "string"}}, "required": ["word", "translation", "example"]}},
        "learning": {"type": "object", "properties": {
            "focus": {"type": "string"}, "challenge": {"type": "string"},
            "exercise": {"type": "string"}}, "required": ["focus", "challenge", "exercise"]},
    },
    "required": ["spoken", "language", "corrections", "vocabulary", "learning"],
}

PROMPTS = [
    ("ES razonamiento",
     "A ver Emma, razona conmigo: si el imperio romano de occidente cae en el 476, "
     "por que seguimos hablando de edad media y no de continuidad? Quiero tu opinion argumentada."),
    ("EN opinion",
     "Convince me in English: is it better to learn a language by translating or by "
     "thinking directly in it? Give reasons, not generic advice."),
    ("ES correccion de rumbo",
     "No, eso no es lo que te he preguntado. Te pregunte por que el cielo es azul, "
     "no por la puesta de sol. Contestame bien."),
    ("EN tutor",
     "Yesterday I go to the beach with my son and we swim a lot. Correct me please."),
]


def call(model, system, user, think=False):
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "stream": False,
        "format": SCHEMA,
        "think": think,
        "keep_alive": "10m",
        "options": {"temperature": 0.6, "top_p": 0.9, "repeat_penalty": 1.08,
                    "num_predict": 480, "num_ctx": 8192},
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        "http://localhost:11434/api/chat", data=data,
        headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=300) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    elapsed = time.perf_counter() - t0
    content = (body.get("message") or {}).get("content") or ""
    try:
        parsed = json.loads(content)
        spoken = parsed.get("spoken", "")
        meta = (len(parsed.get("corrections") or []), len(parsed.get("vocabulary") or []),
                bool((parsed.get("learning") or {}).get("challenge")))
    except Exception:
        spoken, meta = content, "JSON INVALIDO"
    words = len(spoken.split())
    return spoken, meta, elapsed, words, body.get("eval_count"), body.get("eval_duration")


def main():
    model = sys.argv[1] if len(sys.argv) > 1 else "qwen2.5:7b-instruct"
    think = "--think" in sys.argv
    system = load_system_prompt()
    system += ("\n\nIDIOMA OBLIGATORIO: usa el idioma del usuario; si mezcla, "
               "responde en el idioma de su ultima frase.")
    print(f"MODELO: {model}  think={think}  prompt={len(system)} chars")
    for label, user in PROMPTS:
        try:
            spoken, meta, elapsed, words, ev, evd = call(model, system, user, think)
            tps = (ev / (evd / 1e9)) if ev and evd else 0
            print(f"\n=== {label} | {elapsed:.1f}s | {words} palabras | {tps:.1f} tok/s")
            print(spoken.strip()[:700])
            print(f"[meta] corrections={meta[0]} vocab={meta[1]} challenge={meta[2]}")
        except Exception as exc:
            print(f"\n=== {label} | ERROR: {exc}")


if __name__ == "__main__":
    main()
