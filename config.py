import os

class Settings:
    PROJECT_NAME = "Lopy Anime API"
    VERSION = "3.0.0"
    REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "18"))
    RETRIES = int(os.getenv("REQUEST_RETRIES", "1"))
    MAX_WORKERS = int(os.getenv("MAX_WORKERS", "6"))
    CACHE_TTL = int(os.getenv("CACHE_TTL", "240"))
    JS_RENDER_TIMEOUT = int(os.getenv("JS_RENDER_TIMEOUT", "35"))
    JS_RENDER_ENABLED = os.getenv("JS_RENDER_ENABLED", "true").lower() == "true"
    HEADERS = {
        "User-Agent": os.getenv("USER_AGENT", "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"),
        "Accept-Language": os.getenv("ACCEPT_LANGUAGE", "es-419,es;q=0.9,en;q=0.7,ja;q=0.5"),
    }

settings = Settings()
