from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from scraper import AnimeScraper
from keep_alive import start_keep_alive

app = FastAPI(title="Lopi Anime API", version="2.0.0", description="Catálogo unificado y fuentes por proveedor")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])
scraper = AnimeScraper()

@app.on_event("startup")
def startup_event():
    start_keep_alive()

@app.get("/")
def root():
    return {"name": "Lopi Anime API", "version": "2.0.0", "status": "online", "docs": "/docs"}

@app.get("/health")
def health():
    return {"status": "ok", "providers": ["animeflv", "jkanime", "tioanime", "monoschinos"]}

@app.get("/ping")
def ping():
    return {"ping": "pong", "active": True}

@app.get("/api/providers")
def providers():
    from scraper import PROVIDERS
    return {"success": True, "data": [{"id": p["id"], "name": p["name"], "language": p["language"]} for p in PROVIDERS]}

@app.get("/api/catalog")
def catalog(provider: str | None = None, page: int = Query(1, ge=1)):
    return scraper.get_catalog(page, provider)

@app.get("/api/latest")
def latest_anime():
    return scraper.get_latest_episodes()

@app.get("/api/search")
def search_anime(q: str = Query(..., min_length=2), provider: str | None = None):
    return scraper.search_anime(q, provider)

@app.get("/api/anime/info")
def anime_info(url: str):
    try:
        return scraper.get_anime_info(url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"No se pudo obtener la ficha: {str(exc)[:240]}")

@app.get("/api/info")
def anime_info_compat(url: str):
    return anime_info(url)

@app.get("/api/episode")
def episode_sources(url: str):
    return episode_sources_common(url)

def episode_sources_common(url: str):
    try:
        return scraper.get_episode_sources(url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"No se pudieron consultar las fuentes: {str(exc)[:240]}")

@app.get("/api/episode/encoded_id")
def episode_sources_query(link: str):
    return episode_sources_common(link)

@app.get("/api/episode/{episode_id:path}")
def episode_sources_path(episode_id: str):
    # Compatibility: clients may pass a full URL as a path or a URL-encoded identifier.
    from urllib.parse import unquote
    value = unquote(episode_id)
    if not value.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Usa ?url=<URL del episodio>")
    return episode_sources_common(value)

@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc):
    return JSONResponse(status_code=500, content={"success": False, "error": "Error interno del servidor"})
