# -*- coding: utf-8 -*-
"""Bateria de fallos del prompt de Emma (v1 largo vs v2 corto).

Compara las dos versiones del system prompt con los fallos que ya hemos
visto en produccion: idioma del turno, correcciones inventadas o no
literales, promesas imposibles, falta de empatia, cuentos que no se
cuentan, datos inventados y respuestas que se convierten en clase.

Uso:
    python prompt_battery.py                 # v1 y v2, todos los casos
    python prompt_battery.py --versions 2
    python prompt_battery.py --only edad,cuento
"""
import argparse
import ast
import io
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
from datetime import datetime

import requests
import yaml

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
CONFIG_PATH = os.path.join(BASE, "config.yaml")
VOICE_LOOP = os.path.join(BASE, "python", "src", "main", "python", "voice_loop.py")
OUT_DIR = os.path.join(BASE, "logs")

with io.open(CONFIG_PATH, encoding="utf-8") as handle:
    CONFIG = yaml.safe_load(handle)

LLM = CONFIG.get("llm", {})
OLLAMA_URL = LLM.get("ollama_url", "http://localhost:11434")
MODEL = LLM.get("ollama_model", "qwen3.5:9b")
OPTIONS = {
    "temperature": LLM.get("temperature", 0.7),
    "top_p": LLM.get("top_p", 0.9),
    "repeat_penalty": LLM.get("repeat_penalty", 1.08),
    "num_ctx": int(LLM.get("num_ctx", 10240)),
    "seed": 42,
}

SCHEMA = {
    "type": "object",
    "properties": {
        "spoken": {"type": "string"},
        "language": {"type": "string", "enum": ["en", "es"]},
        "corrections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "original": {"type": "string"},
                    "corrected": {"type": "string"},
                    "type": {
                        "type": "string",
                        "enum": ["grammar", "vocabulary", "pronunciation"],
                    },
                    "explanation": {"type": "string"},
                },
                "required": ["original", "corrected", "type", "explanation"],
            },
        },
        "vocabulary": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "word": {"type": "string"},
                    "translation": {"type": "string"},
                    "example": {"type": "string"},
                },
                "required": ["word", "translation", "example"],
            },
        },
        "learning": {
            "type": "object",
            "properties": {
                "focus": {"type": "string"},
                "challenge": {"type": "string"},
                "exercise": {"type": "string"},
            },
            "required": ["focus", "challenge", "exercise"],
        },
    },
    "required": ["spoken", "language", "corrections", "vocabulary", "learning"],
}


def extract_language_block() -> str:
    """Saca build_language_block() de voice_loop sin cargar todo el motor."""
    source = io.open(VOICE_LOOP, encoding="utf-8").read()
    tree = ast.parse(source)
    body = [n for n in tree.body if getattr(n, "name", None) == "build_language_block"]
    namespace = {
        "LANGUAGE_MODE": "adaptive",
        "LANGUAGE_PREFERENCE": "es",
        "Optional": __import__("typing").Optional,
    }
    exec(compile(ast.Module(body=body, type_ignores=[]), VOICE_LOOP, "exec"), namespace)
    return namespace["build_language_block"]


BUILD_LANGUAGE_BLOCK = extract_language_block()


def build_prompt(version: int, turn_language: str, user_name: str = "Henry") -> str:
    if version == 2:
        base = str(CONFIG.get("system_prompt_v2") or "").strip()
    else:
        base = str(CONFIG.get("system_prompt") or "")
    language_block = BUILD_LANGUAGE_BLOCK(turn_language, turn_language)
    prompt = language_block + "\n\n" + base
    if user_name:
        prompt += (
            f"\n\nMEMORIA DEL USUARIO: el usuario se llama \"{user_name}\". "
            f"Llámalo siempre \"{user_name}\" y nunca le pongas otro nombre. "
            "Si dice que no es su nombre, discúlpate y pregúntale cómo se llama."
        )
    else:
        prompt += (
            "\n\nMEMORIA DEL USUARIO: no sabes cómo se llama el usuario. "
            "Pregúntaselo una vez, con naturalidad. No inventes ningún nombre "
            "(ni 'Alex', ni 'amigo', ni apodos genéricos)."
        )
    return prompt


def normalize(text: str) -> str:
    value = unicodedata.normalize("NFKD", str(text or "").lower())
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[^a-z0-9 ]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def sentence_count(text: str) -> int:
    parts = [p for p in re.split(r"[.!?…]+(?:\s|$)", str(text or "")) if p.strip()]
    return max(1, len(parts))


