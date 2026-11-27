"""Temporary test copies for explicit, public MP4 URLs only."""
import ipaddress, os, re, secrets, socket, subprocess, time
from pathlib import Path
from urllib.parse import urlparse, urljoin
import requests
from fastapi import HTTPException

TMP=Path(os.getenv("LOPY_TEMP_DIR","/tmp/lopy-anime-tests")); TMP.mkdir(parents=True,exist_ok=True)
TTL=int(os.getenv("TEMP_DOWNLOAD_TTL","3600")); MAX_BYTES=int(os.getenv("TEMP_DOWNLOAD_MAX_BYTES",str(350*1024*1024)))

def _public_host(url):
    p=urlparse(url or "")
    if p.scheme not in ("http","https") or not p.hostname or p.username or p.password: raise HTTPException(400,"URL http(s) pública requerida")
    try: ips={x[4][0] for x in socket.getaddrinfo(p.hostname,None)}
    except Exception: raise HTTPException(400,"No se pudo resolver el host de la fuente")
    if not ips or any(not ipaddress.ip_address(x).is_global for x in ips): raise HTTPException(400,"Host no público o no permitido")
    return p

def cleanup():
    now=time.time()
    for f in TMP.glob("*.mp4"):
        try:
            if now-f.stat().st_mtime>TTL:f.unlink(missing_ok=True)
        except OSError:pass

def download_mp4(url,referer=None):
    p=_public_host(url)
    if not p.path.lower().endswith(".mp4"): raise HTTPException(400,"Solo se aceptan archivos MP4 directos; no embeds, HLS ni DRM")
    cleanup(); token=secrets.token_urlsafe(18); raw=TMP/(token+".source"); dest=TMP/(token+".mp4")
    headers={"User-Agent":"Mozilla/5.0 LopyTest/3.0"}
    if referer:
        _public_host(referer); headers["Referer"]=referer
    current=url
    try:
        # Validate each redirect hop before following it. Limit redirects and bytes.
        with requests.Session() as session:
            for _ in range(6):
                _public_host(current)
                resp=session.get(current,headers=headers,stream=True,timeout=(12,25),allow_redirects=False)
                if resp.is_redirect or resp.is_permanent_redirect:
                    loc=resp.headers.get("Location"); resp.close()
                    if not loc: raise HTTPException(502,"Redirección sin destino")
                    current=urljoin(current,loc); continue
                resp.raise_for_status()
                ctype=resp.headers.get("Content-Type","").lower()
                if ctype and not ("video/mp4" in ctype or "application/octet-stream" in ctype):
                    resp.close(); raise HTTPException(415,"El servidor no identificó la respuesta como MP4")
                total=0
                with raw.open("wb") as out:
                    for chunk in resp.iter_content(1024*256):
                        if not chunk: continue
                        total+=len(chunk)
                        if total>MAX_BYTES: raise HTTPException(413,"El archivo supera el límite temporal de tamaño")
                        out.write(chunk)
                resp.close(); break
            else: raise HTTPException(502,"Demasiadas redirecciones")
        if not raw.exists() or raw.stat().st_size<1024: raise HTTPException(502,"La fuente MP4 está vacía o incompleta")
        # FFmpeg validates/remuxes the local MP4; it does not fetch embeds or decrypt streams.
        run=subprocess.run(["ffmpeg","-nostdin","-hide_banner","-loglevel","error","-i",str(raw),"-c","copy","-movflags","+faststart","-y",str(dest)],capture_output=True,text=True,timeout=45)
        if run.returncode!=0 or not dest.exists() or dest.stat().st_size<1024:
            raise HTTPException(502,"FFmpeg no pudo validar/remuxear el MP4: "+(run.stderr[-300:] if run.stderr else "archivo no válido"))
        return {"success":True,"id":token,"filename":dest.name,"size":dest.stat().st_size,"temporary":True,"expiresInSeconds":TTL,"url":f"/api/download/{token}"}
    except requests.RequestException as exc:
        raise HTTPException(502,"No se pudo obtener el MP4 directo: "+str(exc)[:180])
    except subprocess.TimeoutExpired: raise HTTPException(504,"FFmpeg superó el tiempo máximo")
    finally: raw.unlink(missing_ok=True)

def get_download_path(token):
    if not re.fullmatch(r"[A-Za-z0-9_-]{16,64}",token):raise HTTPException(404,"Archivo no encontrado")
    f=TMP/(token+".mp4")
    if not f.exists() or time.time()-f.stat().st_mtime>TTL:
        f.unlink(missing_ok=True);raise HTTPException(404,"Archivo temporal expirado o inexistente")
    return f
