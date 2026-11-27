import threading
import time
import requests
import os

def ping_self():
    # Render URL de tu servicio desplegado
    app_url = os.getenv("RENDER_EXTERNAL_URL", "http://localhost:8000") + "/ping"
    while True:
        try:
            requests.get(app_url)
        except Exception:
            pass
        # Hace ping cada 10 minutos para evitar que Render entre en modo suspensión (14 min)
        time.sleep(600)

def start_keep_alive():
    t = threading.Thread(target=ping_self, daemon=True)
    t.start()