ES_WORDS = set(
    "que de la el los las es y en un una por para con no se te tu mi mas pero como "
    "esta muy si al lo del le su sus cuando porque ya hay ser son fue era esto eso "
    "aqui ahora tambien puedes tener tienes".split()
)
EN_WORDS = set(
    "the is are you i to and of it that this for with in my your can do does what "
    "how why when where was were have has had will would should could there their "
    "they we he she not but about from just".split()
)


def spoken_language(text: str) -> str:
    words = re.findall(r"[a-zA-ZÁÉÍÓÚÜÑáéíóúüñ']+", str(text or "").lower())
    if len(words) < 4:
        return ""
    es = sum(1 for w in words if w in ES_WORDS)
    en = sum(1 for w in words if w in EN_WORDS)
    if es == en:
        return ""
    return "es" if es > en else "en"


PROMISE_RE = re.compile(
    r"(te lo (env[ií]o|mando)|voy a (enviar|buscar|reproducir|poner)|"
    r"aqu[ií] (tienes|est[aá])|i'?ll send|i will send|let me send|"
    r"here is your|aqu[ií] va tu)",
    re.IGNORECASE,
)
UNKNOWN_RE = re.compile(
    r"(no lo s[eé]|no puedo (saber|saberlo|comprobarlo)|no tengo (ese dato|esa informaci[oó]n)|"
    r"no ha (ocurrido|pasado)|a[uú]n no|todav[ií]a no|no dispongo|no conozco ese dato|"
    r"i don'?t know|i can'?t know|hasn'?t happened|not yet|no information)",
    re.IGNORECASE,
)
TIME_CLAIM_RE = re.compile(
    r"(son las? (una|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|once|doce|\d{1,2})|"
    r"es la una|it'?s \d{1,2}(:\d{2})?\s*(am|pm|o'?clock)?|it is \d{1,2}(:\d{2})?)",
    re.IGNORECASE,
)
EXERCISE_RE = re.compile(r"\b(ejercicio|reto|practice|exercise|challenge)\b", re.IGNORECASE)

CASES = [
    {
        "id": "es_hora",
        "text": "¿Qué hora es?",
        "lang": "es",
        "max_sent": 3,
        "no_corrections": True,
        "no_time_claim": True,
    },
    {
        "id": "en_hora",
        "text": "What time is it?",
        "lang": "en",
        "max_sent": 3,
        "no_corrections": True,
        "no_time_claim": True,
    },
    {
        "id": "edad",
        "text": "I have 25 years",
        "lang": "en",
        "max_sent": 4,
        "expect_correction": "i am 25 years old",
    },
    {
        "id": "since",
        "text": "I live in Madrid since three years",
        "lang": "en",
        "max_sent": 4,
        "expect_correction": "for three years",
    },
    {
        "id": "irregular",
        "text": "Yesterday I go to the cinema with my brother",
        "lang": "en",
        "max_sent": 4,
        "expect_correction": "went",
    },
    {
        "id": "emocion",
        "text": "Estoy triste porque mi perro está enfermo",
        "lang": "es",
        "max_sent": 4,
        "empathy": True,
        "no_corrections": True,
    },
    {
        "id": "explica",
        "text": "Explícame por qué el cielo es azul",
        "lang": "es",
        "max_sent": 5,
        "no_corrections": True,
        "keywords": ["luz", "azul"],
    },
    {
        "id": "compara",
        "text": "¿Qué es mejor para empezar, Python o JavaScript?",
        "lang": "es",
        "max_sent": 5,
        "no_corrections": True,
        "keywords": ["python", "javascript"],
    },
    {
        "id": "cuento",
        "text": "Cuéntame un cuento de un dragón",
        "lang": "es",
        "story": True,
        "no_corrections": True,
        "forbidden": ["aquí va", "prepárate", "allá va"],
    },
    {
        "id": "corrige",
        "text": "Te equivocaste: la capital de Australia es Canberra, no Sídney",
        "lang": "es",
        "max_sent": 4,
        "no_corrections": True,
    },
    {
        "id": "promesa",
        "text": "¿Puedes enviarme un audio por WhatsApp con la lección?",
        "lang": "es",
        "max_sent": 4,
        "no_corrections": True,
        "no_promise": True,
    },
    {
        "id": "nombre",
        "text": "Me llamo Pedro, ¿puedes llamarme así?",
        "lang": "es",
        "max_sent": 3,
        "no_corrections": True,
        "must_contain": "pedro",
    },
    {
        "id": "futuro",
        "text": "¿Quién ganó el Mundial de fútbol de 2031?",
        "lang": "es",
        "max_sent": 4,
        "no_corrections": True,
        "unknown": True,
    },
]


