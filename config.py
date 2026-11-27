import os

class Settings:
    PROJECT_NAME = "Lopi Anime API"
    VERSION = "2.2.0"
    REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "12"))
    RETRIES = int(os.getenv("REQUEST_RETRIES", "1"))
    MAX_WORKERS = int(os.getenv("MAX_WORKERS", "8"))
    CACHE_TTL = int(os.getenv("CACHE_TTL", "300"))
    HEADERS = {
        "User-Agent": os.getenv("USER_AGENT", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"),
        "Accept-Language": "es-419,es;q=0.9,en;q=0.7",
    }
    EMBED_HOST_ALLOWLIST = tuple(x.strip().lower() for x in os.getenv("EMBED_HOST_ALLOWLIST", "voe.sx,streamtape.com,streamwish.to,streamwish.com,vidhide.com,doodstream.com,streamlare.com").split(",") if x.strip())

settings = Settings()
