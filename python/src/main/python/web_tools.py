#!/usr/bin/env python3
"""Herramientas de busqueda y lectura web para Emma.

Fuentes soportadas (sin claves de API):
  - SearXNG local como buscador general prioritario.
  - DuckDuckGo (paquete ``ddgs``) y Bing RSS como respaldos.
  - Wikipedia (API REST) para informacion enciclopedica contrastada.
  - Google News RSS para noticias y actualidad.
  - Lectura directa de cualquier URL que indique el usuario.

El modulo no imprime HTML ni texto largo por consola: devuelve estructuras
listas para inyectar en el prompt del LLM y para mostrar en la UI.

Uso de prueba:
    python web_tools.py "quien es Sam Altman"
    python web_tools.py "https://es.wikipedia.org/wiki/Inteligencia_artificial"
    python web_tools.py "ultimas noticias de inteligencia artificial"
"""

from __future__ import annotations

import ipaddress
import json
import re
import socket
import sys
import time
import urllib.parse
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Configuracion por defecto (se puede sobrescribir desde config.yaml -> web:)
# ---------------------------------------------------------------------------

DEFAULTS: Dict[str, Any] = {
    "enabled": True,
    "max_results": 3,
    "fetch_pages": 1,
    "timeout_s": 7,
    "max_chars": 1200,
    "wikipedia": True,
    "news": True,
    "extra_trusted_domains": [],
    "search_engine": "searxng",
    "searxng_url": "http://localhost:8080",
    "searxng_categories": "general",
    "searxng_engines": ["bing", "google", "duckduckgo"],
}

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
# Cabeceras de un Chrome real: sin sufijos tipo "Emma/2.0", que los cortafuegos
# de medios (El Pais, Cloudflare) usan para devolver 403.
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Sec-Ch-Ua": '"Chromium";v="131", "Not_A Brand";v="24", "Google Chrome";v="131"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}

# Lector de respaldo para paginas que bloquean peticiones directas.
READER_PROXY = "https://r.jina.ai/http://"

MAX_DOWNLOAD_BYTES = 2_000_000
CACHE_TTL_S = 300
_CACHE: Dict[str, Tuple[float, Any]] = {}

# Dominios de confianza: cuanto mas alto, mas arriba queda en el ranking.
TRUSTED_DOMAINS: Dict[str, int] = {
    "wikipedia.org": 10,
    "britannica.com": 9,
    "reuters.com": 9,
    "apnews.com": 9,
    "bbc.com": 9,
    "bbc.co.uk": 9,
    "elpais.com": 8,
    "rtve.es": 8,
    "lavanguardia.com": 7,
    "elconfidencial.com": 7,
    "eldiario.es": 7,
    "elmundo.es": 7,
    "abc.es": 6,
    "20minutos.es": 6,
    "nasa.gov": 10,
    "who.int": 10,
    "un.org": 10,
    "europa.eu": 9,
    "ine.es": 9,
    "boe.es": 10,
    "cdc.gov": 9,
    "nih.gov": 10,
    "nature.com": 10,
    "science.org": 10,
    "sciencedirect.com": 9,
    "pubmed.ncbi.nlm.nih.gov": 10,
    "arxiv.org": 8,
    "github.com": 8,
    "docs.python.org": 9,
    "developer.mozilla.org": 9,
    "python.org": 9,
    "microsoft.com": 8,
    "apple.com": 8,
    "openai.com": 8,
    "ollama.com": 8,
    "huggingface.co": 8,
    "nationalgeographic.com": 8,
    "history.com": 7,
    "imdb.com": 6,
    "espn.com": 7,
    "marca.com": 6,
    "as.com": 6,
}

# Redes sociales y contenido generado por IA: no son fuentes fiables.
BLOCKED_DOMAINS = {
    "facebook.com",
    "instagram.com",
    "tiktok.com",
    "pinterest.com",
    "pinterest.es",
    "quora.com",
    "x.com",
    "twitter.com",
    "threads.net",
    "snapchat.com",
    "tumblr.com",
    "grokipedia.com",
}

# Publicidad y redirecciones de buscadores: nunca son fuentes.
TRACKER_HOSTS = {
    "doubleclick.net",
    "googleadservices.com",
    "googlesyndication.com",
    "adservice.google.com",
    "amazon-adsystem.com",
    "taboola.com",
    "outbrain.com",
    "adclick.g.doubleclick.net",
}
_TRACKER_PATHS = ("/aclick", "/pagead/", "/aclk", "/clk", "/click?")

# ---------------------------------------------------------------------------
# Fuentes curadas para cuentos
# ---------------------------------------------------------------------------
# Cada entrada es una pagina estable de contenido narrativo, didactico o
# cultural. El cuento final lo escribe Emma: estas fuentes solo le dan un tema,
# un ambiente o datos reales para que no invente. ``start_marker`` sirve para
# saltar cabeceras y indices en los libros de Project Gutenberg.

STORY_CACHE_TTL_S = 6 * 3600
_STORY_CACHE: Dict[str, Tuple[float, Any]] = {}
_STORY_RECENT: List[str] = []
_STORY_RECENT_LIMIT = 4

