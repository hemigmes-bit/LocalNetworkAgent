import urllib.parse, urllib.request, re, html as html_mod

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

def get(url, timeout=15):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")

# Test lite.duckduckgo.com
q = urllib.parse.quote("python programming language")
h = get("https://lite.duckduckgo.com/lite/?q=" + q)
links = re.findall(r'<td class="link"><a href="([^"]+)">(.*?)</a>', h, re.S)
print("Lite DDG results:", len(links))
for href, title in links[:3]:
    print(" -", html_mod.unescape(title.strip()), "->", html_mod.unescape(href))