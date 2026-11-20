import sys
sys.path.insert(0, r'C:\Users\Usuario\LocalNetworkAgent\emma-android')
with open(r'C:\Users\Usuario\LocalNetworkAgent\emma-android\emma.py', 'r', encoding='utf-8') as f:
    c = f.read()
old = '''    voice.speak(text, load_config(), lang=args.lang or \
en\)
    print(\[VOZ]
Reproduciendo:

\.format(text))'''
new = '''voice.speak(text, load_config(), lang=args.lang or \en\)
print(\[VOZ]
Listo.
Presiona
Enter
para
continuar.\)
input()'''
if old in c:
    c = c.replace(old, new)
    with open(r'C:\Users\Usuario\LocalNetworkAgent\emma-android\emma.py', 'w', encoding='utf-8') as f:
        f.write(c)
    print('OK')
else:
    print('Patrón no encontrado')

