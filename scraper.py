"""Lopy scraper v3: HTML + real JavaScript rendering + public metadata APIs.

The renderer executes normal page JavaScript. It deliberately does not bypass
CAPTCHA, authentication, paywalls, anti-bot challenges, or DRM.
"""
from __future__ import annotations
import base64, json, logging, os, re, subprocess, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import RLock, local
from urllib.parse import urljoin, urlparse, quote_plus, unquote, unquote_plus, parse_qs
import requests
from bs4 import BeautifulSoup
from config import settings

log = logging.getLogger("lopy.scraper")
ROOT = Path(__file__).resolve().parent

WEB_PROVIDERS = [
    {"id":"animeflv","name":"AnimeFLV","base":"https://animeflv.net","search":"https://animeflv.net/browse?q={query}","selectors":"article.anime, .Anime, .ListAnimes-item, .anime","language":"es"},
    {"id":"jkanime","name":"JKAnime","base":"https://jkanime.net","search":"https://jkanime.net/buscar/{query}/","selectors":".elemento, .anime, .anime__item, article","language":"es"},
    {"id":"tioanime","name":"TioAnime","base":"https://tioanime.com","search":"https://tioanime.com/directorio?q={query}","selectors":".anime, .item, article","language":"es"},
    {"id":"monoschinos","name":"MonosChinos","base":"https://monoschinos2.com","search":"https://monoschinos2.com/buscar?q={query}","selectors":".item, .anime, article","language":"es"},
    {"id":"animeav1","name":"AnimeAV1","base":"https://animeav1.com","search":"https://animeav1.com/catalogo?q={query}","selectors":"a[href*='/media/']","language":"multi","adapter":"sveltekit"},
]
API_PROVIDERS = [
    {"id":"anilist","name":"AniList","base":"https://graphql.anilist.co","language":"multi"},
    {"id":"jikan","name":"Jikan / MyAnimeList","base":"https://api.jikan.moe/v4","language":"multi"},
    {"id":"kitsu","name":"Kitsu","base":"https://kitsu.io/api/edge","language":"multi"},
]
# The JSON registry is the supported extension point for adding/removing adapters.
try:
    _registry=json.loads((ROOT / "providers.json").read_text(encoding="utf-8"))
    WEB_PROVIDERS=_registry.get("web",WEB_PROVIDERS)
    API_PROVIDERS=_registry.get("metadata_apis",API_PROVIDERS)
except Exception:
    log.warning("No se pudo cargar providers.json; se usan los proveedores integrados")
PROVIDERS = WEB_PROVIDERS + API_PROVIDERS