STORY_SOURCES: List[Dict[str, Any]] = [
    # ------------------------------- Ingles -------------------------------
    {
        "id": "aesop",
        "lang": "en",
        "kind": "classic",
        "site": "Project Gutenberg",
        "title": "Aesop's Fables",
        "url": "https://www.gutenberg.org/cache/epub/11339/pg11339.txt",
        "start_marker": "A hungry Fox saw some fine bunches of Grapes",
        "tags": (
            "animals", "animal", "animales", "fable", "fabula", "moral",
            "fox", "zorro", "wolf", "lobo", "lion", "leon", "mouse", "raton",
            "forest", "bosque", "clever", "astuto", "classic", "clasico",
        ),
    },
    {
        "id": "alice",
        "lang": "en",
        "kind": "classic",
        "site": "Project Gutenberg",
        "title": "Alice's Adventures in Wonderland",
        "url": "https://www.gutenberg.org/cache/epub/11/pg11.txt",
        "start_marker": "Alice was beginning to get very tired",
        "tags": (
            "fantasy", "fantasia", "magic", "magia", "dream", "sueno",
            "rabbit", "conejo", "girl", "nina", "adventure", "aventura",
            "curiosity", "curiosidad", "classic", "clasico",
        ),
    },
    {
        "id": "peter_pan",
        "lang": "en",
        "kind": "classic",
        "site": "Project Gutenberg",
        "title": "Peter Pan",
        "url": "https://www.gutenberg.org/cache/epub/16/pg16.txt",
        "start_marker": "All children, except one, grow up",
        "tags": (
            "fantasy", "fantasia", "magic", "magia", "fly", "volar",
            "pirates", "piratas", "children", "ninos", "night", "noche",
            "adventure", "aventura", "classic", "clasico",
        ),
    },
    {
        "id": "treasure_island",
        "lang": "en",
        "kind": "classic",
        "site": "Project Gutenberg",
        "title": "Treasure Island",
        "url": "https://www.gutenberg.org/cache/epub/120/pg120.txt",
        "start_marker": "Squire Trelawney, Dr. Livesey",
        "tags": (
            "pirates", "pirata", "piratas", "sea", "mar", "ocean", "oceano",
            "treasure", "tesoro", "island", "isla", "ship", "barco",
            "adventure", "aventura", "courage", "valor", "classic", "clasico",
        ),
    },
    {
        "id": "jungle_book",
        "lang": "en",
        "kind": "classic",
        "site": "Project Gutenberg",
        "title": "The Jungle Book",
        "url": "https://www.gutenberg.org/cache/epub/236/pg236.txt",
        "start_marker": "Seeonee hills when Father Wolf woke up",
        "tags": (
            "animals", "animales", "jungle", "jungla", "wolf", "lobo",
            "bear", "oso", "tiger", "tigre", "india", "nature", "naturaleza",
            "wild", "salvaje", "classic", "clasico",
        ),
    },
    {
        "id": "happy_prince",
        "lang": "en",
        "kind": "classic",
        "site": "Project Gutenberg",
        "title": "The Happy Prince",
        "url": "https://www.gutenberg.org/cache/epub/902/pg902.txt",
        "start_marker": "High above the city, on a tall column",
        "tags": (
            "kindness", "bondad", "friendship", "amistad", "statue", "estatua",
            "swallow", "golondrina", "city", "ciudad", "generosity",
            "generosidad", "values", "valores", "classic", "clasico",
        ),
    },
    {
        "id": "christmas_carol",
        "lang": "en",
        "kind": "classic",
        "site": "Project Gutenberg",
        "title": "A Christmas Carol",
        "url": "https://www.gutenberg.org/cache/epub/46/pg46.txt",
        "start_marker": "Marley was dead",
        "tags": (
            "christmas", "navidad", "ghosts", "fantasmas", "winter", "invierno",
            "kindness", "bondad", "family", "familia", "values", "valores",
            "classic", "clasico",
        ),
    },
    {
        "id": "nasa_moon",
        "lang": "en",
        "kind": "didactic",
        "site": "NASA Space Place",
        "title": "All About the Moon",
        "url": "https://spaceplace.nasa.gov/all-about-the-moon/en/",
        "tags": (
            "space", "espacio", "moon", "luna", "science", "ciencia",
            "stars", "estrellas", "night", "noche", "astronaut", "astronauta",
            "planet", "planeta", "nasa", "educativo", "didactico", "aprender",
        ),
    },
    {
        "id": "natgeo_elephant",
        "lang": "en",
        "kind": "didactic",
        "site": "National Geographic Kids",
        "title": "African Elephant",
        "url": "https://kids.nationalgeographic.com/animals/mammals/facts/african-elephant",
        "tags": (
            "animals", "animales", "elephant", "elefante", "nature", "naturaleza",
            "africa", "savanna", "sabana", "water", "agua", "educativo",
            "didactico", "aprender",
        ),
    },
    {
        "id": "british_council",
        "lang": "en",
        "kind": "didactic",
        "site": "British Council",
        "title": "LearnEnglish Story Zone",
        "url": "https://learnenglish.britishcouncil.org/free-resources/general/story-zone/a2-b1",
        "tags": (
            "learning", "aprender", "english", "ingles", "school", "escuela",
            "language", "idioma", "friendship", "amistad", "modern", "moderno",
            "educativo", "didactico",
        ),
    },
    {
        "id": "unesco_en",
        "lang": "en",
        "kind": "cultural",
        "site": "UNESCO",
        "title": "UNESCO in brief",
        "url": "https://www.unesco.org/en",
        "tags": (
            "culture", "cultura", "heritage", "patrimonio", "world", "mundo",
            "history", "historia", "peace", "paz", "art", "arte", "cultural",
        ),
    },
    # ------------------------------- Espanol -------------------------------
    {
        "id": "bosque_zapatero",
        "lang": "es",
        "kind": "classic",
        "site": "Bosque de Fantasias",
        "title": "El zapatero y los duendes",
        "url": (
            "https://www.bosquedefantasias.com/recursos/"
            "cuentos-clasicos-populares/el-zapatero-y-los-duendes"
        ),
        "tags": (
            "kindness", "bondad", "work", "trabajo", "elves", "duendes",
            "shoes", "zapatos", "poverty", "pobreza", "magic", "magia",
            "values", "valores", "classic", "clasico",
        ),
    },
    {
        "id": "bosque_principe_rana",
        "lang": "es",
        "kind": "classic",
        "site": "Bosque de Fantasias",
        "title": "El principe rana",
        "url": (
            "https://www.bosquedefantasias.com/recursos/"
            "cuentos-clasicos-populares/el-principe-rana"
        ),
        "tags": (
            "princess", "princesa", "frog", "rana", "magic", "magia",
            "castle", "castillo", "promise", "promesa", "classic", "clasico",
        ),
    },
    {
        "id": "bosque_iguales",
        "lang": "es",
        "kind": "didactic",
        "site": "Bosque de Fantasias",
        "title": "Todos somos iguales",
        "url": (
            "https://www.bosquedefantasias.com/recursos/"
            "cuentos-inventados-ninos/cuento-corto-todos-somos-iguales"
        ),
        "tags": (
            "diversity", "diversidad", "friendship", "amistad", "school",
            "escuela", "respect", "respeto", "culture", "cultura", "children",
            "ninos", "values", "valores", "educativo", "didactico", "aprender",
        ),
    },
    {
        "id": "monte_animas",
        "lang": "es",
        "kind": "legend",
        "site": "Wikisource",
        "title": "El monte de las animas (Becquer)",
        "url": "https://es.wikisource.org/wiki/El_monte_de_las_%C3%A1nimas",
        "tags": (
            "mystery", "misterio", "fear", "miedo", "night", "noche",
            "legend", "leyenda", "ghosts", "fantasmas", "spain", "espana",
            "soria", "adventure", "aventura", "cultural",
        ),
    },
    {
        "id": "corza_blanca",
        "lang": "es",
        "kind": "legend",
        "site": "Wikisource",
        "title": "La corza blanca (Becquer)",
        "url": "https://es.wikisource.org/wiki/La_corza_blanca",
        "tags": (
            "legend", "leyenda", "nature", "naturaleza", "deer", "ciervo",
            "forest", "bosque", "aragon", "mystery", "misterio", "hunting",
            "caza", "cultural",
        ),
    },
    {
        "id": "quijote",
        "lang": "es",
        "kind": "classic",
        "site": "Project Gutenberg",
        "title": "Don Quijote de la Mancha",
        "url": "https://www.gutenberg.org/cache/epub/2000/pg2000.txt",
        "start_marker": "En un lugar de la Mancha",
        "tags": (
            "classic", "clasico", "knight", "caballero", "adventure", "aventura",
            "windmills", "molinos", "spain", "espana", "humor", "books", "libros",
        ),
    },
    {
        "id": "bosque_ubuntu",
        "lang": "es",
        "kind": "cultural",
        "site": "Bosque de Fantasias",
        "title": "Ubuntu, leyenda africana",
        "url": (
            "https://www.bosquedefantasias.com/recursos/"
            "leyendas-cortas-para-ninos/ubuntu"
        ),
        "tags": (
            "africa", "community", "comunidad", "cooperation", "cooperacion",
            "values", "valores", "culture", "cultura", "kindness", "bondad",
            "cultural",
        ),
    },
    {
        "id": "bosque_hilo_rojo",
        "lang": "es",
        "kind": "cultural",
        "site": "Bosque de Fantasias",
        "title": "El hilo rojo, leyenda japonesa",
        "url": (
            "https://www.bosquedefantasias.com/recursos/"
            "leyendas-cortas-para-ninos/el-hilo-rojo"
        ),
        "tags": (
            "japan", "japon", "love", "amor", "destiny", "destino", "legend",
            "leyenda", "culture", "cultura", "red", "rojo", "cultural",
        ),
    },
    {
        "id": "bosque_arroz",
        "lang": "es",
        "kind": "cultural",
        "site": "Bosque de Fantasias",
        "title": "La leyenda del arroz, India",
        "url": (
            "https://www.bosquedefantasias.com/recursos/"
            "leyendas-cortas-para-ninos/la-leyenda-del-arroz"
        ),
        "tags": (
            "india", "rice", "arroz", "food", "comida", "nature", "naturaleza",
            "legend", "leyenda", "culture", "cultura", "cultural",
        ),
    },
    {
        "id": "bosque_molino",
        "lang": "es",
        "kind": "cultural",
        "site": "Bosque de Fantasias",
        "title": "El molino magico, Noruega",
        "url": (
            "https://www.bosquedefantasias.com/recursos/"
            "leyendas-cortas-para-ninos/el-molino-magico"
        ),
        "tags": (
            "norway", "noruega", "sea", "mar", "salt", "sal", "greed",
            "ambicion", "legend", "leyenda", "culture", "cultura", "adventure",
            "aventura", "cultural",
        ),
    },
    {
        "id": "nasa_ciencia",
        "lang": "es",
        "kind": "didactic",
        "site": "NASA Ciencia",
        "title": "Ciencia de la NASA en espanol",
        "url": "https://ciencia.nasa.gov/",
        "tags": (
            "space", "espacio", "science", "ciencia", "moon", "luna", "planet",
            "planeta", "stars", "estrellas", "astronaut", "astronauta", "nasa",
            "educativo", "didactico", "aprender",
        ),
    },
    {
        "id": "nasa_luna_es",
        "lang": "es",
        "kind": "didactic",
        "site": "NASA Ciencia",
        "title": "La Luna",
        "url": "https://ciencia.nasa.gov/luna/",
        "tags": (
            "space", "espacio", "science", "ciencia", "moon", "luna",
            "stars", "estrellas", "night", "noche", "astronaut", "astronauta",
            "planet", "planeta", "nasa", "educativo", "didactico", "aprender",
        ),
    },
    {
        "id": "unesco_es",
        "lang": "es",
        "kind": "cultural",
        "site": "UNESCO",
        "title": "UNESCO en espanol",
        "url": "https://www.unesco.org/es",
        "tags": (
            "culture", "cultura", "heritage", "patrimonio", "world", "mundo",
            "history", "historia", "peace", "paz", "art", "arte", "cultural",
        ),
    },
    {
        "id": "cervantes_virtual",
        "lang": "es",
        "kind": "cultural",
        "site": "Biblioteca Virtual Miguel de Cervantes",
        "title": "Biblioteca Virtual Miguel de Cervantes",
        "url": "https://www.cervantesvirtual.com/",
        "tags": (
            "literature", "literatura", "culture", "cultura", "spain", "espana",
            "books", "libros", "theater", "teatro", "poetry", "poesia", "cultural",
        ),
    },
    {
        "id": "instituto_cervantes",
        "lang": "es",
        "kind": "didactic",
        "site": "Instituto Cervantes",
        "title": "Instituto Cervantes",
        "url": "https://www.cervantes.es/",
        "tags": (
            "language", "idioma", "spanish", "espanol", "learning", "aprender",
            "culture", "cultura", "words", "palabras", "educativo", "didactico",
        ),
    },
]