def ensure_ollama(timeout_s: float = 40.0) -> bool:
    """Comprueba Ollama y lo arranca si se ha caido (le pasa a menudo)."""
    try:
        if requests.get(f"{OLLAMA_URL}/api/tags", timeout=3).status_code == 200:
            return True
    except Exception:
        pass

    candidates = [
        os.path.join(
            os.environ.get("LOCALAPPDATA", ""), "Programs", "Ollama", "ollama.exe"
        ),
        r"C:\Program Files\Ollama\ollama.exe",
        r"C:\Program Files (x86)\Ollama\ollama.exe",
    ]
    exe = next((p for p in candidates if p and os.path.isfile(p)), None)
    if exe is None:
        return False

    print(f"   Ollama no responde; arrancando {exe}", flush=True)
    env = os.environ.copy()
    env.setdefault("OLLAMA_FLASH_ATTENTION", "1")
    env.setdefault("OLLAMA_KV_CACHE_TYPE", "q8_0")
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    try:
        subprocess.Popen(
            [exe, "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
            env=env,
        )
    except Exception as error:
        print(f"   no se pudo arrancar: {error}", flush=True)
        return False

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            if requests.get(f"{OLLAMA_URL}/api/tags", timeout=2).status_code == 200:
                print("   Ollama listo", flush=True)
                return True
        except Exception:
            pass
        time.sleep(1.0)
    return False


def call_llm(prompt: str, user_text: str, max_tokens: int) -> tuple:
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_text},
        ],
        "stream": False,
        "format": SCHEMA,
        "think": False,
        "keep_alive": "10m",
        "options": dict(OPTIONS, num_predict=int(max_tokens)),
    }
    started = time.perf_counter()
    try:
        response = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=420)
    except requests.exceptions.ConnectionError:
        if not ensure_ollama():
            raise
        response = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=420)
    response.raise_for_status()
    elapsed = time.perf_counter() - started
    content = (response.json().get("message") or {}).get("content") or ""
    return content, elapsed


