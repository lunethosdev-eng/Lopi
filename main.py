from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from scraper import AnimeScraper, ProviderError
from keep_alive import start_keep_alive

app = FastAPI(title="Lopi Anime API", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False,
                   allow_methods=["GET"], allow_headers=["*"])
scraper = AnimeScraper()

@app.on_event("startup")
def startup_event():
    start_keep_alive()

@app.get("/")
def root():
    return {"message": "Lopi Anime API", "status": "online", "version": "2.0.0",
            "providers": ["AnimeFLV", "JKAnime", "TioAnime", "MonosChinos"],
            "hentaila": False}

@app.get("/ping")
def ping():
    return {"ping": "pong", "active": True}

@app.get("/health")
def health():
    return {"success": True, "status": "ok"}

@app.get("/api/latest")
def latest_anime():
    try: return scraper.get_latest_episodes()
    except Exception as exc: raise HTTPException(502, detail=str(exc))

@app.get("/api/search")
def search_anime(q: str = Query(..., min_length=2), provider: str = None):
    try: return scraper.search_anime(q, provider)
    except Exception as exc: raise HTTPException(502, detail=str(exc))

@app.get("/api/anime/info")
@app.get("/api/info")
def anime_info(url: str):
    try: return scraper.get_anime_info(url)
    except ProviderError as exc: raise HTTPException(400, detail=str(exc))
    except Exception as exc: raise HTTPException(502, detail=str(exc))

@app.get("/api/episode/encoded_id")
def episode_sources_query(link: str):
    try: return scraper.get_episode_sources(link)
    except ProviderError as exc: raise HTTPException(400, detail=str(exc))
    except Exception as exc: raise HTTPException(502, detail=str(exc))

@app.get("/api/episode/{episode_id}")
def episode_sources_path(episode_id: str):
    # Backward compatibility: old clients may pass a URL or an encoded URL.
    from urllib.parse import unquote
    value = unquote(episode_id)
    try: return scraper.get_episode_sources(value)
    except ProviderError as exc: raise HTTPException(400, detail=str(exc))
    except Exception as exc: raise HTTPException(502, detail=str(exc))