# Palabras demasiado generales para decidir si un resultado es relevante.
_GENERIC_QUERY_WORDS = {
    "precio", "precios", "noticia", "noticias", "mejor", "mejores", "comprar",
    "compra", "donde", "cuando", "quien", "como", "hoy", "ultima", "ultimas",
    "nuevo", "nueva", "guia", "review", "opiniones", "actualidad", "latest",
    "news", "price", "prices", "best", "buy", "review", "guide", "today",
    # Verbos de consulta: "que dice El Pais sobre..." no debe hacer match con
    # cualquier pagina que contenga "dice" (p. ej. un juego de dados).
    "dice", "dicen", "dijo", "dijeron", "says", "said", "publica", "publican",
    "publicado", "publicada", "habla", "hablan", "opina", "opinan", "piensa",
    "piensan", "significa", "significan", "ocurre", "ocurrio", "pasa", "paso",
    "sucede", "sucedio", "cuenta", "cuentan", "sobre", "acerca", "respecto",
}

# ---------------------------------------------------------------------------
# Deteccion de intencion
# ---------------------------------------------------------------------------

_URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_BARE_DOMAIN_RE = re.compile(
    r"(?<![\w@])(?:www\.)?([a-z0-9][a-z0-9-]*(?:\.[a-z0-9-]+)+)(/[^\s<>\"']*)?",
    re.IGNORECASE,
)
_COMMON_TLDS = {
    "com", "org", "net", "es", "io", "ai", "edu", "gov", "co", "uk", "info",
    "dev", "app", "tv", "me", "fr", "de", "it", "mx", "ar", "cl", "ru", "jp",
    "cn", "in", "br", "eu", "int", "mil", "news", "blog", "xyz", "online",
    "site", "store", "shop", "wiki", "cat",
}

_SEARCH_VERBS = (
    "busca", "buscame", "buscar", "buscad", "search", "look up",
    "find information", "investiga", "consulta en", "mira en internet",
    "mira en la web", "entra en", "abre la pagina", "abre la web",
    "lee la pagina", "lee esta pagina", "hablame de", "cuentame sobre",
    "cuentame de", "dime sobre", "informacion sobre", "informacion de",
    "tell me about",
)
_NEWS_WORDS = (
    "noticia", "noticias", "ultima hora", "ultimas noticias", "actualidad", "news",
)
_FACTUAL_PATTERNS = (
    r"\bque es\b", r"\bque son\b", r"\bquien es\b", r"\bquienes son\b",
    r"\bcuando\b", r"\bdonde\b", r"\bcomo funciona\b", r"\bcuanto cuesta\b",
    r"\bcuanto vale\b", r"\bprecio de\b", r"\bprecio del\b", r"\bclima en\b",
    r"\btiempo en\b", r"\bresultados de\b", r"\bdiferencia entre\b",
    r"\bsignificado de\b", r"\bque significa\b",
    r"\bwhat is\b", r"\bwhat are\b", r"\bwho is\b", r"\bwho are\b",
    r"\bwhen (is|was|did|does)\b", r"\bwhere (is|was|does)\b",
    r"\bhow does\b", r"\bhow much (is|does|cost)\b", r"\bprice of\b",
)
_TUTOR_PATTERNS = (
    r"como se dice", r"como se pronuncia", r"se dice", r"traduce",
    r"corrige", r"correccion", r"pronunciacion",
    r"how do you say", r"how to say", r"translate", r"pronounce",
)
_GREETING_RE = re.compile(
    r"^\s*(hola|buenas|buenos dias|buenas tardes|buenas noches|hey|gracias|"
    r"adios|hasta luego|como estas|que tal|hello|hi|good morning|"
    r"good afternoon|good evening|how are you|thanks|thank you)[\s!,.?]*$",
    re.IGNORECASE,
)


def _strip_accents(text: str) -> str:
    replacements = str.maketrans("áéíóúüñÁÉÍÓÚÜÑ", "aeiouunAEIOUUN")
    return text.translate(replacements)


def _norm(text: str) -> str:
    return _strip_accents(text).lower().strip()


_STOPWORDS = {
    "the", "and", "for", "with", "from", "that", "this", "are", "was",
    "que", "con", "por", "para", "los", "las", "del", "una", "unos", "unas",
    "como", "donde", "cuando", "quien", "quienes", "sobre", "este", "esta",
    "estos", "estas", "hay", "mas", "pero", "sus", "sin", "entre",
    # Palabras de pregunta en ingles: "who is Sam Altman" no debe buscar
    # resultados que solo contengan "sam" (p. ej. la clase SAM de Windows).
    "who", "what", "when", "where", "why", "how", "is", "are", "were",
    "does", "did", "tell", "about", "latest",
}


def _keywords(text: str) -> set:
    return {
        token
        for token in re.findall(r"[a-z0-9]{3,}", _norm(text))
        if token not in _STOPWORDS
    }


def normalize_spoken_urls(text: str) -> str:
    """Convierte 'bbc punto com' o 'wikipedia punto org barra wiki' en URL."""
    if "http" in text.lower():
        return text
    spoken = re.compile(
        r"\b([a-z0-9-]+)\s+punto\s+(com|org|net|es|edu|gov|io|ai|co|uk|info|dev|app|tv|me)\b",
        re.IGNORECASE,
    )
    if not spoken.search(text):
        return text
    fixed = re.sub(r"\s+punto\s+", ".", text, flags=re.IGNORECASE)
    fixed = re.sub(r"\s+barra\s+", "/", fixed, flags=re.IGNORECASE)
    return fixed


def extract_urls(text: str) -> List[str]:
    """Extrae URLs explicitas o dominios escritos en el texto."""
    text = normalize_spoken_urls(text)
    urls: List[str] = []

    for match in _URL_RE.findall(text):
        url = match.rstrip(".,;:!?)]}\"'")
        if url not in urls:
            urls.append(url)

    # Dominios sin esquema ("bbc.com", "www.nasa.gov/...").
    for host, path in _BARE_DOMAIN_RE.findall(text):
        if any(u.lower().find(host.lower()) >= 0 for u in urls):
            continue
        tld = host.rsplit(".", 1)[-1].lower()
        if tld not in _COMMON_TLDS:
            continue
        url = f"https://{host}{path or ''}".rstrip(".,;:!?)]}\"'")
        if url not in urls:
            urls.append(url)
    return urls


