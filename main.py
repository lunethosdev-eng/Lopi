from urllib.parse import unquote
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, HttpUrl
from scraper import AnimeScraper, PROVIDERS
from download_service import download_mp4, get_download_path
from keep_alive import start_keep_alive

app=FastAPI(title="Lopy Anime API",version="3.0.0",description="Catálogo multi-fuente, render JavaScript, episodios y medios directos públicos.")
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_credentials=False,allow_methods=["*"],allow_headers=["*"])
scraper=AnimeScraper()

@app.on_event("startup")
def startup_event(): start_keep_alive()

@app.get("/")
def root(): return {"name":"Lopy Anime API","version":"3.0.0","status":"online","docs":"/docs","providers":[p["id"] for p in PROVIDERS],"javascriptRenderer":True}

@app.get("/health")
@app.get("/ping")
def health(): return {"status":"ok","ping":"pong","active":True,"providers":[p["id"] for p in PROVIDERS]}

@app.get("/api/providers")
def providers():
    return {"success":True,"total":len(PROVIDERS),"data":[{"id":p["id"],"name":p["name"],"language":p["language"],"base":p["base"],"type":"metadata-api" if p["id"] in ("anilist","jikan","kitsu") else "web"} for p in PROVIDERS]}

@app.get("/api/catalog")
@app.get("/api/v1/anime/catalog")
def catalog(provider:str|None=None,page:int=Query(1,ge=1)): return scraper.get_catalog(page,provider)

@app.get("/api/latest")
def latest(): return scraper.get_latest_episodes()

@app.get("/api/search")
@app.get("/api/v1/anime/search")
def search(q:str=Query(...,min_length=2),provider:str|None=None,domain:str|None=None): return scraper.search_anime(q,provider or domain)

def info_common(url):
    try:return scraper.get_anime_info(url)
    except ValueError as e:raise HTTPException(400,str(e))
    except Exception as e:raise HTTPException(502,"No se pudo obtener la ficha: "+str(e)[:200])

@app.get("/api/anime/info")
@app.get("/api/info")
@app.get("/api/v1/anime/info")
def anime_info(url:str):return info_common(url)

def episode_common(url):
    try:return scraper.get_episode_sources(url)
    except ValueError as e:raise HTTPException(400,str(e))
    except Exception as e:raise HTTPException(502,"No se pudieron consultar las fuentes: "+str(e)[:200])

@app.get("/api/episode")
@app.get("/api/v1/anime/episode")
def episode(url:str):return episode_common(url)

@app.get("/api/episode/encoded_id")
def episode_encoded(link:str):return episode_common(link)

@app.get("/api/episode/{episode_id:path}")
def episode_path(episode_id:str):
    value=unquote(episode_id)
    if not value.startswith(("http://","https://")):raise HTTPException(400,"Usa ?url=<URL del episodio>")
    return episode_common(value)

@app.get("/api/resolve")
@app.get("/api/v1/anime/resolve")
def resolve(url:str):
    try:return scraper.resolve_source(url)
    except ValueError as e:raise HTTPException(400,str(e))

class DownloadRequest(BaseModel):
    url: HttpUrl
    referer: HttpUrl|None=None

@app.post("/api/download")
def download_test(body:DownloadRequest):
    """Temporary FFmpeg test for a direct public MP4 only; no embeds or DRM."""
    return download_mp4(str(body.url),str(body.referer) if body.referer else None)

@app.get("/api/download/{token}")
def get_test_download(token:str):
    path=get_download_path(token)
    return FileResponse(path,media_type="video/mp4",filename=path.name)

@app.exception_handler(Exception)
async def unhandled(request,exc):
    return JSONResponse(status_code=500,content={"success":False,"error":"Error interno del servidor"})