class AnimeScraper:
    def __init__(self):
        self._thread = local(); self._cache = {}; self._lock = RLock()
        self._executor = ThreadPoolExecutor(max_workers=settings.MAX_WORKERS)

    def _session(self):
        if not hasattr(self._thread, "session"):
            s = requests.Session(); s.headers.update(settings.HEADERS); self._thread.session = s
        return self._thread.session

    def _cached(self, key):
        with self._lock:
            item = self._cache.get(key)
            if item and item[0] > time.time(): return item[1]
            self._cache.pop(key, None)
        return None

    def _store(self, key, value, ttl=None):
        with self._lock: self._cache[key] = (time.time() + (ttl or settings.CACHE_TTL), value)
        return value

    @staticmethod
    def _validate_http_url(url):
        p = urlparse(url or "")
        if p.scheme not in ("http", "https") or not p.hostname: raise ValueError("Se requiere una URL http(s) válida")
        if p.username or p.password: raise ValueError("No se aceptan credenciales dentro de la URL")
        return url

    def _get(self, url, headers=None):
        last = None
        for attempt in range(settings.RETRIES + 1):
            try:
                r = self._session().get(url, headers=headers, timeout=settings.REQUEST_TIMEOUT, allow_redirects=True)
                r.raise_for_status(); return r
            except Exception as exc:
                last = exc
                if attempt < settings.RETRIES: time.sleep(.4 * (attempt + 1))
        raise RuntimeError(f"No se pudo consultar el proveedor: {last}")

    def _render_js(self, url):
        if not settings.JS_RENDER_ENABLED: return None
        script = ROOT / "js_render.js"
        if not script.exists(): return None
        try:
            run = subprocess.run(["node", str(script), url], capture_output=True, text=True,
                                 timeout=settings.JS_RENDER_TIMEOUT, check=False)
            if run.returncode != 0:
                log.info("JS renderer no disponible para %s: %s", url, run.stderr[-300:]); return None
            return json.loads(run.stdout)
        except Exception as exc:
            log.info("JS render falló para %s: %s", url, exc); return None

    @staticmethod
    def _abs(base, value):
        if not value: return ""
        value = str(value).strip()
        if value.startswith(("javascript:", "data:", "mailto:")): return ""
        return urljoin(base, value)

    @staticmethod
    def _decode_public_data(value):
        """Decode common transport encodings; never eval arbitrary page strings."""
        if not isinstance(value, str): return value
        s = value.strip()
        for _ in range(2):
            try:
                if re.fullmatch(r"[A-Za-z0-9+/=_-]{24,}", s) and len(s) % 4 in (0, 2, 3):
                    raw = base64.urlsafe_b64decode(s + "=" * (-len(s) % 4)).decode("utf-8", "ignore")
                    if raw and (raw[0] in "[{\"" or "<" in raw[:80]): s = raw; continue
            except Exception: pass
            s = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1),16)), s)
            s = re.sub(r"\\x([0-9a-fA-F]{2})", lambda m: chr(int(m.group(1),16)), s)
            s = s.replace(r"\u002F", "/").replace(r"\u003A", ":").replace(r"\/", "/")
            s = unquote_plus(s) if "%" in s else s
            s = s.replace("&quot;", '"').replace("&#x2F;", "/").replace("&amp;", "&")
        return s

    @staticmethod
    def _provider(url):
        host = (urlparse(url).hostname or "").lower()
        for p in WEB_PROVIDERS + API_PROVIDERS:
            domain = urlparse(p["base"]).hostname
            if host == domain or host.endswith("." + domain) or (p["id"]=="anilist" and host.endswith("anilist.co")) or (p["id"]=="jikan" and host.endswith("myanimelist.net")):
                return p
        raise ValueError("El dominio no pertenece a un proveedor configurado")

    @staticmethod
    def _episode_num(text, url):
        m = re.search(r"(?:episode|episodio|cap[ií]tulo|capitulo|ep\.?|#)\s*(\d+(?:\.\d+)?)", text, re.I)
        if not m: m = re.search(r"/(\d+(?:\.\d+)?)/?$", urlparse(url).path)
        try: return float(m.group(1)) if m else None
        except Exception: return None

    def _extract_sveltekit(self, scripts):
        found = []
        for raw in scripts or []:
            decoded = self._decode_public_data(raw)
            # Parse JSON-LD / JSON data safely. SvelteKit's serialized payload is
            # returned as text; URLs are extracted only from public data fields.
            try:
                obj = json.loads(decoded)
                found.extend(self._walk_objects(obj))
            except Exception:
                for m in re.finditer(r'https?:\\?/\\?/[A-Za-z0-9._~:/?#\[\]@!$&()*+,;=%-]+', decoded):
                    u = m.group(0).replace('\\/', '/').rstrip('"\' ,;)}]')
                    if re.search(r"/media/", u): found.append({"url":u})
        return found

    def _walk_objects(self, obj):
        out=[]
        if isinstance(obj, dict):
            if any(k in obj for k in ("url","slug","title")):
                out.append(obj)
            for v in obj.values(): out.extend(self._walk_objects(v))
        elif isinstance(obj, list):
            for v in obj: out.extend(self._walk_objects(v))
        return out

    def _parse_cards(self, html, provider, limit=50, base=None):
        soup=BeautifulSoup(html or "", "html.parser"); cards=[]; seen=set(); base=base or provider["base"]
        for card in soup.select(provider.get("selectors", "article, .item, .anime")):
            a=card if card.name == "a" and card.get("href") else card.find("a", href=True)
            if not a: continue
            url=self._abs(base, a.get("href")); title_node=card.select_one("h2,h3,h4,.title,.name,.anime-name") or a
            title=" ".join(title_node.get_text(" ",strip=True).split()) or a.get("title","").strip()
            if not url or not title or url in seen: continue
            seen.add(url); img=card.find("img")
            image=self._abs(base, (img or {}).get("data-src") or (img or {}).get("data-lazy-src") or (img or {}).get("src")) if img else ""
            cards.append({"id":provider["id"]+":"+url,"title":title,"name":title,"url":url,"slug":url,
                          "image":image,"provider":provider["name"],"providerId":provider["id"],"language":provider["language"]})
            if len(cards)>=limit: break
        return cards

    def _search_web(self, p, q):
        url=p["search"].format(query=quote_plus(q)); rendered=None
        try: r=self._get(url); html=r.text
        except Exception:
            rendered=self._render_js(url)
            if not rendered: raise
            html=rendered.get("html","")
        if rendered is None: rendered=self._render_js(url)
        if rendered and rendered.get("html"): html=rendered["html"]
        cards=self._parse_cards(html,p)
        if p.get("adapter")=="sveltekit" and not cards and rendered:
            for item in self._extract_sveltekit(rendered.get("json")):
                slug=item.get("slug"); u=item.get("url") or (urljoin(p["base"],"/media/"+str(slug)) if slug else "")
                title=item.get("title") or item.get("name")
                if u and title: cards.append({"id":p["id"]+":"+u,"title":title,"name":title,"url":u,"slug":slug or u,"image":item.get("coverImage",{}).get("large","") if isinstance(item.get("coverImage"),dict) else "","provider":p["name"],"providerId":p["id"],"language":p["language"]})
        return cards

    def _search_anilist(self, q):
        query='query ($search: String) { Page(perPage: 20) { media(search: $search, type: ANIME) { id title { romaji english native } coverImage { large } siteUrl episodes seasonYear format status } } }'
        r=self._session().post("https://graphql.anilist.co",json={"query":query,"variables":{"search":q}},timeout=settings.REQUEST_TIMEOUT); r.raise_for_status()
        out=[]
        for x in r.json().get("data",{}).get("Page",{}).get("media",[]):
            title=x.get("title") or {}; name=title.get("english") or title.get("romaji") or title.get("native") or "Anime"
            out.append({"id":"anilist:"+str(x["id"]),"title":name,"name":name,"url":x.get("siteUrl"),"image":(x.get("coverImage") or {}).get("large",""),"provider":"AniList","providerId":"anilist","language":"multi","metadata":{"episodes":x.get("episodes"),"year":x.get("seasonYear"),"format":x.get("format"),"status":x.get("status")}})
        return out

    def _search_jikan(self,q):
        r=self._get("https://api.jikan.moe/v4/anime?q="+quote_plus(q)+"&limit=20")
        out=[]
        for x in r.json().get("data",[]):
            title=x.get("title_english") or x.get("title") or "Anime"
            out.append({"id":"jikan:"+str(x.get("mal_id")),"title":title,"name":title,"url":x.get("url"),"image":((x.get("images") or {}).get("jpg") or {}).get("image_url",""),"provider":"Jikan / MyAnimeList","providerId":"jikan","language":"multi","metadata":{"episodes":x.get("episodes"),"year":x.get("year"),"status":x.get("status")}})
        return out


    def _search_kitsu(self,q):
        r=self._get("https://kitsu.io/api/edge/anime?filter[text]="+quote_plus(q)+"&page[limit]=20")
        out=[]
        for item in r.json().get("data",[]):
            a=item.get("attributes") or {}; titles=a.get("titles") or {}; name=titles.get("en") or titles.get("en_jp") or a.get("canonicalTitle") or "Anime"
            poster=((a.get("posterImage") or {}).get("original") or (a.get("posterImage") or {}).get("large") or "")
            out.append({"id":"kitsu:"+str(item.get("id")),"title":name,"name":name,"url":"https://kitsu.io/anime/"+str(item.get("id")),"image":poster,"provider":"Kitsu","providerId":"kitsu","language":"multi","metadata":{"episodes":a.get("episodeCount"),"year":(a.get("startDate") or "")[:4],"status":a.get("status")}})
        return out

    def search_anime(self, query, provider_id=None):
        q=(query or "").strip()
        if len(q)<2: return {"success":False,"error":"La búsqueda requiere al menos 2 caracteres","data":[],"providers":[]}
        selected=[p for p in PROVIDERS if p["id"]==provider_id] if provider_id else PROVIDERS
        if provider_id and not selected: return {"success":False,"error":"Proveedor desconocido","data":[],"providers":[]}
        key=f"search:{provider_id or 'all'}:{q.lower()}"; cached=self._cached(key)
        if cached is not None: return cached
        results=[]; statuses=[]
        jobs=[]
        for p in selected:
            fn=(lambda p=p:self._search_web(p,q)) if p in WEB_PROVIDERS else (self._search_anilist if p["id"]=="anilist" else self._search_jikan if p["id"]=="jikan" else self._search_kitsu)
            jobs.append((p,self._executor.submit(fn,q) if p not in WEB_PROVIDERS else self._executor.submit(fn)))
        for p,f in jobs:
            try:
                items=f.result(); results.extend(items); statuses.append({"id":p["id"],"name":p["name"],"ok":True,"count":len(items)})
            except Exception as exc:
                log.warning("Proveedor %s falló: %s",p["id"],exc); statuses.append({"id":p["id"],"name":p["name"],"ok":False,"count":0,"error":str(exc)[:180]})
        merged=[]; seen={}
        for x in results:
            norm=re.sub(r"[^a-z0-9]","",(x.get("title") or "").lower())
            if norm and norm in seen:
                merged[seen[norm]].setdefault("alternatives",[]).append({"provider":x["provider"],"providerId":x["providerId"],"url":x.get("url")})
            else:
                if norm: seen[norm]=len(merged)
                x["alternatives"]=[]; merged.append(x)
        return self._store(key,{"success":bool(merged),"query":q,"total":len(merged),"data":merged,"providers":statuses,"error":None if merged else "Ningún proveedor devolvió resultados"})

    def get_catalog(self,page=1,provider_id=None):
        # Catalog pages are provider-specific; use page query only where supported.
        selected=[p for p in WEB_PROVIDERS if not provider_id or p["id"]==provider_id]
        if provider_id and not selected: return {"success":False,"data":[],"error":"Proveedor no compatible con catálogo web"}
        data=[]; statuses=[]
        for p in selected:
            try:
                u=p["base"]+ ("?page="+str(max(1,int(page))) if int(page)>1 else "")
                r=self._get(u); rendered=self._render_js(u); html=rendered.get("html") if rendered else r.text
                items=self._parse_cards(html,p); data.extend(items); statuses.append({"id":p["id"],"ok":True,"count":len(items)})
            except Exception as e: statuses.append({"id":p["id"],"ok":False,"error":str(e)[:180]})
        return {"success":bool(data),"page":page,"total":len(data),"data":data,"providers":statuses}

    def get_latest_episodes(self): return self.get_catalog(1)

    def get_anime_info(self, anime_url):
        self._validate_http_url(anime_url); p=self._provider(anime_url); key="info:"+anime_url; cached=self._cached(key)
        if cached is not None:return cached
        if p["id"] in ("anilist","jikan","kitsu"):
            path_id=re.search(r"/(?:anime/)?(\d+)(?:/|$)",urlparse(anime_url).path)
            if not path_id: raise ValueError("No se pudo identificar el ID del anime en el proveedor de metadatos")
            ident=path_id.group(1)
            if p["id"]=="anilist":
                query='query ($id: Int) { Media(id: $id, type: ANIME) { id title { romaji english native } description episodes seasonYear format status genres coverImage { large } siteUrl } }'
                data=self._session().post(p["base"],json={"query":query,"variables":{"id":int(ident)}},timeout=settings.REQUEST_TIMEOUT).json().get("data",{}).get("Media") or {}
                title=data.get("title") or {}; name=title.get("english") or title.get("romaji") or title.get("native") or "Anime"
                meta={"episodes":data.get("episodes"),"year":data.get("seasonYear"),"format":data.get("format"),"status":data.get("status"),"genres":data.get("genres",[])}; image=(data.get("coverImage") or {}).get("large",""); desc=re.sub(r"<[^>]+>"," ",data.get("description") or "")
            elif p["id"]=="jikan":
                data=self._get(p["base"]+"/anime/"+ident+"/full").json().get("data",{}); name=data.get("title_english") or data.get("title") or "Anime"
                meta={"episodes":data.get("episodes"),"year":data.get("year"),"status":data.get("status"),"genres":[g.get("name") for g in data.get("genres",[])]}; image=((data.get("images") or {}).get("jpg") or {}).get("large_image_url",""); desc=data.get("synopsis") or ""
            else:
                data=self._get(p["base"]+"/anime/"+ident).json().get("data",{}).get("attributes",{}); name=(data.get("titles") or {}).get("en") or (data.get("titles") or {}).get("en_jp") or data.get("canonicalTitle") or "Anime"
                meta={"episodes":data.get("episodeCount"),"year":(data.get("startDate") or "")[:4],"status":data.get("status")}; image=(data.get("posterImage") or {}).get("original",""); desc=data.get("synopsis") or ""
            return self._store(key,{"success":True,"id":p["id"]+":"+ident,"title":name,"name":name,"description":desc,"image":image,"url":anime_url,"provider":p["name"],"providerId":p["id"],"language":"multi","seasons":[],"episodes":[],"totalEpisodes":meta.get("episodes"),"metadata":meta,"note":"Proveedor de metadatos: no ofrece enlaces de episodios ni streams."})
        rendered=None
        try: r=self._get(anime_url); html=r.text
        except Exception:
            rendered=self._render_js(anime_url)
            if not rendered: raise
            html=rendered.get("html","")
        if rendered is None: rendered=self._render_js(anime_url)
        if rendered and rendered.get("html"): html=rendered["html"]
        soup=BeautifulSoup(html,"html.parser"); h=soup.select_one("h1") or soup.title
        title=h.get_text(" ",strip=True) if h else "Anime"
        desc=soup.find("meta",attrs={"name":"description"}) or soup.find("meta",attrs={"property":"og:description"})
        image=soup.find("meta",attrs={"property":"og:image"}); image=self._abs(anime_url,image.get("content")) if image else ""
        eps={}; pages=[(anime_url,soup)]; seen_pages={anime_url}
        def collect_episode_links(page_url,page_soup):
            for a in page_soup.select("a[href]"):
                href=self._abs(page_url,a.get("href")); label=" ".join(a.get_text(" ",strip=True).split())
                if not href or not label: continue
                if re.search(r"(episode|episod|cap[ií]tulo|capitulo|/\d+/?$)",href+" "+label,re.I):
                    n=self._episode_num(label,href); season_m=re.search(r"(?:season|temporada|s)\s*(\d+)",label+" "+href,re.I)
                    eps[href]={"id":p["id"]+":"+href,"number":n,"season":int(season_m.group(1)) if season_m else None,"title":label,"url":href,"provider":p["name"],"providerId":p["id"]}
        collect_episode_links(anime_url,soup)
        # Follow only explicit same-origin season/pagination navigation; hard cap avoids crawls.
        host=urlparse(anime_url).netloc
        nav=[]
        for a in soup.select('a[rel="next"],.pagination a[href],a[href*="page="],a[href*="temporada"],a[href*="season"]'):
            u=self._abs(anime_url,a.get("href"))
            if u and urlparse(u).netloc==host and u not in seen_pages: nav.append(u)
        for page_url in nav[:11]:
            try:
                pr=self._get(page_url); ps=BeautifulSoup(pr.text,"html.parser"); pages.append((page_url,ps)); seen_pages.add(page_url); collect_episode_links(page_url,ps)
            except Exception as exc: log.info("No se pudo leer página de temporada/paginación %s: %s",page_url,exc)
        # Parse JSON-LD and rendered framework data for episode lists (without eval).
        if rendered:
            for raw in rendered.get("json",[]):
                decoded=self._decode_public_data(raw)
                try:
                    for obj in self._walk_objects(json.loads(decoded)):
                        u=obj.get("url") or obj.get("href")
                        n=obj.get("number") or obj.get("episodeNumber")
                        if isinstance(u,str) and re.search(r"episode|episod|/\d+",u,re.I):
                            full=self._abs(anime_url,u); eps.setdefault(full,{"id":p["id"]+":"+full,"number":n or self._episode_num(str(obj.get("title", "")),full),"season":obj.get("seasonNumber"),"title":obj.get("title") or f"Episodio {n or ''}".strip(),"url":full,"provider":p["name"],"providerId":p["id"]})
                except Exception: pass
        episodes=sorted(eps.values(),key=lambda x:(x["season"] is None,x["season"] or 0,x["number"] is None,x["number"] or 0,x["title"]))
        groups={}
        for ep in episodes:groups.setdefault(ep["season"],[]).append(ep)
        seasons=[{"number":n,"title":f"Temporada {n}" if n is not None else "Temporada sin identificar","episodes":v} for n,v in sorted(groups.items(),key=lambda x:(x[0] is None,x[0] or 0))]
        result={"success":True,"id":p["id"]+":"+anime_url,"title":title,"name":title,"description":desc.get("content","") if desc else "","image":image,"url":anime_url,"provider":p["name"],"providerId":p["id"],"language":p["language"],"seasons":seasons,"episodes":episodes,"totalEpisodes":len(episodes),"metadata":{"renderedWithJavaScript":bool(rendered),"episodeExtraction":"html+json" if rendered else "html"},"pagination":{"detected":len(pages)>1,"pagesRead":len(pages),"pageLimit":12,"note":"Se siguieron enlaces de temporada/paginación explícitos del mismo dominio; no se inventan episodios."}}
        return self._store(key,result)

    @staticmethod
    def _media_type(url,label=""):
        path=unquote(urlparse(url).path).lower(); q=(urlparse(url).query+" "+label).lower()
        if path.endswith((".m3u8",".m3u")) or "mpegurl" in q:return "hls"
        if path.endswith(".mp4") or "video/mp4" in q:return "mp4"
        if path.endswith(".mpd"):return "dash"
        return "page"

    def _inspect_hls(self, url, referer):
        result={"variants":[],"audioTracks":[],"subtitleTracks":[]}
        try:
            r=self._session().get(url,headers={"Referer":referer},timeout=settings.REQUEST_TIMEOUT); r.raise_for_status(); body=r.text
            if "#EXTM3U" not in body[:100]: return result
            lines=[x.strip() for x in body.splitlines() if x.strip()]
            pending=None
            for line in lines:
                if line.startswith("#EXT-X-STREAM-INF:"):
                    pending=line; continue
                if line.startswith("#EXT-X-MEDIA:"):
                    attrs=dict(re.findall(r'([A-Z-]+)="?([^",]+)',line.split(":",1)[1]))
                    item={"type":attrs.get("TYPE"),"group":attrs.get("GROUP-ID"),"name":attrs.get("NAME"),"language":attrs.get("LANGUAGE"),"url":self._abs(url,attrs.get("URI")) if attrs.get("URI") else None,"default":attrs.get("DEFAULT")=="YES"}
                    if item["type"]=="AUDIO":result["audioTracks"].append(item)
                    if item["type"]=="SUBTITLES":result["subtitleTracks"].append(item)
                elif pending and not line.startswith("#"):
                    res=re.search(r"RESOLUTION=(\d+x\d+)",pending); bw=re.search(r"BANDWIDTH=(\d+)",pending)
                    height=int(res.group(1).split("x")[1]) if res else None
                    result["variants"].append({"url":self._abs(url,line),"resolution":res.group(1) if res else None,"height":height,"quality":f"{height}p" if height else "Automática","bandwidth":int(bw.group(1)) if bw else None})
                    pending=None
        except Exception as exc: log.info("No se pudo inspeccionar HLS: %s",exc)
        return result

    def _inspect_dash(self,url,referer):
        result={"audioTracks":[],"subtitleTracks":[],"variants":[]}
        try:
            import xml.etree.ElementTree as ET
            r=self._session().get(url,headers={"Referer":referer},timeout=settings.REQUEST_TIMEOUT);r.raise_for_status()
            root=ET.fromstring(r.content)
            for a in root.iter():
                if a.tag.rsplit("}",1)[-1]!="AdaptationSet":continue
                lang=a.attrib.get("lang") or "und"; mime=a.attrib.get("mimeType",""); content=a.attrib.get("contentType","")
                item={"language":lang,"mimeType":mime,"contentType":content}
                if content=="audio" or mime.startswith("audio/"):result["audioTracks"].append(item)
                elif content=="text" or "text" in mime or "subtitle" in mime:result["subtitleTracks"].append(item)
                for rep in a:
                    if rep.tag.rsplit("}",1)[-1]=="Representation":
                        h=int(rep.attrib.get("height",0) or 0)
                        result["variants"].append({"quality":f"{h}p" if h else "Automática","height":h or None,"bandwidth":int(rep.attrib.get("bandwidth",0) or 0)})
        except Exception as exc:log.info("No se pudo inspeccionar DASH: %s",exc)
        return result

    def get_episode_sources(self, episode_link):
        self._validate_http_url(episode_link); p=self._provider(episode_link)
        if p["id"] in ("anilist","jikan","kitsu"): raise ValueError("Este proveedor ofrece metadatos, no fuentes de vídeo")
        key="episode:"+episode_link; cached=self._cached(key)
        if cached is not None:return cached
        rendered=None
        try: r=self._get(episode_link); html=r.text
        except Exception:
            rendered=self._render_js(episode_link)
            if not rendered: raise
            html=rendered.get("html","")
        if rendered is None: rendered=self._render_js(episode_link)
        if rendered and rendered.get("html"): html=rendered["html"]
        soup=BeautifulSoup(html,"html.parser"); candidates={}; tracks=[]
        def add(raw,label=""):
            u=self._abs(episode_link,self._decode_public_data(raw))
            if not u:return
            typ=self._media_type(u,label)
            if typ in ("hls","mp4","dash"):candidates[u]=label
        for node in soup.select("video[src],video source[src],source[src],[data-file],[data-video-file],[data-src*='.m3u8'],[data-src*='.mp4']"):
            add(node.get("src") or node.get("data-file") or node.get("data-video-file") or node.get("data-src") or "",node.get("title","")+" "+node.get("label",""))
        for t in soup.select("track[src]"):
            tracks.append({"url":self._abs(episode_link,t.get("src")),"label":t.get("label") or t.get("srclang") or "Subtitles","language":t.get("srclang") or "und","kind":t.get("kind") or "subtitles","default":t.has_attr("default")})
        for script in soup.find_all("script"):
            raw=self._decode_public_data(script.string or script.get_text(" ",strip=False) or "")
            for m in re.finditer(r'https?:\\?/\\?/[A-Za-z0-9._~:/?#\[\]@!$&()*+,;=%-]+',raw):
                u=m.group(0).replace('\\/','/').rstrip('"\' ,;)}]')
                context=raw[max(0,m.start()-200):m.end()+120]
                if re.search(r"(file|source|hls|m3u8|videoUrl|downloadUrl)",context,re.I):add(u,context)
        if rendered:
            for u in rendered.get("media",[]): add(u,"runtime-media-resource")
        sources=[]
        for u,label in candidates.items():
            typ=self._media_type(u,label); host=urlparse(u).hostname or ""
            manifest=self._inspect_hls(u,episode_link) if typ=="hls" else self._inspect_dash(u,episode_link) if typ=="dash" else {"variants":[],"audioTracks":[],"subtitleTracks":[]}
            all_subs=tracks+manifest.get("subtitleTracks",[])
            quality=next((v.get("quality") for v in manifest.get("variants",[]) if v.get("quality")),self._quality(label+" "+u))
            audios=[x.get("language") or x.get("name") for x in manifest.get("audioTracks",[]) if x.get("language") or x.get("name")]
            audio=", ".join(dict.fromkeys(audios)) if audios else self._language(label+" "+u)
            sources.append({"id":f"{p['id']}:{len(sources)+1}","server":host,"provider":p["name"],"url":u,"streamUrl":u,"embedUrl":None,"type":typ,"mediaType":typ,"kind":"direct","playable":True,"requiresIframe":False,"quality":quality,"variants":manifest.get("variants",[]),"audioTracks":manifest.get("audioTracks",[]),"audio":audio,"language":audio,"subtitle":"Disponible" if all_subs else "No especificado","referer":episode_link,"tracks":all_subs,"resolved":True})
        result={"success":bool(sources),"episode_link":episode_link,"provider":p["name"],"sources":sources,"total":len(sources),"audioOptions":sorted({x["audio"] for x in sources if x["audio"]!="No especificado"}),"subtitleTracks":list({x.get("url") or x.get("language") or str(x):x for src in sources for x in src.get("tracks",[])}.values()),"playableCount":len(sources),"embedCount":0,"error":None if sources else "No se encontró una fuente directa HLS/MP4/DASH pública; los iframes y páginas de reproductor se omiten.","renderedWithJavaScript":bool(rendered),"message":"Solo se devuelven fuentes directas explícitas. No se extraen claves DRM ni se abren iframes."}
        return self._store(key,result,ttl=120)

    @staticmethod
    def _quality(s):
        m=re.search(r"(2160|1440|1080|720|480|360)p",s,re.I);return m.group(0).lower() if m else "Automática"
    @staticmethod
    def _language(s):
        s=s.lower()
        for pat,name in [(r"latino|es-419","Español latino"),(r"castellano|es-es","Castellano"),(r"english|ingles|en-us|dub","Inglés / doblado"),(r"japanese|japon[eé]s|subbed|subtit","Japonés / subtitulado")]:
            if re.search(pat,s):return name
        return "No especificado"

    def resolve_source(self, source_url):
        self._validate_http_url(source_url); typ=self._media_type(source_url)
        direct=typ in ("hls","mp4","dash")
        return {"success":True,"server":urlparse(source_url).hostname,"mediaType":typ,"streamUrl":source_url if direct else None,"embedUrl":None,"direct":direct,"requiresIframe":False,"playable":direct,"message":None if direct else "No es una URL directa de medios; no se ofrecerá como iframe."}
