"""
Lopi Anime backend — adaptado con la arquitectura modular de Anime1v.
Proveedores incluidos: AnimeFLV, JKAnime, TioAnime y MonosChinos.
HentaiLA no está incluido. No se generan resultados ni streams ficticios.
"""
import base64
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, urlparse, quote_plus
import cloudscraper
from bs4 import BeautifulSoup
from config import settings


PROVIDERS = {
    "animeflv": {"name": "AnimeFLV", "base": "https://www.animeflv.net", "search": "https://www.animeflv.net/browse?q={q}"},
    "jkanime": {"name": "JKAnime", "base": "https://jkanime.net", "search": "https://jkanime.net/buscar/{q}/"},
    "tioanime": {"name": "TioAnime", "base": "https://tioanime.com", "search": "https://tioanime.com/directorio?search={q}"},
    "monoschinos": {"name": "MonosChinos", "base": "https://monoschinos2.com", "search": "https://monoschinos2.com/buscar?q={q}"},
}
HEADERS = {
    **settings.HEADERS,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.google.com/",
}
CARD_SELECTORS = {
    "animeflv": "article.Anime, .ListAnimes li article",
    "jkanime": ".anime__item, .anime-item, .elemento, article",
    "tioanime": "article.anime",
    "monoschinos": ".item, article, .anime-item",
}
TITLE_SELECTORS = {
    "animeflv": "h3.Title",
    "jkanime": "h3, h2, .title",
    "tioanime": "h3.title",
    "monoschinos": "h2, h3, .title",
}

class ProviderError(Exception):
    pass

