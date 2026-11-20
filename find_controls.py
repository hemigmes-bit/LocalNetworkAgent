with open(r'C:\Users\Usuario\LocalNetworkAgent\emma_bilingue\avatar\index.html', 'r') as f:
    content = f.read()
    idx = content.find('<div class="controls">')
    if idx >= 0:
        print(content[idx:idx+800])