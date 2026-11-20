import urllib.parse, urllib.request, re, html as html_mod

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

def get(url, timeout=15):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")

# Test HTML endpoint with a different pattern
q = urllib.parse.quote("python programming language")
h = get("https://html.duckduckgo.com/html/?q=" + q)

# Try different patterns
patterns = [
    r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
    r'class="result__url"[^>]*>(.*?)</a>',
    r'<a[^>]*class="[^"]*result__a[^"]*"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
]

for i, pat in enumerate(patterns):
    links = re.findall(pat, h, re.S)
    print(f"Pattern {i}: {len(links)} results")
    for href, title in links[:2]:
        print("  -", html_mod.unescape(title.strip())[:60], "->", html_mod.unescape(href)[:80])
    print()

# Check if HTML contains "result" at all
if "result" in h.lower():
    print("HTML contains 'result'")
else:
    print("HTML does NOT contain 'result'")
    # Print first 500 chars to see structure
    print("First 500 chars:", h[:500])