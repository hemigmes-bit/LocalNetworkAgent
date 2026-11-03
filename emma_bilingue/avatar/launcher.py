#!/usr/bin/env python3
"""
Emma Avatar Launcher - Conecta a servidores ya corriendo
"""
import sys
import os
import webview
import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
sys.path.insert(0, PROJECT_ROOT)

def wait_for_server(url, timeout=10):
    """Espera a que un servidor responda"""
    import time
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = requests.get(url, timeout=2)
            if resp.status_code == 200:
                return True
        except:
            pass
        time.sleep(0.5)
    return False

def main():
    print("[START] Emma Bilingue - Avatar VRM")
    print("=" * 50)
    
    # Verificar servidores existentes
    print("[INFO] Verificando FastAPI (puerto 8000)...")
    if not wait_for_server('http://localhost:8000/health'):
        print("[ERROR] FastAPI no esta corriendo en puerto 8000")
        print("   Ejecuta: python -m uvicorn server.main:app --host 0.0.0.0 --port 8000")
        return
    print("[OK] FastAPI listo")
    
    print("[INFO] Verificando Avatar server (puerto 5173)...")
    if not wait_for_server('http://localhost:5173'):
        print("[ERROR] Avatar server no esta corriendo en puerto 5173")
        print("   Ejecuta: cd avatar/dist && python -m http.server 5173")
        return
    print("[OK] Avatar server listo")
    
    # Crear ventanas pywebview
    print("[INFO] Abriendo ventanas...")
    
    # Ventana principal: Avatar VRM
    avatar_window = webview.create_window(
        'Emma Avatar - VRM',
        'http://localhost:5173',
        width=600,
        height=800,
        min_size=(400, 500),
        resizable=True,
        x=100, y=100
    )
    
    # Ventana secundaria: Chat/Control (FastAPI client.html)
    chat_window = webview.create_window(
        'Emma Chat - Control',
        'http://localhost:8000',
        width=500,
        height=700,
        min_size=(400, 500),
        resizable=True,
        x=750, y=100
    )
    
    def on_closing():
        print("\n[INFO] Cerrando aplicacion...")
    
    avatar_window.events.closing += on_closing
    chat_window.events.closing += on_closing
    
    print("[OK] Aplicacion lista")
    print("   - Avatar VRM: http://localhost:5173")
    print("   - Chat/Control: http://localhost:8000")
    print("   - WebSocket: ws://localhost:8000/ws")
    
    # Iniciar loop de pywebview
    webview.start(debug=False, storage_path=os.path.join(BASE_DIR, 'webview_data'))

if __name__ == '__main__':
    main()