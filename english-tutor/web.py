"""web.py - Busqueda de informacion en internet (DuckDuckGo Instant Answer + Wikipedia).
Sin claves API, usando endpoints publicos. Maneja consultas en español e inglés.
"""
import json
import re
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

UA = {"User-Agent": "Emma/1.0 (Windows; contact: none)"}

def _get(url, timeout=15):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def _strip_question_prefix(query):
    """Quita prefijos de pregunta para que la busqueda sea más efectiva."""
    q = query.strip().lower()
    patterns = [
        r"^que es\s+(?:la|el|los|las|un|una|unos|unas)?\s*(.+)",
        r"^qué es\s+(?:la|el|los|las|un|una|unos|unas)?\s*(.+)",
        r"^quien es\s+(?:la|el|los|las|un|una|unos|unas)?\s*(.+)",
        r"^quién es\s+(?:la|el|los|las|un|una|unos|unas)?\s*(.+)",
        r"^cual es\s+(?:la|el|los|las|un|una|unos|unas)?\s*(.+)",
        r"^cuál es\s+(?:la|el|los|las|un|una|unos|unas)?\s*(.+)",
        r"^busca\s+(.+)",
        r"^buscar\s+(.+)",
        r"^busca en\s+(.+)",
        r"^muestra\s+(?:el|la|los|las)?\s*(.+)",
        r"^dime\s+(?:el|la|los|las)?\s*(.+)",
        r"^dime\s+(?:el|la|los|las)?\s*(.+)",
    ]
    for pat in patterns:
        m = re.match(pat, q)
        if m:
            return m.group(1).strip()
    return query


def _to_english_if_spanish(query):
    """Heuristica: traduce preguntas comunes en español a inglés para DDG."""
    q = query.lower().strip()
    patterns = [
        (r"^que es\s+(?:la|el|los|las|un|una|unos|unas)?\s*(.+)", r"what is \1"),
        (r"^qué es\s+(?:la|el|los|las|un|una|unos|unas)?\s*(.+)", r"what is \1"),
        (r"^quien es\s+(?:la|el|los|las|un|una|unos|unas)?\s*(.+)", r"who is \1"),
        (r"^quién es\s+(?:la|el|los|las|un|una|unos|unas)?\s*(.+)", r"who is \1"),
        (r"^cual es\s+(?:la|el|los|las|un|una|unos|unas)?\s*(.+)", r"what is \1"),
        (r"^cuál es\s+(?:la|el|los|las|un|una|unos|unas)?\s*(.+)", r"what is \1"),
        (r"^busca\s+(.+)", r"\1"),
        (r"^buscar\s+(.+)", r"\1"),
        (r"^busca en\s+(.+)", r"\1"),
    ]
    for pat, repl in patterns:
        m = re.match(pat, q)
        if m:
            return re.sub(pat, repl, q)
    return query


def quick_answer(query):
    """DuckDuckGo Instant Answer API - funciona mejor con consultas en inglés."""
    q = _to_english_if_spanish(query)
    try:
        url = "https://api.duckduckgo.com/?format=json&no_html=1&q=" + urllib.parse.quote(q)
        data = json.loads(_get(url))
        if data.get("AbstractText"):
            return {"source": data.get("AbstractURL", ""), "text": data["AbstractText"]}
        if data.get("Answer"):
            return {"source": "", "text": data["Answer"]}
        related = data.get("RelatedTopics") or []
        parts = []
        for t in related[:3]:
            if isinstance(t, dict) and t.get("Text"):
                parts.append(t["Text"])
        if parts:
            return {"source": "", "text": "\n".join(parts)}
    except Exception:
        pass
    return None


def wikipedia_summary(query, lang="es"):
    """Resumen de Wikipedia (via API REST + busqueda de titulo en el idioma indicado)."""
    q = _strip_question_prefix(query)
    try:
        data = json.loads(_get("https://" + lang + ".wikipedia.org/w/api.php?action=opensearch&search=" + urllib.parse.quote(q) + "&limit=1&format=json"))
        title = (data[1] or [None])[0]
        if not title:
            return None
        data2 = json.loads(_get("https://" + lang + ".wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(title)))
        ext = data2.get("extract", "")
        return {"title": data2.get("title"), "text": ext[:700], "url": data2.get("content_urls", {}).get("desktop", {}).get("page", "")}
    except Exception:
        return None


def search(query, lang="es"):
    """Busqueda combinada en paralelo: Wikipedia + DuckDuckGo."""
    with ThreadPoolExecutor(max_workers=2) as ex:
        fut_wiki = ex.submit(wikipedia_summary, query, lang)
        fut_ddg = ex.submit(quick_answer, query)
        w = fut_wiki.result()
        d = fut_ddg.result()

    parts = []
    if w and w.get("text"):
        parts.append("Wikipedia - " + w["title"] + ": " + w["text"][:700])
    if d and d.get("text"):
        src = (" (" + d["source"] + ")") if d["source"] else ""
        parts.append("DuckDuckGo" + src + ": " + d["text"][:500])
    if not parts:
        return "No encontre informacion relevante para: " + query
    return "\n\n".join(parts)


if __name__ == "__main__":
    import sys
    q = " ".join(sys.argv[1:]) or "que es la inteligencia artificial"
    print("Buscando:", q)
    print("-" * 50)
    print(search(q))