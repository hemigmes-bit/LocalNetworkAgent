with open(r'C:\Users\Usuario\LocalNetworkAgent\emma_bilingue\avatar\index.html', 'r', encoding='utf-8') as f:
    content = f.read()
    
idx = content.find('id="btn-settings"')
if idx >= 0:
    snippet = content[max(0,idx-100):idx+200]
    # Remove non-ASCII
    snippet = snippet.encode('ascii', 'replace').decode('ascii')
    print(snippet)
else:
    print('NOT FOUND')