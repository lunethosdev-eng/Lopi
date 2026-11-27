from urllib.parse import unquote

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from scraper import AnimeScraper, PROVIDERS
from keep_alive import start_keep_alive

app = FastAPI(
    title="Lopi Anime API",
    version="2.2.0",
    description="Catálogo multi-proveedor, fichas, episodios y fuentes detectadas. Sin HentaiLA.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
scraper = AnimeScraper()


@app.on_event("startup")
def startup_event():
    start_keep_alive()


@app.get("/")
def root():
    return {
        "name": "Lopi Anime API",
        "version": "2.2.0",
        "status": "online",
        "docs": "/docs",
        "providers": [p["id"] for p in PROVIDERS],
    }


@app.get("/health")
@app.get("/ping")
def health():
    return {"status": "ok", "ping": "pong", "active": True,
            "providers": [p["id"] for p in PROVIDERS]}


@app.get("/api/providers")
def providers():
    return {"success": True, "data": [
        {"id": p["id"], "name": p["name"], "language": p["language"], "base": p["base"]}
        for p in PROVIDERS
    ]}


@app.get("/api/catalog")
@app.get("/api/v1/anime/catalog")
def catalog(provider: str | None = None, page: int = Query(1, ge=1)):
    return scraper.get_catalog(page, provider)


@app.get("/api/latest")
def latest_anime():
    return scraper.get_latest_episodes()


@app.get("/api/search")
@app.get("/api/v1/anime/search")
def search_anime(q: str = Query(..., min_length=2), provider: str | None = None,
                 domain: str | None = None):
    return scraper.search_anime(q, provider or domain)


def anime_info_common(url: str):
    try:
        return scraper.get_anime_info(url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"No se pudo obtener la ficha: {str(exc)[:240]}")


@app.get("/api/anime/info")
@app.get("/api/info")
@app.get("/api/v1/anime/info")
def anime_info(url: str):
    return anime_info_common(url)


def episode_sources_common(url: str):
    try:
        return scraper.get_episode_sources(url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"No se pudieron consultar las fuentes: {str(exc)[:240]}")


@app.get("/api/episode")
@app.get("/api/v1/anime/episode")
def episode_sources(url: str):
    return episode_sources_common(url)


@app.get("/api/episode/encoded_id")
def episode_sources_query(link: str):
    return episode_sources_common(link)


@app.get("/api/episode/{episode_id:path}")
def episode_sources_path(episode_id: str):
    value = unquote(episode_id)
    if not value.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Usa ?url=<URL del episodio>")
    return episode_sources_common(value)


@app.get("/api/resolve")
@app.get("/api/v1/anime/resolve")
def resolve_source(url: str):
    """Classifies direct media URLs; embed pages remain embeds unless directly exposed."""
    try:
        return scraper.resolve_source(url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc):
    return JSONResponse(status_code=500, content={
        "success": False,
        "error": "Error interno del servidor",
    })
