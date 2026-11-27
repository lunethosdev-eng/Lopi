"""Multi-provider anime catalog and episode source scraper for Lopi.

Only public page metadata and publicly exposed embed/media URLs are collected.
No synthetic/demo streams are returned when a provider fails.
"""
from __future__ import annotations

import re
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, urlparse, quote_plus
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

    def _latest_provider(self, provider):
        response = self._get(provider["base"])
        return self._parse_cards(response.text, provider, limit=20)

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
                season_number = int(season_match.group(1)) if season_match else 1
                episodes.append({"id": f"{provider['id']}:{href}", "number": self._episode_number(text, href), "season": season_number, "title": text,
                                 "url": href, "provider": provider["name"], "providerId": provider["id"]})
        episodes.sort(key=lambda x: (x["season"], x["number"] is None, x["number"] or 0, x["title"]))
        grouped = {}
        for episode in episodes:
            grouped.setdefault(episode["season"], []).append(episode)
        seasons = [{"number": number, "title": f"Temporada {number}", "episodes": items} for number, items in sorted(grouped.items())]
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

    def get_episode_sources(self, episode_link: str):
        episode_url = self._validate_url(episode_link)
        key = "episode:" + episode_url
        cached = self._cached(key)
        if cached is not None:
            return cached
        response = self._get(episode_url)
        soup = BeautifulSoup(response.text, "html.parser")
        provider = self._provider_for_url(episode_url)
        sources, seen = [], set()
        candidates = []
        for node in soup.select("iframe[src], iframe[data-src], video[src], video source[src], source[src], a[href]"):
            value = node.get("src") or node.get("data-src") or node.get("href")
            url = self._absolute(episode_url, value)
            if not url or url in seen or urlparse(url).scheme not in ("http", "https"):
                continue
            seen.add(url)
            candidates.append((url, node))
        for url, node in candidates:
            lower = url.lower().split("?")[0]
            media_type = "hls" if ".m3u8" in lower else "mp4" if ".mp4" in lower else "embed"
            label = " ".join([node.get("title", ""), node.get("aria-label", ""), node.get_text(" ", strip=True)]).strip()
            language = self._audio_language(label + " " + url)
            if media_type == "embed" and not any(host in urlparse(url).netloc.lower() for host in settings.EMBED_HOST_ALLOWLIST):
                # Keep provider-owned iframe embeds and explicit media links; discard arbitrary page links.
                if node.name == "a" or urlparse(url).netloc == urlparse(episode_url).netloc:
                    continue
            sources.append({"id": f"{provider['id']}:{len(sources)+1}", "server": urlparse(url).netloc,
                            "provider": provider["name"], "url": url, "streamUrl": url,
                            "type": media_type, "mediaType": media_type, "quality": self._quality(label + " " + url),
                            "audio": language, "language": language, "subtitle": "Español" if re.search(r"sub|español|spanish", label + " " + url, re.I) else "No especificado",
                            "resolved": media_type in ("hls", "mp4")})
        audio_options = sorted({source["audio"] for source in sources if source["audio"] != "No especificado"})
        result = {"success": bool(sources), "episode_link": episode_url, "provider": provider["name"],
                  "sources": sources, "total": len(sources), "audioOptions": audio_options,
                  "error": None if sources else "El proveedor no expuso enlaces de reproducción detectables"}
        return self._store(key, result, ttl=180)

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
        if provider_id:
            provider = next((p for p in PROVIDERS if p["id"] == provider_id.lower()), None)
            if not provider:
                return {"success": False, "data": [], "error": "Proveedor desconocido"}
            try:
                items = self._latest_provider(provider)
                return {"success": True, "provider": provider["name"], "page": 1, "total": len(items), "data": items}
            except Exception as exc:
                return {"success": False, "provider": provider["name"], "data": [], "error": str(exc)}
        return self.get_latest_episodes()
