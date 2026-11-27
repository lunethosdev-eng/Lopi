"""Multi-provider anime catalog and episode source scraper for Lopi.

Only public page metadata and publicly exposed embed/media URLs are collected.
No synthetic/demo streams are returned when a provider fails.
"""
from __future__ import annotations

import re
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, urlparse, quote_plus, parse_qsl, urlencode, urlunparse, unquote
from threading import RLock

import cloudscraper
from bs4 import BeautifulSoup
from requests import RequestException

from config import settings

log = logging.getLogger("lopi.scraper")

PROVIDERS = [
    {"id": "animeflv", "name": "AnimeFLV", "language": "Español", "base": "https://animeflv.net", "search": "https://animeflv.net/browse?q={query}", "selectors": "article.anime, .Anime, .ListAnimes-item, .anime"},
    {"id": "jkanime", "name": "JKAnime", "language": "Español", "base": "https://jkanime.net", "search": "https://jkanime.net/buscar/{query}/", "selectors": ".elemento, .anime, .anime__item, article"},
    {"id": "tioanime", "name": "TioAnime", "language": "Español", "base": "https://tioanime.com", "search": "https://tioanime.com/directorio?q={query}", "selectors": ".anime, .item, article"},
    {"id": "monoschinos", "name": "MonosChinos", "language": "Español", "base": "https://monoschinos2.com", "search": "https://monoschinos2.com/buscar?q={query}", "selectors": ".item, .anime, article"},
]