def score(case: dict, user_text: str, payload: dict, raw: str, elapsed: float) -> dict:
    checks = {}
    problems = []

    if not isinstance(payload, dict):
        payload = {}
    spoken = str(payload.get("spoken") or "")
    corrections = payload.get("corrections") or []
    learning = payload.get("learning") or {}
    lang_field = str(payload.get("language") or "")
    spoken_lang = spoken_language(spoken)

    checks["json"] = bool(spoken.strip())
    if not checks["json"]:
        problems.append("sin spoken")

    checks["lang_field"] = lang_field == case["lang"]
    if not checks["lang_field"]:
        problems.append(f"language={lang_field!r}")

    checks["lang_spoken"] = (spoken_lang == case["lang"]) if spoken_lang else True
    if not checks["lang_spoken"]:
        problems.append(f"spoken en {spoken_lang}")

    if case.get("story"):
        words = len(re.findall(r"\b[\wáéíóúüñÁÉÍÓÚÜÑ']+\b", spoken))
        checks["story_words"] = 300 <= words <= 470
        if not checks["story_words"]:
            problems.append(f"{words} palabras")
        banned = [
            p for p in case.get("forbidden", []) if normalize(p) in normalize(spoken)
        ]
        checks["story_no_prep"] = not banned
        if banned:
            problems.append(f"dice {banned}")
    else:
        count = sentence_count(spoken)
        checks["sentences"] = count <= case.get("max_sent", 5)
        if not checks["sentences"]:
            problems.append(f"{count} oraciones")

    if case.get("no_corrections") or case.get("story"):
        checks["no_fake_corrections"] = len(corrections) == 0
        if corrections:
            problems.append(f"{len(corrections)} correcciones")
    else:
        checks["corrections_count"] = 1 <= len(corrections) <= 2
        if not checks["corrections_count"]:
            problems.append(f"{len(corrections)} correcciones")

    expect = case.get("expect_correction")
    if expect:
        hit = any(expect in normalize(c.get("corrected", "")) for c in corrections)
        checks["correction_content"] = hit
        if not hit:
            problems.append(f"no corrige a {expect!r}")

    if corrections:
        user_norm = normalize(user_text)
        literals = [
            normalize(c.get("original", "")) in user_norm
            for c in corrections
            if c.get("original")
        ]
        checks["literal_original"] = bool(literals) and all(literals)
        if not checks["literal_original"]:
            problems.append("original no literal")

    if case.get("empathy"):
        empty = not str(learning.get("challenge") or "").strip() and not str(
            learning.get("exercise") or ""
        ).strip()
        checks["empathy_no_task"] = empty
        if not empty:
            problems.append("propone reto/ejercicio")
        if EXERCISE_RE.search(spoken):
            checks["empathy_no_task"] = False
            problems.append("habla de ejercicio")

    if case.get("keywords"):
        low = normalize(spoken)
        missing = [k for k in case["keywords"] if normalize(k) not in low]
        checks["keywords"] = not missing
        if missing:
            problems.append(f"falta {missing}")

    if case.get("must_contain"):
        hit = normalize(case["must_contain"]) in normalize(spoken)
        checks["must_contain"] = hit
        if not hit:
            problems.append(f"no dice {case['must_contain']!r}")

    if case.get("no_promise"):
        bad = bool(PROMISE_RE.search(spoken)) and "no puedo" not in normalize(spoken)
        checks["no_promise"] = not bad
        if bad:
            problems.append("promete una accion")

    if case.get("unknown"):
        hit = bool(UNKNOWN_RE.search(spoken))
        checks["admits_unknown"] = hit
        if not hit:
            problems.append("no admite que no lo sabe")

    if case.get("no_time_claim"):
        inventa = bool(TIME_CLAIM_RE.search(spoken)) and not UNKNOWN_RE.search(spoken)
        checks["no_invented_time"] = not inventa
        if inventa:
            problems.append("inventa la hora")

    return {
        "id": case["id"],
        "raw": raw,
        "spoken": spoken,
        "language": lang_field,
        "corrections": corrections,
        "vocabulary": payload.get("vocabulary") or [],
        "learning": learning,
        "elapsed_s": round(elapsed, 1),
        "checks": checks,
        "passed": all(checks.values()),
        "problems": problems,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--versions", default="1,2")
    parser.add_argument("--only", default="")
    args = parser.parse_args()

    versions = [int(v) for v in args.versions.split(",") if v.strip()]
    only = {c.strip() for c in args.only.split(",") if c.strip()}
    cases = [c for c in CASES if not only or c["id"] in only]

    if not ensure_ollama():
        print("Ollama no disponible; abortando.")
        sys.exit(1)

    results = {}
    started = time.time()
    for version in versions:
        results[version] = []
        print(f"\n===== PROMPT v{version} =====", flush=True)
        for case in cases:
            prompt = build_prompt(version, case["lang"])
            max_tokens = 1400 if case.get("story") else 500
            try:
                raw, elapsed = call_llm(prompt, case["text"], max_tokens)
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError:
                    payload = {}
                    print(f"  {case['id']:10s} JSON INVALIDO: {raw[:90]!r}", flush=True)
                scored = score(case, case["text"], payload, raw, elapsed)
            except Exception as error:
                scored = {
                    "id": case["id"],
                    "raw": "",
                    "spoken": "",
                    "language": "",
                    "corrections": [],
                    "vocabulary": [],
                    "learning": {},
                    "elapsed_s": 0.0,
                    "checks": {"request": False},
                    "passed": False,
                    "problems": [f"error: {error}"],
                }
            results[version].append(scored)
            mark = "OK  " if scored["passed"] else "FALLO"
            detail = "" if scored["passed"] else " -> " + ", ".join(scored["problems"])
            print(
                f"  {mark} {case['id']:10s} {scored['elapsed_s']:5.1f}s "
                f"{scored['spoken'][:80]!r}{detail}",
                flush=True,
            )

    print("\n===== RESUMEN =====")
    header = f"{'caso':12s}" + "".join(f"  v{v}" for v in versions)
    print(header)
    for case in cases:
        row = f"{case['id']:12s}"
        for version in versions:
            item = next(r for r in results[version] if r["id"] == case["id"])
            row += "   " + ("OK " if item["passed"] else "X  ")
        print(row)
    for version in versions:
        passed = sum(1 for r in results[version] if r["passed"])
        total = len(results[version])
        chars = len(build_prompt(version, "es"))
        avg = sum(r["elapsed_s"] for r in results[version]) / max(1, total)
        print(f"v{version}: {passed}/{total} OK | prompt {chars} chars | media {avg:.1f}s")

    os.makedirs(OUT_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = os.path.join(OUT_DIR, f"prompt_battery_{stamp}.json")
    with io.open(out, "w", encoding="utf-8") as handle:
        json.dump(
            {
                "model": MODEL,
                "versions": versions,
                "results": results,
                "total_s": round(time.time() - started, 1),
            },
            handle,
            ensure_ascii=False,
            indent=2,
        )
    print("guardado:", out)


if __name__ == "__main__":
    main()
