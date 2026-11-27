import threading
import time
import requests
import os

def ping_self():
    app_url = os.getenv("RENDER_EXTERNAL_URL", "http://localhost:10000") + "/ping"
    while True:
        try:
            requests.get(app_url)
        except Exception:
            pass
        time.sleep(600)  # Ping cada 10 minutos para evitar el apagado de Render

def start_keep_alive():
    t = threading.Thread(target=ping_self, daemon=True)
    t.start()
