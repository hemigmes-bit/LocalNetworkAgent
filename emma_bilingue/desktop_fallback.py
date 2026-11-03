#!/usr/bin/env python3
"""
Emma Bilingüe - Desktop App (pywebview fallback)
Lanza FastAPI en hilo separado y abre ventana webview
"""
import webview
import threading
import sys
import os
import time

# Añadir path del proyecto
sys.path.insert(0, r"C:\Users\Usuario\LocalNetworkAgent\emma_bilingue")

from server.main import app
import uvicorn

def start_fastapi():
    """Inicia FastAPI en hilo separado"""
    uvicorn.run("server.main:app", host="127.0.0.1", port=8000, log_level="warning")

def on_closing():
    """Callback al cerrar la ventana"""
    print("🔄 Cerrando aplicación...")
    # Los hilos daemon se cerrarán automáticamente

def main():
    print("[START] Iniciando Emma Bilingüe - Desktop App (pywebview)")
    
    # 1. Iniciar FastAPI en hilo separado
    api_thread = threading.Thread(target=start_fastapi, daemon=True)
    api_thread.start()
    
    # Esperar a que FastAPI esté listo
    print("[WAIT] Esperando a que FastAPI inicie...")
    time.sleep(3)
    
    # Verificar que el servidor responde
    import urllib.request
    for i in range(10):
        try:
            import urllib.request
            response = urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=2)
            if response.getcode() == 200:
                print("[OK] FastAPI listo y respondiendo")
                break
        except:
            time.sleep(0.5)
    else:
        print("[ERROR] FastAPI no respondió a tiempo")
        return
    
    print("[OK] FastAPI listo - Abriendo ventana...")
    
    # Crear ventana webview
    window = webview.create_window(
        "Emma Bilingüe - Tutor de Inglés",
        "http://127.0.0.1:8000",
        width=1200,
        height=800,
        min_size=(800, 600),
        resizable=True,
        text_select=True
    )
    
    # Configurar cierre
    def on_closing():
        print("[CLOSE] Cerrando aplicación...")
        # Los hilos daemon se cerrarán automáticamente
    
    window.events.closing += on_closing
    
    print("[GUI] Abriendo ventana de Emma Bilingüe...")
    webview.start(debug=False, storage_path=os.path.join(os.path.dirname(__file__), "webview_data"))

if __name__ == "__main__":
    # Configurar path
    import sys
    sys.path.insert(0, r"C:\Users\Usuario\LocalNetworkAgent\emma_bilingue")
    
    # Cambiar al directorio del proyecto
    os.chdir(r"C:\Users\Usuario\LocalNetworkAgent\emma_bilingue")
    
    main()