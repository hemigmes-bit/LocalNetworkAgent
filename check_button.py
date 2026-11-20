with open(r'C:\Users\Usuario\LocalNetworkAgent\emma_bilingue\avatar\index.html', 'r', encoding='utf-8') as f:
    content = f.read()
    idx = content.find('onclick="openSettings()"')
    if idx >= 0:
        print(content[max(0,idx-100):idx+200])
    else:
        print('NOT FOUND: onclick openSettings')
        # Search for btn-settings in HTML body
        idx2 = content.find('id="btn-settings"')
        if idx2 >= 0:
            print('FOUND id at:', idx2)
            print(content[max(0,idx2-100):idx2+200])