def _has_phrase(text: str, phrase: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", text) is not None


def detect_intent(text: str) -> Optional[str]:
    """Devuelve 'url', 'news', 'search' o None si no hace falta la web."""
    if not text or not text.strip():
        return None

    if extract_urls(text):
        return "url"

    norm = _norm(text)
    greeting = re.sub(r"\bemma\b", "", norm).strip(" ,.!?¿¡")
    if _GREETING_RE.match(greeting):
        return None
    if any(re.search(p, norm) for p in _TUTOR_PATTERNS):
        return None

    if any(_has_phrase(norm, w) for w in _NEWS_WORDS):
        return "news"
    if any(_has_phrase(norm, v) for v in _SEARCH_VERBS):
        return "search"
    if any(re.search(p, norm) for p in _FACTUAL_PATTERNS):
        return "search"
    return None


def should_search(text: str) -> bool:
    return detect_intent(text) is not None


def clean_query(text: str) -> str:
    """Quita muletillas, verbos y formulas interrogativas para obtener el tema.

    'quien es Sam Altman' -> 'Sam Altman'
    'que es la fotosintesis' -> 'fotosintesis'
    'y donde nacio' -> 'donde nacio' (se completa luego con el turno previo)
    """
    q = normalize_spoken_urls(text)
    q = re.sub(r"^(oye|emma|por favor)[,\s]+", "", q, flags=re.IGNORECASE)
    q = re.sub(
        r"^\s*(busca|buscame|búscame|buscar|search|look up|investiga|consulta|"
        r"mira|lee|abre|entra)\b",
        "",
        q,
        flags=re.IGNORECASE,
    ).strip()
    # Formulas interrogativas al inicio: "quien es", "qué es", "what is"...
    q = re.sub(
        r"^(quien|quién|quienes|quiénes|que|qué|cual|cuál|cuales|cuáles|"
        r"cuando|cuándo|donde|dónde|como|cómo|cuanto|cuánto|cuanta|cuánta|"
        r"cuantos|cuántos|cuantas|cuántas)\s+"
        r"(es|son|era|eran|fue|fueron|significa|se llama|esta|está|estan|"
        r"están|hay|funciona|funcionan|nacio|nació|nacieron|murio|murió|"
        r"murieron)\s+",
        "",
        q,
        flags=re.IGNORECASE,
    )
    q = re.sub(
        r"^(what|who|when|where|which|why|how)\s+"
        r"(is|are|was|were|does|do|did|can|much|many|to)\s+",
        "",
        q,
        flags=re.IGNORECASE,
    )
    q = re.sub(
        r"\b(en internet|en la web|en wikipedia|en google|por favor|para mi|"
        r"dime|cuentame|cuéntame|hablame|háblame|informacion sobre|"
        r"información sobre|informacion de|información de|"
        r"please|for me|tell me|search for|look up|information about|"
        r"information on|latest news|news about|news on|noticias sobre|"
        r"noticias de|ultimas noticias|últimas noticias|noticias|about)\b",
        " ",
        q,
        flags=re.IGNORECASE,
    )
    q = re.sub(r"^(for|up|about)\s+", "", q, flags=re.IGNORECASE)
    q = re.sub(r"\s+", " ", q).strip()
    q = re.sub(r"^(el|la|los|las|the)\s+", "", q, flags=re.IGNORECASE)
    q = q.strip(" ,.;:¿?¡!")
    return q or text.strip()


def _wants_wikipedia(text: str) -> bool:
    """Wikipedia aporta en preguntas de definicion, entidad o historia."""
    norm = _norm(text)
    return bool(
        re.search(
            r"\b(quien|quienes|que es|que son|cuando|donde|como funciona|"
            r"historia de|biografia|que significa|definicion de|"
            r"who is|who are|what is|what are|when was|where was|"
            r"how does|biography|history of|definition of)\b",
            norm,
        )
    )


def _entity_query(query: str) -> str:
    """Para Wikipedia conviene el sustantivo, no la pregunta completa.

    'Sam Altman donde nacio' -> 'Sam Altman'
    """
    trimmed = re.sub(
        r"\s+(donde|cuando|quien|quienes|como|que|cuanto|cuanta|por que)\b.*$",
        "",
        query,
        flags=re.IGNORECASE,
    ).strip()
    return trimmed or query


def _merge_followup(query: str, previous: str) -> str:
    """Resuelve seguimientos cortos ('y donde nacio') usando el turno previo.

    'Sam Altman' + 'y donde nacio' -> 'Sam Altman donde nacio'
    """
    if not previous or not query:
        return query

    q = re.sub(
        r"^(y|e|entonces|pero|ademas|tambien|and)\s+", "", query, flags=re.IGNORECASE
    ).strip()
    question_start = re.match(
        r"^(donde|cuando|quien|quienes|como|que|cuanto|cuanta|por que|a que|"
        r"where|when|who|how|what|why)\b",
        _norm(q),
    )
    reference_start = re.match(
        r"^(eso|esto|el|ella|ellos|ahi|it|that|this|he|she|they)\b", _norm(q)
    )
    if len(q.split()) <= 6 and (question_start or reference_start):
        return f"{previous.strip()} {q}"
    return query


# ---------------------------------------------------------------------------
# Utilidades de red y extraccion
# ---------------------------------------------------------------------------

def _safe_print(*args: Any) -> None:
    try:
        print(*args)
    except UnicodeEncodeError:
        text = " ".join(str(a) for a in args)
        enc = getattr(sys.stdout, "encoding", None) or "utf-8"
        print(text.encode(enc, errors="replace").decode(enc, errors="replace"))


def _url_allowed(url: str) -> Tuple[bool, str]:
    """Evita SSRF: solo http/https publicos, sin IPs privadas ni localhost."""
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        return False, "URL no valida"
    if parsed.scheme not in ("http", "https"):
        return False, "Solo se permiten enlaces http o https"
    host = parsed.hostname
    if not host:
        return False, "La URL no tiene dominio"
    if parsed.username or parsed.password:
        return False, "La URL contiene credenciales"
    if host.lower() in ("localhost", "localhost.localdomain"):
        return False, "No se permiten direcciones locales"
    try:
        infos = socket.getaddrinfo(host, None)
    except Exception:
        return False, "No se pudo resolver el dominio"
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            continue
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            return False, "No se permiten direcciones de red privadas"
    return True, ""


def _domain_score(url: str, extra_trusted: Optional[List[str]] = None) -> int:
    try:
        parsed = urllib.parse.urlparse(url)
        host = (parsed.hostname or "").lower()
    except Exception:
        return -100
    host = host[4:] if host.startswith("www.") else host
    for blocked in BLOCKED_DOMAINS:
        if host == blocked or host.endswith("." + blocked):
            return -100
    for tracker in TRACKER_HOSTS:
        if host == tracker or host.endswith("." + tracker):
            return -100
    path = (parsed.path or "").lower()
    if path and any(path.startswith(p) for p in _TRACKER_PATHS):
        return -100
    best = 0
    for domain, score in TRUSTED_DOMAINS.items():
        if host == domain or host.endswith("." + domain):
            best = max(best, score)
    for domain in extra_trusted or []:
        domain = str(domain).lower().strip()
        if domain and (host == domain or host.endswith("." + domain)):
            best = max(best, 9)
    if host.endswith(".gov") or host.endswith(".edu") or host.endswith(".int"):
        best = max(best, 8)
    if best == 0:
        best = 2
    return best


def _site_name(url: str) -> str:
    try:
        host = (urllib.parse.urlparse(url).hostname or "").lower()
    except Exception:
        return "web"
    return host[4:] if host.startswith("www.") else host


_SHORT_BRANDS = {
    "bbc", "rtve", "as", "efe", "nasa", "who", "un", "eu", "cdc", "nih", "mit",
    "bci", "csic", "upm", "uam", "unam", "nato", "ibm", "amd",
}

# Nombres de medios que la heuristica estropearia ("elpais" -> "Elpais").
_SITE_NAMES = {
    "elpais.com": "El País",
    "elconfidencial.com": "El Confidencial",
    "eldiario.es": "elDiario.es",
    "elmundo.es": "El Mundo",
    "lavanguardia.com": "La Vanguardia",
    "larazon.es": "La Razón",
    "20minutos.es": "20minutos",
    "okdiario.com": "OKDiario",
    "elperiodico.com": "El Periódico",
    "abc.es": "ABC",
    "rtve.es": "RTVE",
    "cadenaser.com": "Cadena SER",
    "ondacero.es": "Onda Cero",
    "elespanol.com": "El Español",
    "publico.es": "Público",
    "infobae.com": "Infobae",
    "clarin.com": "Clarín",
    "lanacion.com.ar": "La Nación",
    "elmundo.com": "El Mundo",
    "eluniversal.com.mx": "El Universal",
    "milenio.com": "Milenio",
}


def _display_site(site: str, url: str = "") -> str:
    """Nombre legible para citar en voz alta: 'idealo.es' -> 'Idealo'.

    Evita que el LLM lea dominios como si fueran palabras sueltas
    ('idealo.es' -> 'Ideal o').
    """
    raw = (site or "").strip()
    source = raw or _site_name(url)
    low = source.lower()
    if "wikipedia" in low:
        code = re.search(r"\((es|en)\)", low)
        return f"Wikipedia ({code.group(1)})" if code else "Wikipedia"
    if low in _SITE_NAMES:
        return _SITE_NAMES[low]
    if "." in source:
        host = _site_name(source) or source.lower()
        parts = [p for p in host.split(".") if p and p not in ("www", "m")]
        if len(parts) >= 2 and parts[0] in ("es", "en", "news", "amp"):
            parts = parts[1:]
        source = parts[0] if parts else source
    if not source:
        return "web"
    if source.lower() in _SHORT_BRANDS:
        return source.upper()
    return source[:1].upper() + source[1:]


def _url_key(url: str) -> str:
    """Clave para deduplicar URLs con distinta codificacion o barra final."""
    try:
        parsed = urllib.parse.urlparse(url)
        host = (parsed.hostname or "").lower()
        host = host[4:] if host.startswith("www.") else host
        path = urllib.parse.unquote(parsed.path or "").rstrip("/").lower()
        return f"{host}{path}"
    except Exception:
        return url.lower()


def _truncate(text: str, max_chars: int) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    last_period = max(cut.rfind(". "), cut.rfind(".\n"))
    if last_period > max_chars * 0.6:
        cut = cut[: last_period + 1]
    return cut.rstrip() + " [...]"


_BOILERPLATE = re.compile(
    r"(inicia sesion|crea una cuenta|suscribete|aceptar cookies|politica de cookies|"
    r"todos los derechos reservados|compartir en|siguenos en|descargar la app|"
    r"publicidad|newsletter|terminos de uso|aviso legal)",
    re.IGNORECASE,
)


def _extract_main_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(
        [
            "script", "style", "noscript", "nav", "footer", "header", "aside",
            "form", "svg", "button", "iframe", "dialog",
        ]
    ):
        tag.decompose()

    root = (
        soup.find("article")
        or soup.find("main")
        or soup.find(attrs={"role": "main"})
        or soup.body
        or soup
    )

    paragraphs: List[str] = []
    seen = set()
    for element in root.find_all(["p", "h2", "h3", "li"]):
        text = re.sub(r"\s+", " ", element.get_text(" ", strip=True))
        if len(text) < 50 or _BOILERPLATE.search(text):
            continue
        key = text[:120].lower()
        if key in seen:
            continue
        seen.add(key)
        paragraphs.append(text)

    if not paragraphs:
        fallback = re.sub(r"\s+", " ", root.get_text(" ", strip=True))
        if fallback:
            paragraphs = [fallback]

    return "\n".join(paragraphs)


def _page_title(soup: BeautifulSoup) -> str:
    meta = soup.find("meta", property="og:title") or soup.find("meta", attrs={"name": "twitter:title"})
    if meta and meta.get("content"):
        return re.sub(r"\s+", " ", meta["content"]).strip()
    if soup.title and soup.title.string:
        return re.sub(r"\s+", " ", soup.title.string).strip()
    return ""


def _cache_get(key: str) -> Any:
    entry = _CACHE.get(key)
    if entry and time.time() - entry[0] < CACHE_TTL_S:
        return entry[1]
    return None


def _cache_put(key: str, value: Any) -> None:
    if len(_CACHE) > 80:
        _CACHE.clear()
    _CACHE[key] = (time.time(), value)


# ---------------------------------------------------------------------------
# Lectura de una pagina concreta
# ---------------------------------------------------------------------------

READER_FALLBACK_STATUS = (401, 403, 429, 451, 503)
MIN_USEFUL_CHARS = 220


def _clean_markdown(text: str) -> str:
    """Quita imagenes y enlaces markdown dejando el texto legible."""
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"[*_`>]+", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _fetch_via_reader(url: str, timeout: float = 10.0, max_chars: int = 2200) -> Dict[str, Any]:
    """Lector externo (r.jina.ai) para paginas que bloquean peticiones directas.

    Devuelve el mismo formato que ``fetch_page``; ``error`` vacio si funciono.
    """
    result: Dict[str, Any] = {
        "title": "",
        "url": url,
        "site": _site_name(url),
        "text": "",
        "snippet": "",
        "kind": "page",
        "error": "",
        "via": "reader",
    }
    proxy_url = READER_PROXY + re.sub(r"^https?://", "", url, flags=re.IGNORECASE)
    try:
        response = requests.get(
            proxy_url,
            headers={"User-Agent": USER_AGENT, "Accept": "text/plain"},
            timeout=max(timeout, 10.0),
        )
        if response.status_code >= 400:
            result["error"] = f"reader HTTP {response.status_code}"
            return result
        body = response.text
    except Exception as exc:
        result["error"] = f"reader {type(exc).__name__}"
        return result

    title = ""
    title_match = re.search(r"^Title:\s*(.+)$", body, re.MULTILINE)
    if title_match:
        title = title_match.group(1).strip()
    content = body
    marker = body.find("Markdown Content:")
    if marker >= 0:
        content = body[marker + len("Markdown Content:"):]
    content = _clean_markdown(content)
    if not content.strip():
        result["error"] = "reader sin texto util"
        return result
    result.update(
        {
            "title": title or _site_name(url),
            "text": _truncate(content, max_chars),
            "snippet": _truncate(content, 300),
            "error": "",
        }
    )
    return result


def fetch_page(url: str, timeout: float = 7.0, max_chars: int = 2200) -> Dict[str, Any]:
    """Descarga una pagina y devuelve titulo, texto principal y metadatos."""
    cached = _cache_get("page:" + url)
    if cached is not None:
        return cached

    result: Dict[str, Any] = {
        "title": "",
        "url": url,
        "site": _site_name(url),
        "text": "",
        "snippet": "",
        "kind": "page",
        "error": "",
    }

    allowed, reason = _url_allowed(url)
    if not allowed:
        result["error"] = reason
        return result

    try:
        with requests.get(
            url, headers=HEADERS, timeout=timeout, stream=True, allow_redirects=True
        ) as response:
            if response.status_code >= 400:
                # 403/429/451/503: cortafuegos o paywall. Probamos el lector.
                if response.status_code in READER_FALLBACK_STATUS:
                    reader = _fetch_via_reader(url, timeout, max_chars)
                    if not reader.get("error"):
                        _cache_put("page:" + url, reader)
                        return reader
                result["error"] = f"HTTP {response.status_code}"
                return result
            content_type = (response.headers.get("content-type") or "").lower()
            if not any(t in content_type for t in ("text/html", "text/plain", "application/xhtml")):
                result["error"] = f"Tipo de contenido no soportado: {content_type.split(';')[0]}"
                return result
            raw = b""
            for chunk in response.iter_content(chunk_size=16384):
                raw += chunk
                if len(raw) >= MAX_DOWNLOAD_BYTES:
                    break
            encoding = response.encoding or "utf-8"
            final_url = response.url
    except requests.Timeout:
        reader = _fetch_via_reader(url, timeout, max_chars)
        if not reader.get("error"):
            _cache_put("page:" + url, reader)
            return reader
        result["error"] = "Tiempo de espera agotado"
        return result
    except Exception as exc:
        reader = _fetch_via_reader(url, timeout, max_chars)
        if not reader.get("error"):
            _cache_put("page:" + url, reader)
            return reader
        result["error"] = f"{type(exc).__name__}: {exc}"
        return result

    try:
        html = raw.decode(encoding, errors="replace")
    except Exception:
        html = raw.decode("utf-8", errors="replace")

    soup = BeautifulSoup(html, "html.parser")
    title = _page_title(soup)
    text = _extract_main_text(html)

    if not text.strip():
        meta = soup.find("meta", attrs={"name": "description"}) or soup.find(
            "meta", property="og:description"
        )
        if meta and meta.get("content"):
            text = meta["content"].strip()

    # Paginas con muro de cookies o cargadas por JS dejan poco texto: el lector
    # externo suele devolver el articulo completo.
    if len(text.strip()) < MIN_USEFUL_CHARS:
        reader = _fetch_via_reader(url, timeout, max_chars)
        if not reader.get("error") and len(reader.get("text") or "") > len(text.strip()):
            _cache_put("page:" + url, reader)
            return reader

    result.update(
        {
            "title": title or _site_name(final_url),
            "url": final_url,
            "site": _site_name(final_url),
            "text": _truncate(text, max_chars),
            "snippet": _truncate(text, 300),
            "error": "" if text.strip() else "No se pudo extraer texto util",
        }
    )
    _cache_put("page:" + url, result)
    return result


# ---------------------------------------------------------------------------
# Cuentos: seleccion de fuentes y material de apoyo
# ---------------------------------------------------------------------------

def _story_cache_get(key: str) -> Any:
    entry = _STORY_CACHE.get(key)
    if entry and time.time() - entry[0] < STORY_CACHE_TTL_S:
        return entry[1]
    return None


def _story_cache_put(key: str, value: Any) -> None:
    if len(_STORY_CACHE) > 60:
        _STORY_CACHE.clear()
    _STORY_CACHE[key] = (time.time(), value)


def _tag_in_text(text: str, tag: str) -> bool:
    tag = _norm(tag)
    if not tag:
        return False
    if " " in tag:
        return tag in text
    return re.search(rf"\b{re.escape(tag)}(?:s|es)?\b", text) is not None


def rank_story_sources(text: str, lang: str = "es") -> List[Dict[str, Any]]:
    """Ordena las fuentes curadas segun el tema que pide el usuario.

    Se mezclan fuentes de los dos idiomas: un cuento de piratas pedido en
    espanol puede inspiarse en ``Treasure Island`` y narrarse en espanol. Las
    fuentes del idioma de respuesta reciben un pequeno extra para desempatar.
    """
    code = "en" if str(lang or "").lower().startswith("en") else "es"
    candidates = list(STORY_SOURCES)

    norm = _norm(text or "")
    scored: List[Tuple[float, Dict[str, Any]]] = []
    for source in candidates:
        score = 0.0
        for tag in source["tags"]:
            if _tag_in_text(norm, tag):
                score += 2.0 if " " in tag else 1.0
        if source["kind"] in ("classic", "legend", "folktale"):
            score += 0.5
        if source["lang"] == code:
            score += 0.75
        if source["id"] in _STORY_RECENT:
            score -= 0.25
        scored.append((score, source))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [source for _, source in scored]


def _story_material_start(text: str, marker: Optional[str]) -> str:
    if not marker:
        return text
    index = text.lower().find(marker.lower())
    if index < 0:
        return text
    return text[index:]


def _clean_story_material(text: str, source: Dict[str, Any]) -> str:
    text = (text or "").strip()
    if not text:
        return ""

    # Cabeceras de Project Gutenberg que puedan quedar si falta el marcador.
    for marker in (
        "*** START OF THE PROJECT GUTENBERG",
        "START OF THE PROJECT GUTENBERG EBOOK",
    ):
        index = text.upper().find(marker)
        if index >= 0:
            end = text.find("***", index + len(marker))
            if end >= 0:
                text = text[end + 3:]
            break

    text = re.sub(r"\s*\[\.\.\.\]\s*$", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip(" \n\"'«»")


def _shorten_story_material(text: str, max_chars: int) -> str:
    text = (text or "").strip()
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    last_stop = max(
        cut.rfind(". "),
        cut.rfind("! "),
        cut.rfind("? "),
        cut.rfind("\n"),
    )
    if last_stop > int(max_chars * 0.55):
        cut = cut[: last_stop + 1]
    return cut.rstrip()


def fetch_story_material(
    source: Dict[str, Any],
    timeout: float = 4.5,
    max_chars: int = 1400,
) -> Dict[str, Any]:
    """Descarga y limpia una fuente curada para el modo cuento."""
    cache_key = f"story:{source['id']}:{max_chars}"
    cached = _story_cache_get(cache_key)
    if cached is not None:
        return cached

    # Los libros de Gutenberg llevan delante licencia, indice y prologo: hay
    # que descargar bastante texto para llegar al marcador de contenido.
    fetch_chars = max(max_chars + 2500, 5000)
    if source.get("start_marker"):
        fetch_chars = max(fetch_chars, 60000)

    page = fetch_page(source["url"], timeout=timeout, max_chars=fetch_chars)
    result: Dict[str, Any] = {
        "id": source["id"],
        "title": source["title"],
        "url": page.get("url") or source["url"],
        "site": source["site"],
        "kind": source["kind"],
        "text": "",
        "error": "",
    }
    text = page.get("text") or ""
    if not text.strip():
        result["error"] = page.get("error") or "sin texto"
        return result

    text = _story_material_start(text, source.get("start_marker"))
    text = _clean_story_material(text, source)
    text = _shorten_story_material(text, max_chars)
    if len(text) < 180:
        result["error"] = "texto insuficiente"
        return result

    result["text"] = text
    _story_cache_put(cache_key, result)
    return result


_STORY_KIND_LABEL = {
    "classic": "relato clasico",
    "legend": "leyenda tradicional",
    "didactic": "contenido didactico",
    "cultural": "contenido cultural",
}


def build_story_context_text(source: Dict[str, Any], request: str) -> str:
    kind = source.get("kind") or "classic"
    label = _STORY_KIND_LABEL.get(kind, "material de apoyo")
    lines = [
        f"MATERIAL DE APOYO PARA EL CUENTO ({label}; fuente curada: "
        f"{source['site']} - {source['title']})",
        f"URL: {source['url']}",
        "",
        source.get("text") or "",
        "",
        "INSTRUCCIONES SOBRE EL MATERIAL:",
        "- Inspírate en este material para contar el cuento; no lo copies ni lo "
        "leas literalmente.",
    ]
    if kind in ("classic", "legend"):
        lines.append(
            "- Puedes tomar el ambiente, el conflicto o los personajes, pero "
            "reescribe el relato con tus palabras y cambia los detalles."
        )
    elif kind == "didactic":
        lines.append(
            "- Usa solo datos reales que aparezcan en el material; no inventes "
            "cifras, fechas ni hechos."
        )
    else:
        lines.append(
            "- Respeta la tradicion o cultura del material; si adaptas una "
            "leyenda, hazlo con respeto y sin inventar datos historicos."
        )
    lines.extend(
        [
            "- Si el material no encaja con lo que pide el usuario, conserva "
            "solo el tema o el ambiente.",
            "- Si el material esta en otro idioma, adaptalo y narralo en el "
            "idioma de respuesta.",
            "- El cuento debe ser original, estar en el idioma de respuesta y "
            "tener inicio, nudo y desenlace.",
            "- No menciones la fuente ni la URL dentro del cuento.",
        ]
    )
    return "\n".join(lines)


def gather_story_context(
    text: str,
    lang: str = "es",
    config: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Busca material curado para un cuento y lo prepara para el prompt."""
    cfg = dict(DEFAULTS)
    cfg.update(config or {})
    if not cfg.get("enabled", True):
        return None

    timeout = min(float(cfg.get("timeout_s", 7)), 4.5)
    max_chars = int(cfg.get("story_max_chars", 1400))
    ordered = rank_story_sources(text, lang)

    chosen: Optional[Dict[str, Any]] = None
    for source in ordered[:3]:
        material = fetch_story_material(
            source, timeout=timeout, max_chars=max_chars
        )
        if material.get("text"):
            chosen = material
            break

    if not chosen:
        return None

    _STORY_RECENT.append(chosen["id"])
    del _STORY_RECENT[:-_STORY_RECENT_LIMIT]

    return {
        "query": text,
        "intent": "story",
        "source_id": chosen["id"],
        "sources": [
            {
                "title": chosen["title"],
                "url": chosen["url"],
                "site": _display_site(chosen["site"], chosen["url"]),
            }
        ],
        "context": build_story_context_text(chosen, text),
        "created": time.strftime("%Y-%m-%d %H:%M"),
    }


def build_story_prompt_block(context: Optional[Dict[str, Any]]) -> str:
    """Devuelve el bloque de material curado listo para el prompt."""
    if not context or not context.get("context"):
        return ""
    return "\n\n" + context["context"] + "\n"


def prefetch_story_sources(langs: Tuple[str, ...] = ("es", "en"), per_lang: int = 2) -> None:
    """Precarga en segundo plano las fuentes narrativas mas usadas."""
    for lang in langs:
        ordered = rank_story_sources("", lang)
        for source in ordered[:per_lang]:
            material = fetch_story_material(source, timeout=4.0, max_chars=1400)
            if material.get("text"):
                _safe_print(f"[CUENTO] Fuente preparada: {source['title']}")
            elif material.get("error"):
                _safe_print(
                    f"[CUENTO] Fuente no disponible: {source['title']} "
                    f"({material['error']})"
                )


# ---------------------------------------------------------------------------
# Buscadores
# ---------------------------------------------------------------------------

def wikipedia_lookup(
    query: str, lang: str = "es", timeout: float = 6.0, max_chars: int = 1800
) -> Optional[Dict[str, Any]]:
    """Primer resultado de Wikipedia con su introduccion."""
    started = time.perf_counter()
    for code in (["es", "en"] if lang != "en" else ["en", "es"]):
        remaining = timeout - (time.perf_counter() - started)
        if remaining <= 0.5:
            break
        request_timeout = max(1.5, min(4.0, remaining))
        try:
            search = requests.get(
                f"https://{code}.wikipedia.org/w/api.php",
                params={
                    "action": "query",
                    "list": "search",
                    "srsearch": query,
                    "format": "json",
                    "srlimit": 5,
                    "utf8": 1,
                },
                headers=HEADERS,
                timeout=request_timeout,
            )
            if search.status_code != 200:
                continue
            hits = (search.json().get("query") or {}).get("search") or []
            if not hits:
                continue
            # Elegir el resultado cuyo titulo/snippet comparte mas terminos.
            tokens = {t for t in re.findall(r"\w+", _norm(query)) if len(t) > 2}

            def _hit_score(hit: Dict[str, Any]) -> int:
                title_blob = _norm(hit.get("title", ""))
                snippet_blob = _norm(
                    re.sub(r"<[^>]+>", " ", hit.get("snippet", "") or "")
                )
                score = 0
                for token in tokens:
                    if token in title_blob:
                        score += 3
                    elif token in snippet_blob:
                        score += 1
                return score

            best_hit = max(hits, key=_hit_score) if tokens else hits[0]
            title = best_hit["title"]
            summary = requests.get(
                f"https://{code}.wikipedia.org/api/rest_v1/page/summary/"
                f"{urllib.parse.quote(title.replace(' ', '_'))}",
                headers=HEADERS,
                timeout=request_timeout,
            )
            if summary.status_code != 200:
                continue
            data = summary.json()
            extract = (data.get("extract") or "").strip()
            if not extract:
                continue
            url = (
                (data.get("content_urls") or {}).get("desktop", {}).get("page")
                or f"https://{code}.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}"
            )
            return {
                "title": data.get("title") or title,
                "url": url,
                "site": f"Wikipedia ({code})",
                "text": _truncate(extract, max_chars),
                "snippet": _truncate(extract, 300),
                "kind": "wikipedia",
                "error": "",
            }
        except Exception:
            continue
    return None


def _bing_rss(query: str, limit: int, timeout: float) -> List[Dict[str, Any]]:
    """Respaldo de busqueda: Bing en formato RSS (sin clave).

    Acepta primero los resultados que comparten dos palabras clave y, si no
    hay suficientes, completa con los que comparten al menos una.
    """
    try:
        response = requests.get(
            "https://www.bing.com/search",
            params={"q": query, "format": "rss"},
            headers=HEADERS,
            timeout=timeout,
        )
        if response.status_code != 200:
            return []
        root = ET.fromstring(response.content)
        keywords = _keywords(query)
        specific = [k for k in keywords if k not in _GENERIC_QUERY_WORDS]
        needed = 2 if len(keywords) >= 2 else 1
        strict: List[Dict[str, Any]] = []
        loose: List[Dict[str, Any]] = []
        for item in root.findall(".//item")[: limit * 3]:
            link = (item.findtext("link") or "").strip()
            if not link:
                continue
            title = (item.findtext("title") or "").strip()
            description = re.sub(r"<[^>]+>", "", item.findtext("description") or "")
            blob = _norm(f"{title} {description}")
            # La palabra clave especifica (p. ej. "iphone") es obligatoria:
            # evita resultados que solo comparten "precio".
            if specific and not any(keyword in blob for keyword in specific):
                continue
            overlap = (
                sum(1 for keyword in keywords if keyword in blob) if keywords else needed
            )
            entry = {
                "title": title,
                "url": link,
                "snippet": re.sub(r"\s+", " ", description).strip(),
                "site": _site_name(link),
                "kind": "search",
            }
            if overlap >= needed:
                strict.append(entry)
            elif overlap >= 1:
                loose.append(entry)
        results = strict + [entry for entry in loose if entry not in strict]
        return results[:limit]
    except Exception:
        return []


def _bing_news_rss(
    query: str, limit: int, timeout: float, lang: str = "es"
) -> List[Dict[str, Any]]:
    """Titulares via Bing News RSS; devuelve el enlace directo del medio."""
    try:
        params: Dict[str, Any] = {"q": query, "format": "rss"}
        params["setmkt"] = "en-US" if lang == "en" else "es-ES"
        response = requests.get(
            "https://www.bing.com/news/search",
            params=params,
            headers=HEADERS,
            timeout=timeout,
        )
        if response.status_code != 200:
            return []
        root = ET.fromstring(response.content)
        results: List[Dict[str, Any]] = []
        for item in root.findall(".//item")[: limit * 2]:
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            if not title or not link:
                continue
            # Bing envuelve el enlace real: apiclick.aspx?...&url=https%3a%2f%2f...
            url = link
            try:
                query_params = urllib.parse.parse_qs(urllib.parse.urlparse(link).query)
                real = (query_params.get("url") or [""])[0]
                if real.startswith("http"):
                    url = real
            except Exception:
                pass
            description = re.sub(r"<[^>]+>", "", item.findtext("description") or "")
            published = (item.findtext("pubDate") or "")[:22]
            results.append({
                "title": title,
                "url": url,
                "snippet": re.sub(r"\s+", " ", f"{description} {published}").strip(),
                "site": _site_name(url),
                "kind": "news",
                "engine": "Bing News",
                "error": "",
            })
        return results[:limit]
    except Exception:
        return []


def _wikipedia_search(
    query: str, lang: str, limit: int, timeout: float
) -> List[Dict[str, Any]]:
    """Busqueda de articulos en Wikipedia (API oficial, sin scraping)."""
    code = "en" if lang == "en" else "es"
    try:
        response = requests.get(
            f"https://{code}.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "list": "search",
                "srsearch": query,
                "format": "json",
                "srlimit": max(2, min(10, limit)),
                "utf8": 1,
            },
            headers=HEADERS,
            timeout=timeout,
        )
        if response.status_code != 200:
            return []
        pages = ((response.json().get("query") or {}).get("search") or [])
    except Exception:
        return []
    results: List[Dict[str, Any]] = []
    for page in pages:
        title = str(page.get("title") or "").strip()
        if not title:
            continue
        url = (
            f"https://{code}.wikipedia.org/wiki/"
            + urllib.parse.quote(title.replace(" ", "_"))
        )
        snippet = re.sub(r"<[^>]+>", "", str(page.get("snippet") or ""))
        results.append({
            "title": title,
            "url": url,
            "snippet": re.sub(r"\s+", " ", snippet).strip(),
            "site": f"{code}.wikipedia.org",
            "kind": "page",
            "engine": "Wikipedia",
            "error": "",
        })
    return results


def news_search(
    query: str, limit: int = 4, timeout: float = 6.0, lang: str = "es"
) -> List[Dict[str, Any]]:
    """Titulares recientes via Google News RSS (edicion es o en)."""
    try:
        q = urllib.parse.quote(query or ("latest news" if lang == "en" else "ultima hora"))
        if lang == "en":
            edition = "hl=en&gl=US&ceid=US:en"
        else:
            edition = "hl=es&gl=ES&ceid=ES:es"
        response = requests.get(
            f"https://news.google.com/rss/search?q={q}&{edition}",
            headers=HEADERS,
            timeout=timeout,
        )
        if response.status_code != 200:
            return []
        root = ET.fromstring(response.content)
        results = []
        for item in root.findall(".//item")[:limit]:
            title = (item.findtext("title") or "").strip()
            if not title:
                continue
            source = item.findtext("source") or ""
            published = (item.findtext("pubDate") or "")[:22]
            results.append(
                {
                    "title": title,
                    "url": (item.findtext("link") or "").strip(),
                    "site": source or "Google News",
                    "text": f"{title}. {source} {published}".strip(),
                    "snippet": f"{title} ({source})",
                    "kind": "news",
                    "error": "",
                }
            )
        return results
    except Exception:
        return []


def _search_relevance(query: str, result: Dict[str, Any]) -> int:
    """Puntuacion lexica sencilla: prioriza coincidencias en el titulo."""
    keywords = _keywords(query) - _GENERIC_QUERY_WORDS
    if not keywords:
        return 1
    title = _norm(result.get("title") or "")
    snippet = _norm(result.get("snippet") or result.get("text") or "")
    title_hits = sum(1 for word in keywords if word in title)
    snippet_hits = sum(1 for word in keywords if word in snippet)
    return title_hits * 3 + snippet_hits


def _searxng_search(
    query: str,
    lang: str,
    limit: int,
    timeout: float,
    config: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Consulta la API JSON de la instancia SearXNG local."""
    cfg = config or {}
    base_url = str(cfg.get("searxng_url") or "http://localhost:8080").strip().rstrip("/")
    if not base_url:
        return []
    language = "en-US" if lang == "en" else "es-ES"
    default_engines = ["bing", "google", "duckduckgo"]
    engines = cfg.get("searxng_engines") or default_engines
    engine_list: List[str] = []
    for engine in engines:
        name = str(engine).strip().lower()
        if name and name not in engine_list:
            engine_list.append(name)
    if not engine_list:
        engine_list = list(default_engines)

    for engine in engine_list:
        params: Dict[str, Any] = {
            "q": query,
            "format": "json",
            "language": language,
            "categories": cfg.get("searxng_categories") or "general",
            "safesearch": 0,
            "engines": engine,
        }
        try:
            response = requests.get(
                base_url + "/search",
                params=params,
                headers=HEADERS,
                timeout=timeout,
            )
            if response.status_code != 200:
                continue
            payload = response.json()
            items = payload.get("results", []) if isinstance(payload, dict) else []
            normalized: List[Dict[str, Any]] = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                url = str(item.get("url") or "").strip()
                title = re.sub(r"\s+", " ", str(item.get("title") or "")).strip()
                if not url or not title:
                    continue
                # No se aceptan destinos locales, privados ni esquemas no HTTP.
                allowed, _ = _url_allowed(url)
                if not allowed:
                    continue
                snippet = re.sub(r"\s+", " ", str(item.get("content") or "")).strip()
                normalized.append({
                    "title": title,
                    "url": url,
                    "snippet": snippet,
                    "site": _site_name(url),
                    "kind": "search",
                    "engine": str(item.get("engine") or engine),
                    "published": str(item.get("publishedDate") or ""),
                    "error": "",
                })
            if normalized:
                return normalized[: max(limit * 3, limit)]
        except Exception:
            continue
    return []


def search_web(
    query: str,
    lang: str = "es",
    max_results: int = 3,
    timeout: float = 7.0,
    extra_trusted: Optional[List[str]] = None,
    config: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Busca primero en SearXNG; usa DuckDuckGo/Yandex y Bing RSS como respaldo."""
    cfg = config or {}
    engine = str(cfg.get("search_engine") or "searxng").lower().strip()
    searxng_url = str(cfg.get("searxng_url") or "http://localhost:8080").rstrip("/")
    cache_key = f"search:{engine}:{searxng_url}:{lang}:{max_results}:{_norm(query)}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    wanted = max_results * 3
    normalized: List[Dict[str, Any]] = []

    # Motor prioritario: SearXNG local. Si no responde o no devuelve enlaces
    # validos, se conserva la cadena de respaldo que ya tenia Emma.
    if engine == "searxng":
        normalized = _searxng_search(query, lang, wanted, timeout, cfg)

    if len(normalized) < min(2, wanted):
        raw: List[Dict[str, Any]] = []
        region = "es-es" if lang != "en" else "us-en"
        try:
            from ddgs import DDGS
        except Exception:
            DDGS = None  # type: ignore[assignment]

        if DDGS is not None:
            for backend in ("auto", "yandex"):
                try:
                    with DDGS(timeout=timeout) as ddgs:
                        raw = list(ddgs.text(
                            query,
                            region=region,
                            max_results=wanted,
                            backend=backend,
                        ))
                except Exception:
                    raw = []
                if len(raw) >= min(3, wanted):
                    break

        for item in raw:
            url = (item.get("href") or item.get("url") or "").strip()
            if not url:
                continue
            normalized.append({
                "title": (item.get("title") or "").strip(),
                "url": url,
                "snippet": re.sub(r"\s+", " ", item.get("body") or "").strip(),
                "site": _site_name(url),
                "kind": "search",
                "engine": "DuckDuckGo",
                "error": "",
            })

    def _rank(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filtra destinos inseguros y resultados sin relacion con la consulta."""
        keywords = _keywords(query) - _GENERIC_QUERY_WORDS
        scored: List[Dict[str, Any]] = []
        for result in candidates:
            url = result.get("url") or ""
            allowed, _ = _url_allowed(url)
            if not allowed or _domain_score(url, extra_trusted) < 0:
                continue
            relevance = _search_relevance(query, result)
            if relevance <= 0:
                continue
            # Con dos o mas palabras clave, exigir al menos dos coincidencias:
            # evita que "Sam Altman" acepte una pagina que solo dice "SAM".
            if len(keywords) >= 2:
                haystack = _norm(
                    f"{result.get('title') or ''} "
                    f"{result.get('snippet') or result.get('text') or ''}"
                )
                if sum(1 for word in keywords if word in haystack) < 2:
                    continue
            item = dict(result)
            item["relevance"] = relevance
            scored.append(item)
        scored.sort(
            key=lambda r: (
                r.get("relevance", 0),
                _domain_score(r["url"], extra_trusted),
                len(r.get("snippet") or ""),
            ),
            reverse=True,
        )
        return scored

    ranked = _rank(normalized)

    if len(ranked) < max_results:
        ranked = _rank(normalized + _bing_rss(query, wanted, timeout))

    # Los buscadores generales estan bloqueados por captcha/anti-bot en esta
    # red; los RSS de noticias responden bien y se consultan en paralelo.
    if len(ranked) < max_results:
        with ThreadPoolExecutor(max_workers=2) as executor:
            google_future = executor.submit(news_search, query, wanted, timeout, lang)
            bing_future = executor.submit(_bing_news_rss, query, wanted, timeout, lang)
            try:
                news_items = google_future.result()
            except Exception:
                news_items = []
            try:
                bing_items = bing_future.result()
            except Exception:
                bing_items = []
        ranked = _rank(normalized + news_items + bing_items)

    # Ultimo recurso para consultas de entidades: API de Wikipedia.
    if not ranked:
        ranked = _rank(_wikipedia_search(query, lang, wanted, timeout))

    chosen: List[Dict[str, Any]] = []
    seen_urls = set()
    per_domain: Dict[str, int] = {}
    for result in ranked:
        key = _url_key(result["url"])
        if key in seen_urls:
            continue
        domain = _site_name(result["url"])
        if per_domain.get(domain, 0) >= 1:
            continue
        seen_urls.add(key)
        per_domain[domain] = 1
        chosen.append(result)
        if len(chosen) >= max_results:
            break
    if chosen:
        _cache_put(cache_key, chosen)
    return chosen


# ---------------------------------------------------------------------------
# Orquestacion
# ---------------------------------------------------------------------------

def gather_context(
    text: str,
    lang: str = "es",
    previous: str = "",
    config: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Reune contexto web para una consulta.

    Devuelve None si no hace falta buscar. Si busca, devuelve un dict con
    ``sources`` (para la UI) y ``context`` (bloque de texto para el LLM).
    """
    cfg = dict(DEFAULTS)
    cfg.update(config or {})
    if not cfg.get("enabled", True):
        return None

    intent = detect_intent(text)
    if intent is None:
        return None

    timeout = float(cfg.get("timeout_s", 7))
    max_chars = int(cfg.get("max_chars", 2200))
    max_results = int(cfg.get("max_results", 3))
    fetch_pages = int(cfg.get("fetch_pages", 2))
    extra_trusted = list(cfg.get("extra_trusted_domains") or [])
    sources: List[Dict[str, Any]] = []

    if intent == "url":
        urls = extract_urls(text)
        for url in urls[:2]:
            page = fetch_page(url, timeout=timeout, max_chars=max_chars)
            if page.get("text"):
                sources.append(page)
            elif page.get("error"):
                sources.append(
                    {
                        "title": page.get("title") or url,
                        "url": url,
                        "site": _site_name(url),
                        "text": "",
                        "snippet": f"No se pudo leer la pagina: {page['error']}",
                        "kind": "page",
                        "error": page["error"],
                    }
                )
        query = urls[0] if urls else text
        kind = "url"
    else:
        query = clean_query(text)
        query = _merge_followup(query, clean_query(previous))

        news_items: List[Dict[str, Any]] = []
        if intent == "news" and cfg.get("news", True):
            news_items = news_search(
                query, limit=max_results + 1, timeout=timeout, lang=lang
            )

        # Wikipedia y DuckDuckGo son independientes: se lanzan en paralelo.
        results: List[Dict[str, Any]] = []
        wiki: Optional[Dict[str, Any]] = None
        if cfg.get("wikipedia", True):
            with ThreadPoolExecutor(max_workers=2) as executor:
                search_future = executor.submit(
                    search_web,
                    query,
                    lang,
                    max_results + 2,
                    timeout,
                    extra_trusted,
                    cfg,
                )
                wiki_future = executor.submit(
                    wikipedia_lookup, _entity_query(query), lang, timeout, max_chars
                )
                try:
                    results = search_future.result()
                except Exception:
                    results = []
                try:
                    wiki = wiki_future.result()
                except Exception:
                    wiki = None
            if not (_wants_wikipedia(text) or len(results) < 2):
                wiki = None
        else:
            results = search_web(
                query,
                lang=lang,
                max_results=max_results + 2,
                timeout=timeout,
                extra_trusted=extra_trusted,
                config=cfg,
            )

        # Descargar en paralelo solo si aporta: con Wikipedia ya hay texto de sobra.
        fetch_candidates: List[Dict[str, Any]] = []
        if intent != "news" and fetch_pages > 0 and not wiki:
            fetch_candidates = [r for r in results if r.get("kind") == "search"][:fetch_pages]
        fetched: Dict[str, Dict[str, Any]] = {}
        if fetch_candidates:
            with ThreadPoolExecutor(max_workers=len(fetch_candidates)) as executor:
                futures = {
                    executor.submit(fetch_page, r["url"], timeout, max_chars): r["url"]
                    for r in fetch_candidates
                }
                try:
                    for future in as_completed(futures, timeout=timeout + 2):
                        url = futures[future]
                        try:
                            page = future.result()
                        except Exception:
                            continue
                        if page.get("text"):
                            fetched[url] = page
                except Exception:
                    pass

        # Orden: noticias, Wikipedia, paginas descargadas y snippets.
        ordered: List[Dict[str, Any]] = list(news_items)
        if wiki:
            ordered.append(wiki)
        for result in results:
            page = fetched.get(result["url"])
            if page and page.get("text"):
                merged = dict(result)
                merged["text"] = page["text"]
                merged["title"] = page.get("title") or result.get("title") or result["url"]
                ordered.append(merged)
            else:
                ordered.append(result)

        seen = set()
        final: List[Dict[str, Any]] = []
        for source in ordered:
            key = _url_key(source["url"])
            if key in seen:
                continue
            seen.add(key)
            final.append(source)
        sources = final[: max_results + 1]
        kind = "news" if intent == "news" else "search"

    if not sources:
        return None

    for index, source in enumerate(sources, start=1):
        if not source.get("text"):
            source["text"] = source.get("snippet") or "(sin contenido extraido)"
        source["rank"] = index

    context = build_context_text(query, kind, sources)
    return {
        "query": query,
        "intent": kind,
        "sources": [
            {
                "title": s.get("title") or s["url"],
                "url": s["url"],
                "site": _display_site(s.get("site") or "", s["url"]),
            }
            for s in sources
        ],
        "context": context,
        "created": time.strftime("%Y-%m-%d %H:%M"),
    }


def build_context_text(query: str, kind: str, sources: List[Dict[str, Any]]) -> str:
    """Construye el bloque de contexto que se inyecta en el prompt."""
    label = {
        "url": "pagina indicada por el usuario",
        "news": "noticias recientes",
        "search": "busqueda web",
    }.get(kind, "busqueda web")

    lines = [
        f"CONTEXTO WEB ({label}; consulta: {query}; fecha: {time.strftime('%d/%m/%Y %H:%M')})",
        "",
    ]
    for index, source in enumerate(sources, start=1):
        title = source.get("title") or source["url"]
        site = _display_site(source.get("site") or "", source["url"])
        lines.append(f"[Fuente {index}] {site} - {title}")
        lines.append(f"URL: {source['url']}")
        text = source.get("text") or source.get("snippet") or ""
        lines.append(f"Contenido: {text}")
        lines.append("")
    lines.extend(
        [
            "INSTRUCCIONES SOBRE EL CONTEXTO WEB:",
            "- Usa este contexto como fuente principal para responder.",
            "- Empieza la respuesta citando la fuente principal de forma natural "
            "('segun Wikipedia, ...' o 'segun la BBC, ...'). No leas URLs ni "
            "dominios con .com/.es en voz alta.",
            "- Responde en dos o tres frases seguidas, sin listas ni viñetas: "
            "la respuesta se escucha en voz alta.",
            "- Si hay varias cifras o precios, da el mas relevante o un rango corto.",
            "- Si las fuentes no responden a la pregunta, dilo con claridad y no inventes datos.",
            "- No inventes cifras, precios ni fechas: usa solo las que aparezcan en el "
            "contexto; si no aparecen, dilo.",
            "- Prioriza datos concretos y recientes; ignora publicidad o texto de navegacion.",
            "- Mantén el formato JSON habitual de respuesta.",
        ]
    )
    return "\n".join(lines)


def build_prompt_block(context: Dict[str, Any]) -> str:
    """Devuelve el bloque listo para anexar al prompt del sistema."""
    if not context or not context.get("context"):
        return ""
    return "\n\n" + context["context"] + "\n"


# ---------------------------------------------------------------------------
# Prueba por linea de comandos
# ---------------------------------------------------------------------------

def _main(argv: List[str]) -> int:
    if len(argv) < 2:
        _safe_print("Uso: python web_tools.py \"consulta o URL\"")
        return 1
    text = " ".join(argv[1:])
    _safe_print(f"Texto: {text}")
    _safe_print(f"Intencion: {detect_intent(text)}")

    started = time.perf_counter()
    context = gather_context(text)
    elapsed = (time.perf_counter() - started) * 1000
    if not context:
        _safe_print("No se requiere busqueda web.")
        return 0

    _safe_print(f"Consulta: {context['query']} ({context['intent']}) en {elapsed:.0f} ms")
    _safe_print(f"Fuentes: {len(context['sources'])}")
    for source in context["sources"]:
        _safe_print(f"- {source['site']}: {source['title']}")
        _safe_print(f"  {source['url']}")
    _safe_print("\n--- Contexto para el LLM ---\n")
    _safe_print(context["context"])
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv))
