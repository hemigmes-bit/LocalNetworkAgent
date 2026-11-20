with open(r'C:\Users\Usuario\LocalNetworkAgent\emma_bilingue\avatar\index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the saveApiKey function - make it async
content = content.replace(
    'function saveApiKey() {',
    'async function saveApiKey() {'
)

with open(r'C:\Users\Usuario\LocalNetworkAgent\emma_bilingue\avatar\index.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed!")