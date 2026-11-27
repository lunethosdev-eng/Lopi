import os

class Settings:
    PROJECT_NAME: str = "Oxy Anime API"
    VERSION: str = "1.0.0"
    # Simula un navegador real para esquivar filtros básicos
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    }

settings = Settings()
