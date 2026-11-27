from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from scraper import AnimeScraper
from keep_alive import start_keep_alive

app = FastAPI(title="Oxy Anime Backend", version="1.0.0")

# Configuración abierta de CORS para evitar bloqueos con la web de prueba y la APK
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

scraper = AnimeScraper()

@app.on_event("startup")
def startup_event():
    start_keep_alive()

@app.get("/")
def read_root():
    return {"message": "Bienvenido al Backend de Oxy Anime 🚀", "status": "online"}

@app.get("/ping")
def ping():
    return {"ping": "pong", "active": True}

@app.get("/api/latest")
def latest_anime():
    return scraper.get_latest_episodes()

@app.get("/api/search")
def search_anime(q: str):
    return scraper.search_anime(q)

@app.get("/api/episode/encoded_id")
def episode_sources_query(link: str):
    return scraper.get_episode_sources(link)

@app.get("/api/episode/{episode_id}")
def episode_sources_path(episode_id: str):
    return scraper.get_episode_sources(episode_id)