class AnimeScraper:
    def __init__(self):
        self._local = None
        self._cache = {}
        self._cache_lock = RLock()
        self._executor = ThreadPoolExecutor(max_workers=settings.MAX_WORKERS)

    def _session(self):
        # Each worker owns its own scraper session (requests sessions are not thread-safe).
        from threading import local
        if self._local is None:
            self._local = local()
        if not hasattr(self._local, "session"):
            self._local.session = cloudscraper.create_scraper(browser={"browser": "chrome", "platform": "windows", "desktop": True})
        return self._local.session

    def _cached(self, key):
        with self._cache_lock:
            value = self._cache.get(key)
            if value and value[0] > time.time():
                return value[1]
            if value:
                self._cache.pop(key, None)
        return None

    def _store(self, key, value, ttl=None):
        with self._cache_lock:
            self._cache[key] = (time.time() + (ttl or settings.CACHE_TTL), value)
        return value

    def _get(self, url):
        last_error = None
        for attempt in range(settings.RETRIES + 1):
            try:
                response = self._session().get(url, headers=settings.HEADERS, timeout=settings.REQUEST_TIMEOUT, allow_redirects=True)
                response.raise_for_status()
                return response
            except (RequestException, Exception) as exc:
                last_error = exc
                if attempt < settings.RETRIES:
                    time.sleep(0.35 * (attempt + 1))
        raise RuntimeError(f"No se pudo consultar {url}: {last_error}")

    @staticmethod
    def _absolute(base, value):
        if not value:
            return ""
        value = value.strip()
        if value.startswith(("javascript:", "data:", "mailto:")):
            return ""
        return urljoin(base, value)

    @staticmethod
    def _image(card, base):
        img = card.find("img")
        if not img:
            return ""
        return AnimeScraper._absolute(base, img.get("data-src") or img.get("data-lazy-src") or img.get("src") or img.get("data-original"))

    def _parse_cards(self, html, provider, limit=30):
        soup = BeautifulSoup(html, "html.parser")
        cards = []
        seen = set()
        selectors = provider.get("selectors", "article, .item, .anime")
        for card in soup.select(selectors):
            anchor = card.find("a", href=True)
            if not anchor:
                continue
            url = self._absolute(provider["base"], anchor.get("href"))
            if not url or url in seen or urlparse(url).scheme not in ("http", "https"):
                continue
            title_node = card.select_one("h2, h3, h4, .title, .name, .anime-name") or anchor
            title = " ".join(title_node.get_text(" ", strip=True).split())
            if not title or len(title) < 2:
                title = anchor.get("title", "").strip()
            if not title:
                continue
            seen.add(url)
            cards.append({"id": f"{provider['id']}:{url}", "title": title, "name": title, "url": url, "slug": url,
                          "image": self._image(card, provider["base"]), "provider": provider["name"],
                          "providerId": provider["id"], "language": provider["language"]})
            if len(cards) >= limit:
                break
        return cards

    def _search_provider(self, provider, query):
        url = provider["search"].format(query=quote_plus(query))
        response = self._get(url)
        return self._parse_cards(response.text, provider)

    def search_anime(self, query: str, provider_id: str | None = None):
        query = (query or "").strip()
        if len(query) < 2:
            return {"success": False, "error": "La búsqueda debe contener al menos 2 caracteres", "data": [], "providers": []}
        selected = [p for p in PROVIDERS if p["id"] == (provider_id or "").lower()] if provider_id else PROVIDERS
        if provider_id and not selected:
            return {"success": False, "error": "Proveedor desconocido", "data": [], "providers": []}
        key = "search:" + (provider_id or "all") + ":" + query.lower()
        cached = self._cached(key)
        if cached is not None:
            return cached
        results, statuses = [], []
        futures = {self._executor.submit(self._search_provider, p, query): p for p in selected}
        for future in as_completed(futures):
            p = futures[future]
            try:
                items = future.result()
                results.extend(items)
                statuses.append({"id": p["id"], "name": p["name"], "ok": True, "count": len(items)})
            except Exception as exc:
                log.warning("Search provider %s failed: %s", p["id"], exc)
                statuses.append({"id": p["id"], "name": p["name"], "ok": False, "error": str(exc)[:240]})
        # Merge duplicates by normalized title, preserving distinct provider URLs.
        merged, index = [], {}
        for item in results:
            normalized = re.sub(r"[^a-z0-9]", "", item["title"].lower())
            if normalized in index:
                current = merged[index[normalized]]
                current.setdefault("alternatives", []).append({"provider": item["provider"], "providerId": item["providerId"], "url": item["url"]})
                if not current.get("image") and item.get("image"):
                    current["image"] = item["image"]
            else:
                index[normalized] = len(merged)
                item["alternatives"] = []
                merged.append(item)
        merged.sort(key=lambda x: x["title"].lower())
        return self._store(key, {"success": bool(merged), "query": query, "source": "multi" if not provider_id else provider_id,
                                 "total": len(merged), "data": merged, "providers": statuses,
                                 "error": None if merged else "No se encontraron resultados en los proveedores disponibles"})

    def get_latest_episodes(self):
        # Home pages differ widely; this endpoint is a unified catalog of current listings,
        # not fabricated episode entries. Consumers can label it as catálogo/recientes.
        key = "catalog:all"
        cached = self._cached(key)
        if cached is not None:
            return cached
        results, statuses = [], []
        futures = {self._executor.submit(self._latest_provider, p): p for p in PROVIDERS}
        for future in as_completed(futures):
            p = futures[future]
            try:
                items = future.result()
                results.extend(items)
                statuses.append({"id": p["id"], "name": p["name"], "ok": True, "count": len(items)})
            except Exception as exc:
                statuses.append({"id": p["id"], "name": p["name"], "ok": False, "error": str(exc)[:240]})
        return self._store(key, {"success": bool(results), "total": len(results), "data": results, "providers": statuses,
                                 "error": None if results else "No hay proveedores disponibles"})

    def _latest_provider(self, provider, page=1):
        page_url = provider["base"]
        if page > 1:
            parsed = urlparse(page_url)
            query = dict(parse_qsl(parsed.query, keep_blank_values=True))
            query["page"] = str(page)
            page_url = urlunparse(parsed._replace(query=urlencode(query)))
        response = self._get(page_url)
        return self._parse_cards(response.text, provider, limit=30)

    def get_anime_info(self, anime_url: str):
        anime_url = self._validate_url(anime_url)
        key = "info:" + anime_url
        cached = self._cached(key)
        if cached is not None:
            return cached
        provider = self._provider_for_url(anime_url)
        response = self._get(anime_url)
        soup = BeautifulSoup(response.text, "html.parser")
        title = (soup.select_one("h1") or soup.select_one("title"))
        title_text = title.get_text(" ", strip=True) if title else "Anime"
        description = ""
        meta = soup.find("meta", attrs={"name": re.compile("description", re.I)}) or soup.find("meta", attrs={"property": "og:description"})
        if meta:
            description = meta.get("content", "").strip()
        image = ""
        image_meta = soup.find("meta", attrs={"property": "og:image"})
        if image_meta:
            image = self._absolute(anime_url, image_meta.get("content"))
        if not image:
            image = self._image(soup, anime_url)
        episodes, seen = [], set()
        for anchor in soup.select("a[href]"):
            href = self._absolute(anime_url, anchor.get("href"))
            text = " ".join(anchor.get_text(" ", strip=True).split())
            if not href or href in seen or not text:
                continue
            if re.search(r"(episod|cap[ií]tulo|episode|\bep\.?\s*\d+|/\d+/?$)", href + " " + text, re.I):
                seen.add(href)
                season_match = re.search(r"(?:temporada|season|s)\s*(\d+)", text + " " + href, re.I)
                season_number = int(season_match.group(1)) if season_match else None
                episodes.append({"id": f"{provider['id']}:{href}", "number": self._episode_number(text, href), "season": season_number, "title": text,
                                 "url": href, "provider": provider["name"], "providerId": provider["id"]})
        episodes.sort(key=lambda x: (x["season"] is None, x["season"] or 0, x["number"] is None, x["number"] or 0, x["title"]))
        grouped = {}
        for episode in episodes:
            grouped.setdefault(episode["season"], []).append(episode)
        seasons = [{"number": number, "title": f"Temporada {number}" if number is not None else "Temporada sin identificar", "episodes": items} for number, items in sorted(grouped.items(), key=lambda item: (item[0] is None, item[0] or 0))]
        info = {"success": True, "id": f"{provider['id']}:{anime_url}", "title": title_text, "name": title_text,
                "description": description, "image": image, "url": anime_url, "provider": provider["name"],
                "providerId": provider["id"], "language": provider["language"], "seasons": seasons,
                "episodes": episodes, "totalEpisodes": len(episodes), "metadata": self._metadata(soup)}
        return self._store(key, info)

    @staticmethod
    def _metadata(soup):
        text = soup.get_text(" ", strip=True)
        out = {}
        for label, key in [("Género", "genres"), ("Tipo", "type"), ("Estado", "status"), ("Año", "year"), ("Duración", "duration")]:
            match = re.search(label + r"\s*:?\s*([^|]{1,100})", text, re.I)
            if match:
                out[key] = match.group(1).strip()
        return out

    @staticmethod
    def _episode_number(text, url):
        match = re.search(r"(?:episodio|episode|cap[ií]tulo|capitulo|ep\.?|#)\s*(\d+(?:\.\d+)?)", text, re.I)
        if not match:
            match = re.search(r"/(\d+(?:\.\d+)?)/?$", url)
        try:
            return float(match.group(1)) if match else None
        except (ValueError, AttributeError):
            return None

    @staticmethod
    def _media_type(url: str, label: str = "") -> str:
        """Classify only explicit media URLs; an iframe/page is never called a video."""
        parsed = urlparse(url)
        path = unquote(parsed.path).lower()
        query = (parsed.query + " " + label).lower()
        if path.endswith((".m3u8", ".m3u")) or re.search(r"(?:format|type|mime)=?(?:%2F|/)mpegurl|m3u8", query):
            return "hls"
        if path.endswith(".mp4") or re.search(r"(?:format|type|mime)=?video%2Fmp4|video/mp4", query):
            return "mp4"
        if path.endswith((".mpd",)):
            return "dash"
        return "embed"

    def get_episode_sources(self, episode_link: str):
        episode_url = self._validate_url(episode_link)
        key = "episode:" + episode_url
        cached = self._cached(key)
        if cached is not None:
            return cached

        response = self._get(episode_url)
        soup = BeautifulSoup(response.text, "html.parser")
        provider = self._provider_for_url(episode_url)
        candidates, seen = [], set()

        def add_candidate(raw_url, node=None, label=""):
            url = self._absolute(episode_url, raw_url)
            if not url or url in seen:
                return
            parsed = urlparse(url)
            if parsed.scheme not in ("http", "https") or not parsed.hostname:
                return
            # Do not return javascript/data URLs or links to unrelated navigation pages.
            if parsed.hostname.lower() in {"localhost", "127.0.0.1"}:
                return
            seen.add(url)
            node_label = label
            if node is not None:
                node_label = " ".join(filter(None, [
                    node.get("title", ""), node.get("aria-label", ""),
                    node.get("data-audio", ""), node.get("data-lang", ""),
                    node.get("data-server", ""), node.get_text(" ", strip=True), label
                ]))
            candidates.append((url, node, node_label.strip()))

        # Real media and embed elements only. Do not treat every anchor on the page as a server.
        selectors = (
            "iframe[src], iframe[data-src], iframe[data-lazy-src], "
            "video[src], video source[src], source[src], "
            "[data-video], [data-embed], [data-src*='.m3u8'], [data-src*='.mp4']"
        )
        for node in soup.select(selectors):
            value = (node.get("src") or node.get("data-src") or node.get("data-lazy-src")
                     or node.get("data-video") or node.get("data-embed"))
            add_candidate(value, node)

        # Some providers serialize player URLs in script JSON. Extract only URLs whose
        # surrounding text indicates a player/media/server field.
        for script in soup.find_all("script"):
            raw = script.string or script.get_text(" ", strip=False) or ""
            if not raw or not re.search(r"(?:file|source|src|embed|player|video|hls|m3u8)", raw, re.I):
                continue
            for match in re.finditer(r"https?:\\?/\\?/[A-Za-z0-9._~:/?#\[\]@!$&()*+,;=%-]+", raw):
                candidate = match.group(0).replace("\\/", "/").rstrip(",;)")
                before = raw[max(0, match.start() - 180):match.start()]
                after = raw[match.end():match.end() + 100]
                context = before + " " + after
                if re.search(r"(?:file|source|src|embed|player|video|hls|m3u8)", context, re.I):
                    add_candidate(candidate, None, context)

        subtitle_tracks = []
        for track in soup.select("track[src]"):
            track_url = self._absolute(episode_url, track.get("src"))
            if not track_url:
                continue
            subtitle_tracks.append({
                "url": track_url,
                "label": track.get("label") or track.get("srclang") or "Subtítulos",
                "language": track.get("srclang") or "und",
                "kind": track.get("kind") or "subtitles",
                "default": track.has_attr("default"),
            })

        sources = []
        for url, node, label in candidates:
            media_type = self._media_type(url, label)
            host = urlparse(url).hostname or ""
            # A direct stream is playable by the HTML player. A server page is an embed
            # and must be loaded in an iframe, never assigned to <video src>.
            is_direct = media_type in ("hls", "mp4")
            if media_type == "embed":
                # Filter out provider's own episode/detail links and random external links.
                if node is None and not re.search(r"player|embed|server|video|file|source", label, re.I):
                    continue
                if node is not None and node.name == "a":
                    continue
                if node is not None and node.name not in ("iframe", "video", "source") and not any(
                    node.has_attr(attr) for attr in ("data-video", "data-embed")
                ):
                    continue
            language = self._audio_language(label + " " + url)
            subtitle = "Español" if re.search(r"subtit|subbed|español|spanish|\bsub\b", label + " " + url, re.I) else "No especificado"
            sources.append({
                "id": f"{provider['id']}:{len(sources) + 1}",
                "server": host,
                "provider": provider["name"],
                "url": url,
                "streamUrl": url if is_direct else None,
                "embedUrl": url if not is_direct else None,
                "type": media_type,
                "mediaType": media_type,
                "kind": "direct" if is_direct else "embed",
                "playable": is_direct,
                "requiresIframe": not is_direct,
                "quality": self._quality(label + " " + url),
                "audio": language,
                "language": language,
                "subtitle": subtitle,
                "referer": episode_url,
                "tracks": subtitle_tracks,
                "resolved": is_direct,
            })

        # Directly exposed <video> URLs can be relative and may be missed by script parsing;
        # no synthetic fallback is ever inserted here.
        audio_options = sorted({x["audio"] for x in sources if x["audio"] != "No especificado"})
        result = {
            "success": bool(sources),
            "episode_link": episode_url,
            "provider": provider["name"],
            "sources": sources,
            "total": len(sources),
            "audioOptions": audio_options,
            "subtitleTracks": subtitle_tracks,
            "playableCount": sum(1 for x in sources if x["playable"]),
            "embedCount": sum(1 for x in sources if x["requiresIframe"]),
            "error": None if sources else "No se detectaron servidores ni enlaces de vídeo en el HTML del episodio",
            "message": "Los servidores embed deben abrirse en iframe; solo HLS/MP4 directos se asignan al elemento video."
        }
        return self._store(key, result, ttl=180)

    def resolve_source(self, source_url: str):
        """Classify a URL without pretending an embed page is a direct video."""
        parsed = urlparse(source_url or "")
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise ValueError("Se requiere una URL http(s) válida")
        host = parsed.hostname.lower()
        if host in ("localhost", "127.0.0.1", "::1") or host.endswith((".local", ".internal")):
            raise ValueError("Host no permitido")
        media_type = self._media_type(source_url)
        direct = media_type in ("hls", "mp4")
        return {
            "success": True, "server": host, "mediaType": media_type,
            "streamUrl": source_url if direct else None,
            "embedUrl": None if direct else source_url,
            "direct": direct,
            "requiresIframe": not direct,
            "message": None if direct else "Es una página de servidor; debe abrirse como embed, no como video src."
        }

    @staticmethod
    def _audio_language(value):
        value = value.lower()
        if re.search(r"latino|lat\b|es-419|castellano latino", value): return "Español latino"
        if re.search(r"castellano|españa|es-es|spanish.?cast", value): return "Castellano"
        if re.search(r"subtit|subbed|japon[eé]s|japanese|\braw\b", value): return "Subtitulado / Japonés"
        if re.search(r"doblado|español|spanish|\bdub\b", value): return "Español (sin región)"
        return "No especificado"

    @staticmethod
    def _quality(value):
        match = re.search(r"(2160|1080|720|480|360)p", value, re.I)
        return match.group(0).lower() if match else "Automática"

    @staticmethod
    def _validate_url(value):
        parsed = urlparse(value or "")
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise ValueError("Se requiere una URL http(s) válida")
        host = parsed.hostname.lower()
        allowed = [urlparse(p["base"]).hostname.lower() for p in PROVIDERS]
        if not any(host == domain or host.endswith("." + domain) for domain in allowed):
            raise ValueError("La URL debe pertenecer a uno de los proveedores compatibles")
        return value

    @staticmethod
    def _provider_for_url(url):
        host = urlparse(url).netloc.lower().split(":")[0]
        for provider in PROVIDERS:
            base_host = urlparse(provider["base"]).netloc.lower()
            if host == base_host or host.endswith("." + base_host):
                return provider
        return {"id": "external", "name": host, "language": "No especificado"}

    def get_catalog(self, page=1, provider_id=None):
        page = max(1, int(page or 1))
        if provider_id:
            provider = next((p for p in PROVIDERS if p["id"] == provider_id.lower()), None)
            if not provider:
                return {"success": False, "data": [], "error": "Proveedor desconocido"}
            try:
                items = self._latest_provider(provider, page=page)
                return {"success": True, "provider": provider["name"], "page": page, "total": len(items), "data": items}
            except Exception as exc:
                return {"success": False, "provider": provider["name"], "data": [], "error": str(exc)}
        return self.get_latest_episodes()