class AnimeScraper:
    def __init__(self):
        self.session = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "android", "desktop": False}
        )
        self.timeout = 12

    def _get(self, url):
        if not url or not url.startswith(("http://", "https://")):
            raise ProviderError("URL no válida")
        response = self.session.get(url, headers=HEADERS, timeout=self.timeout,
                                    allow_redirects=True)
        response.raise_for_status()
        return response.text, response.url

    def _absolute(self, value, base):
        return urljoin(base, value) if value else None

    def _provider_for_url(self, url):
        host = (urlparse(url).hostname or "").lower()
        for key, p in PROVIDERS.items():
            base_host = urlparse(p["base"]).hostname
            if host == base_host or host.endswith("." + base_host):
                return key
        raise ProviderError("Proveedor no compatible. Usa AnimeFLV, JKAnime, TioAnime o MonosChinos.")

    def _parse_cards(self, html, provider):
        p = PROVIDERS[provider]
        soup = BeautifulSoup(html, "html.parser")
        results, seen = [], set()
        for card in soup.select(CARD_SELECTORS[provider]):
            a = card.select_one("a[href]")
            title_el = card.select_one(TITLE_SELECTORS[provider]) or card.select_one("a[title], img[alt]")
            title = (title_el.get("title") if title_el and title_el.name in ("a","img") else
                     title_el.get("alt") if title_el and title_el.name == "img" else
                     title_el.get_text(" ", strip=True) if title_el else "")
            if not title and a:
                title = a.get("title") or a.get_text(" ", strip=True)
            href = a.get("href") if a else None
            if not title or not href:
                continue
            link = self._absolute(href, p["base"])
            if link in seen:
                continue
            seen.add(link)
            img = card.select_one("img")
            image = None
            if img:
                image = self._absolute(img.get("data-src") or img.get("data-lazy-src") or img.get("src"), p["base"])
            results.append({
                "id": None, "title": title.strip(), "slug": link.rstrip("/").split("/")[-1],
                "url": link, "link": link, "image": image, "backdrop": None,
                "type": (card.select_one(".Type") or card.select_one(".anime-type-serie, .anime-type-peli")).get_text(" ", strip=True)
                        if card.select_one(".Type, .anime-type-serie, .anime-type-peli") else "Anime",
                "provider": p["name"], "language": "Español / Sub"
            })
        return results

    def search_anime(self, query, provider=None):
        q = (query or "").strip()
        if len(q) < 2:
            return {"success": False, "error": "Escribe al menos 2 caracteres", "data": []}
        selected = [provider] if provider in PROVIDERS else list(PROVIDERS)
        found, errors = [], []
        with ThreadPoolExecutor(max_workers=min(4, len(selected))) as pool:
            jobs = {pool.submit(self._search_one, key, q): key for key in selected}
            for future in as_completed(jobs):
                key = jobs[future]
                try:
                    found.extend(future.result())
                except Exception as exc:
                    errors.append({"provider": key, "error": str(exc)[:180]})
        # Deduplicar por título normalizado + URL
        unique, seen = [], set()
        for item in found:
            key = re.sub(r"[^a-z0-9]", "", item["title"].lower())
            if key and key not in seen:
                seen.add(key); unique.append(item)
        return {"success": True, "query": q, "count": len(unique), "data": unique,
                "providers_checked": selected, "provider_errors": errors}

    def _search_one(self, key, q):
        url = PROVIDERS[key]["search"].format(q=quote_plus(q))
        html, final_url = self._get(url)
        # Provider base is immutable; avoids races between parallel searches.
        return self._parse_cards(html, key)

    def get_latest_episodes(self):
        # Home pages are not all episode feeds; parse real cards only.
        candidates = []
        for key in ("animeflv", "tioanime", "monoschinos"):
            try:
                html, _ = self._get(PROVIDERS[key]["base"])
                candidates.extend(self._parse_cards(html, key)[:12])
            except Exception:
                continue
        return {"success": True, "total_providers": 3, "data": candidates,
                "message": None if candidates else "No se pudo obtener catálogo de los proveedores ahora mismo."}

    def get_anime_info(self, url):
        key = self._provider_for_url(url)
        html, final_url = self._get(url)
        soup = BeautifulSoup(html, "html.parser")
        title = (soup.select_one("h1.title") or soup.select_one("h1"))
        description = (soup.select_one("p.sinopsis") or soup.select_one(".Description") or
                       soup.select_one(".Anime-Description") or soup.select_one(".description"))
        image = soup.select_one(".AnimeCover img, .cover img, .Anime img, img.cover")
        genres = []
        for el in soup.select(".Nvgnrs a, .ListAnmRel a, .genres a, a[href*='genero']"):
            name = el.get_text(" ", strip=True)
            if name and name not in genres: genres.append(name)
        episodes, seen = [], set()
        for a in soup.select("a[href*='/ver/']"):
            href = self._absolute(a.get("href"), final_url)
            number = self._episode_number(href)
            if number is None or href in seen: continue
            seen.add(href)
            episodes.append({"id": None, "number": number, "title": f"Episodio {number}", "url": href})
        # AnimeFLV/TioAnime expose episode arrays in page scripts.
        if not episodes:
            for script in soup.find_all("script"):
                text = script.string or script.get_text()
                match = re.search(r"episodes\s*=\s*(\[[\s\S]*?\])", text)
                if match:
                    try:
                        nums = json.loads(match.group(1))
                        for n in nums:
                            if isinstance(n, (int,float)):
                                episodes.append({"id": None, "number": int(n),
                                                 "title": f"Episodio {int(n)}",
                                                 "url": self._episode_url(final_url, int(n))})
                    except Exception: pass
        episodes.sort(key=lambda x: x["number"])
        return {"success": True, "source": key, "data": {
            "id": None, "title": title.get_text(" ", strip=True) if title else None,
            "description": description.get_text(" ", strip=True) if description else None,
            "image": self._absolute(image.get("data-src") or image.get("src"), final_url) if image else None,
            "genres": [{"id": None, "name": g, "slug": re.sub(r"\s+","-",g.lower())} for g in genres],
            "totalEpisodes": len(episodes), "episodes": episodes, "url": final_url
        }}

    def _episode_url(self, anime_url, number):
        parsed = urlparse(anime_url)
        slug = parsed.path.rstrip("/").split("/")[-1]
        slug = re.sub(r"-\d+$", "", slug)
        if parsed.path.startswith("/anime/"):
            return f"{parsed.scheme}://{parsed.netloc}/ver/{slug}-{number}"
        return f"{parsed.scheme}://{parsed.netloc}/ver/{slug}-{number}"

    def _episode_number(self, url):
        if not url: return None
        m = re.search(r"(\d+)(?:/)?$", urlparse(url).path)
        return int(m.group(1)) if m else None

    def get_episode_sources(self, episode_link):
        # A link is required. Never return sample MP4 files as if they were anime.
        if not episode_link:
            return {"success": False, "error": "Se requiere el enlace del episodio"}
        key = self._provider_for_url(episode_link)
        html, final_url = self._get(episode_link)
        soup = BeautifulSoup(html, "html.parser")
        sources, seen = [], set()
        # Parse the site's own video metadata, if exposed.
        for script in soup.find_all("script"):
            body = script.string or script.get_text()
            match = re.search(r"videos\s*=\s*(\{[\s\S]*?\});", body)
            if match:
                raw = match.group(1)
                try:
                    data = json.loads(raw.replace("\\/", "/"))
                except Exception:
                    data = None
                if isinstance(data, dict):
                    for variant, rows in data.items():
                        if not isinstance(rows, list): continue
                        for row in rows:
                            if not isinstance(row, dict): continue
                            raw_url = row.get("code") or row.get("url") or row.get("embed") or row.get("file")
                            if raw_url and isinstance(raw_url, str):
                                try:
                                    decoded = base64.b64decode(raw_url).decode("utf-8")
                                    if decoded.startswith(("http://","https://")): raw_url = decoded
                                except Exception: pass
                                self._add_source(sources, seen, row.get("title") or row.get("server") or "Servidor",
                                                 self._absolute(raw_url, final_url), variant)
        # Iframes and video tags are returned as embeds, not falsely labeled as direct media.
        for el in soup.select("iframe[src], video[src], video source[src]"):
            src = self._absolute(el.get("src"), final_url)
            if src: self._add_source(sources, seen, "Embed", src, "SUB")
        return {"success": True, "source": key, "episode_link": final_url,
                "episode": self._episode_number(final_url),
                "sources": sources,
                "message": None if sources else "La página no expuso servidores reproducibles. Puede requerir cambios del proveedor."}

    def _add_source(self, target, seen, server, url, variant):
        if not url or not url.startswith(("http://","https://")) or url in seen: return
        seen.add(url)
        target.append({"server": server, "url": url, "audio": "Japonés",
                       "sub": "Español" if "sub" in str(variant).lower() else "No especificado",
                       "variant": str(variant).upper()})
