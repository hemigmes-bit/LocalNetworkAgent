import json, urllib.parse, urllib.request, re, html as html_mod

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def get(url, timeout=15):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


q = urllib.parse.quote("python programming language")
h = get("https://html.duckduckgo.com/html/?q=" + q)
links = re.findall(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', h, re.S)
snips = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', h, re.S)
print("DDG resultados:", len(links), "| snippets:", len(snips))
for i, (href, title) in enumerate(links[:3]):
    t = html_mod.unescape(re.sub(r"<[^>]+>", "", title)).strip()
    s = ""
    if i < len(snips):
        s = html_mod.unescape(re.sub(r"<[^>]+>", "", snips[i])).strip()
    print(" -", t[:70], "->", html_mod.unescape(href)[:60])
    print("   ", s[:100])

print()
try:
    d = json.loads(get("https://api.duckduckgo.com/?format=json&no_html=1&q=" + q))
    print("InstantAnswer Abstract:", (d.get("AbstractText") or "")[:120])
except Exception as e:
    print("InstantAnswer FALLO:", e)

print()
try:
    w = json.loads(get("https://es.wikipedia.org/api/rest_v1/page/summary/Python"))
    print("Wikipedia:", w.get("title"), "->", (w.get("extract") or "")[:120])
except Exception as e:
    print("Wikipedia FALLO:", e)
