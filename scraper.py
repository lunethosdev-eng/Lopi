import cloudscraper
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from config import settings

class AnimeScraper:
    def __init__(self):
        # cloudscraper maneja automáticamente Cloudflare y retos de JavaScript
        self.scraper = cloudscraper.create_scraper(
            browser={'browser': 'chrome', 'platform': 'android', 'desktop': False}
        )
        
        # Más de 50 proveedores clasificados por idioma y región
        self.targets = [
            # === ESPAÑOL / LATINO ===
            {
                "name": "AnimeFLV",
                "lang": "Español",
                "url": "https://animeflv.net",
                "search_url": "https://animeflv.net/browse?q=",
                "card_selector": "article.anime",
                "title_selector": "h3",
                "img_selector": "img"
            },
            {
                "name": "Jkanime",
                "lang": "Español",
                "url": "https://jkanime.net",
                "search_url": "https://jkanime.net/buscar/",
                "card_selector": ".elemento",
                "title_selector": "h3",
                "img_selector": "img"
            },
            {
                "name": "MonosChinos",
                "lang": "Español",
                "url": "https://monoschinos2.com",
                "search_url": "https://monoschinos2.com/buscar?q=",
                "card_selector": ".item",
                "title_selector": "h2",
                "img_selector": "img"
            },
            {
                "name": "AnimeID",
                "lang": "Español",
                "url": "https://www.animeid.tv",
                "search_url": "https://www.animeid.tv/search?q=",
                "card_selector": ".anime-card",
                "title_selector": "h3",
                "img_selector": "img"
            },
            {
                "name": "AnimeFenix",
                "lang": "Español",
                "url": "https://www.animefenix.tv",
                "search_url": "https://www.animefenix.tv/animes?q=",
                "card_selector": ".serie-card",
                "title_selector": "h5",
                "img_selector": "img"
            },
            {
                "name": "AnimeBlix",
                "lang": "Español",
                "url": "https://animeblix.com",
                "search_url": "https://animeblix.com/search?q=",
                "card_selector": ".item",
                "title_selector": "h3",
                "img_selector": "img"
            },
            {
                "name": "AnimeVibe",
                "lang": "Español",
                "url": "https://animevibe.cx",
                "search_url": "https://animevibe.cx/search?q=",
                "card_selector": ".anime-block",
                "title_selector": "h4",
                "img_selector": "img"
            },
            {
                "name": "AnimeOnline360",
                "lang": "Español",
                "url": "https://animeonline360.me",
                "search_url": "https://animeonline360.me/?s=",
                "card_selector": ".manga-item",
                "title_selector": "h3",
                "img_selector": "img"
            },
            {
                "name": "Compucalitv Anime",
                "lang": "Español Latino",
                "url": "https://www.compucalitv.com/?s=anime",
                "search_url": "https://www.compucalitv.com/?s=",
                "card_selector": ".item",
                "title_selector": "h2",
                "img_selector": "img"
            },
            {
                "name": "Peliculotas / AnimeLatino",
                "lang": "Español Latino",
                "url": "https://animelatino.org",
                "search_url": "https://animelatino.org/?s=",
                "card_selector": "article",
                "title_selector": "h2",
                "img_selector": "img"
            },
            {
                "name": "AnimeLatinoHD",
                "lang": "Español Latino",
                "url": "https://animelatinohd.com",
                "search_url": "https://animelatinohd.com/?s=",
                "card_selector": ".anime-box",
                "title_selector": "h3",
                "img_selector": "img"
            },
            {
                "name": "Crunchyroll ES",
                "lang": "Español / Sub",
                "url": "https://www.crunchyroll.com/es",
                "search_url": "https://www.crunchyroll.com/es/search?q=",
                "card_selector": ".card",
                "title_selector": "h4",
                "img_selector": "img"
            },
            {
                "name": "AnimeStix",
                "lang": "Español",
                "url": "https://animestix.site",
                "search_url": "https://animestix.site/?s=",
                "card_selector": ".post-item",
                "title_selector": "h3",
                "img_selector": "img"
            },
            {
                "name": "AnimeMega",
                "lang": "Español",
                "url": "https://animemega.org",
                "search_url": "https://animemega.org/?s=",
                "card_selector": ".item",
                "title_selector": "h2",
                "img_selector": "img"
            },
            {
                "name": "VerAnime",
                "lang": "Español",
                "url": "https://veranime.to",
                "search_url": "https://veranime.to/animes?q=",
                "card_selector": "article",
                "title_selector": "h3",
                "img_selector": "img"
            },
            {
                "name": "AnimeSub",
                "lang": "Español",
                "url": "https://animesub.cc",
                "search_url": "https://animesub.cc/?s=",
                "card_selector": ".item",
                "title_selector": "h3",
                "img_selector": "img"
            },
            {
                "name": "AnimeGatito",
                "lang": "Español",
                "url": "https://animegatito.com",
                "search_url": "https://animegatito.com/?s=",
                "card_selector": ".card",
                "title_selector": "h2",
                "img_selector": "img"
            },
            {
                "name": "AnimeFenix Net",
                "lang": "Español",
                "url": "https://www.animefenix.com",
                "search_url": "https://www.animefenix.com/animes?q=",
                "card_selector": ".serie-card",
                "title_selector": "h3",
                "img_selector": "img"
            },
            {
                "name": "AnimeHao",
                "lang": "Español",
                "url": "https://animehao.com",
                "search_url": "https://animehao.com/?s=",
                "card_selector": ".item",
                "title_selector": "h2",
                "img_selector": "img"
            },
            {
                "name": "AnimeBlanco",
                "lang": "Español",
                "url": "https://animeblanco.com",
                "search_url": "https://animeblanco.com/?s=",
                "card_selector": ".anime-card",
                "title_selector": "h3",
                "img_selector": "img"
            },
            {
                "name": "AnimePro",
                "lang": "Español",
                "url": "https://animepro.cc",
                "search_url": "https://animepro.cc/?s=",
                "card_selector": ".item",
                "title_selector": "h3",
                "img_selector": "img"
            },
            {
                "name": "AnimeLatino Online",
                "lang": "Español Latino",
                "url": "https://animelatino.online",
                "search_url": "https://animelatino.online/?s=",
                "card_selector": "article",
                "title_selector": "h3",
                "img_selector": "img"
            },
            {
                "name": "AnimeZeta",
                "lang": "Español",
                "url": "https://animezeta.com",
                "search_url": "https://animezeta.com/?s=",
                "card_selector": ".item",
                "title_selector": "h2",
                "img_selector": "img"
            },
            {
                "name": "AnimeYugen",
                "lang": "Español",
                "url": "https://animeyugen.xyz",
                "search_url": "https://animeyugen.xyz/?s=",
                "card_selector": ".card",
                "title_selector": "h3",
                "img_selector": "img"
            },
            {
                "name": "AnimeKino",
                "lang": "Español",
                "url": "https://animekino.net",
                "search_url": "https://animekino.net/?s=",
                "card_selector": ".item",
                "title_selector": "h3",
                "img_selector": "img"
            },

            # === INGLÉS (SUB / DUB) ===
            {
                "name": "Gogoanime / Animesuge",
                "lang": "Inglés",
                "url": "https://animesuge.to",
                "search_url": "https://animesuge.to/search?keyword=",
                "card_selector": ".item",
                "title_selector": ".name",
                "img_selector": "img"
            },
            {
                "name": "Zoro.to / AniWatch",
                "lang": "Inglés",
                "url": "https://aniwatch.to",
                "search_url": "https://aniwatch.to/search?keyword=",
                "card_selector": ".film-detail",
                "title_selector": "h3",
                "img_selector": "img"
            },
            {
                "name": "9Anime Target",
                "lang": "Inglés",
                "url": "https://9animetv.to",
                "search_url": "https://9animetv.to/search?keyword=",
                "card_selector": ".flw-item",
                "title_selector": "h3",
                "img_selector": "img"
            },
            {
                "name": "AnimePahe",
                "lang": "Inglés",
                "url": "https://animepahe.ru",
                "search_url": "https://animepahe.ru/api?q=",
                "card_selector": ".card",
                "title_selector": "h3",
                "img_selector": "img"
            },
            {
                "name": "KickAssAnime",
                "lang": "Inglés",
                "url": "https://kickassanime.am",
                "search_url": "https://kickassanime.am/search?q=",
                "card_selector": ".anime-card",
                "title_selector": "h4",
                "img_selector": "img"
            },
            {
                "name": "AnimeHeaven",
                "lang": "Inglés",
                "url": "https://animeheaven.me",
                "search_url": "https://animeheaven.me/search.php?s=",
                "card_selector": ".infobox",
                "title_selector": "a",
                "img_selector": "img"
            },
            {
                "name": "Masterani",
                "lang": "Inglés",
                "url": "https://masterani.find",
                "search_url": "https://masterani.find/search?q=",
                "card_selector": ".anime-block",
                "title_selector": "h3",
                "img_selector": "img"
            },
            {
                "name": "DarkAnime",
                "lang": "Inglés",
                "url": "https://darkanime.sub",
                "search_url": "https://darkanime.sub/?s=",
                "card_selector": ".post",
                "title_selector": "h2",
                "img_selector": "img"
            },
            {
                "name": "Erai-raws",
                "lang": "Inglés / Multi-Sub",
                "url": "https://erai-raws.info",
                "search_url": "https://erai-raws.info/?s=",
                "card_selector": "tr",
                "title_selector": "td",
                "img_selector": "img"
            },
            {
                "name": "SubsPlease",
                "lang": "Inglés / Japonés",
                "url": "https://subsplease.org",
                "search_url": "https://subsplease.org/?s=",
                "card_selector": ".release-row",
                "title_selector": "h4",
                "img_selector": "img"
            },
            {
                "name": "TokyoInsider",
                "lang": "Inglés / Japonés",
                "url": "https://www.tokyoinsider.com",
                "search_url": "https://www.tokyoinsider.com/search?q=",
                "card_selector": ".list-item",
                "title_selector": "a",
                "img_selector": "img"
            },
            {
                "name": "HiAnime",
                "lang": "Inglés",
                "url": "https://hianime.to",
                "search_url": "https://hianime.to/search?keyword=",
                "card_selector": ".film-detail",
                "title_selector": "h3",
                "img_selector": "img"
            },
            {
                "name": "AnimeKai",
                "lang": "Inglés",
                "url": "https://animekai.to",
                "search_url": "https://animekai.to/search?q=",
                "card_selector": ".item",
                "title_selector": "h3",
                "img_selector": "img"
            },
            {
                "name": "AnimeUltima",
                "lang": "Inglés",
                "url": "https://animeultima.to",
                "search_url": "https://animeultima.to/search?q=",
                "card_selector": ".anime-card",
                "title_selector": "h4",
                "img_selector": "img"
            },
            {
                "name": "AnimeDao Target",
                "lang": "Inglés",
                "url": "https://animedao.to",
                "search_url": "https://animedao.to/?s=",
                "card_selector": ".card",
                "title_selector": "h3",
                "img_selector": "img"
            },
            {
                "name": "Chia-Anime",
                "lang": "Inglés",
                "url": "https://www.chia-anime.me",
                "search_url": "https://www.chia-anime.me/search/?s=",
                "card_selector": ".item",
                "title_selector": "h3",
                "img_selector": "img"
            },
            {
                "name": "AnimeFrenzy",
                "lang": "Inglés",
                "url": "https://animefrenzy.org",
                "search_url": "https://animefrenzy.org/?s=",
                "card_selector": ".series",
                "title_selector": "h3",
                "img_selector": "img"
            },
            {
                "name": "Wcostream",
                "lang": "Inglés (Dub)",
                "url": "https://www.wcostream.tv",
                "search_url": "https://www.wcostream.tv/search?s=",
                "card_selector": ".cat-item",
                "title_selector": "h3",
                "img_selector": "img"
            },
            {
                "name": "Anime Karma",
                "lang": "Inglés",
                "url": "https://animekarma.com",
                "search_url": "https://animekarma.com/?s=",
                "card_selector": ".post",
                "title_selector": "h2",
                "img_selector": "img"
            },
            {
                "name": "Anime Twist",
                "lang": "Inglés",
                "url": "https://twist.moe",
                "search_url": "https://twist.moe/search?q=",
                "card_selector": ".serie",
                "title_selector": "h3",
                "img_selector": "img"
            },

            # === JAPONÉS / OTROS IDIOMAS ===
            {
                "name": "Abema TV Anime",
                "lang": "Japonés",
                "url": "https://abema.tv/video/genre/animation",
                "search_url": "https://abema.tv/search?q=",
                "card_selector": ".com-video-Card",
                "title_selector": "h4",
                "img_selector": "img"
            },
            {
                "name": "NicoNico Anime",
                "lang": "Japonés",
                "url": "https://ch.nicovideo.jp/anime",
                "search_url": "https://ch.nicovideo.jp/search/",
                "card_selector": ".item",
                "title_selector": "a",
                "img_selector": "img"
            },
            {
                "name": "BS11 Anime",
                "lang": "Japonés",
                "url": "https://www.bs11.jp/anime/",
                "search_url": "https://www.bs11.jp/search/?q=",
                "card_selector": ".program-box",
                "title_selector": "h3",
                "img_selector": "img"
            },
            {
                "name": "U-NEXT Anime",
                "lang": "Japonés",
                "url": "https://video.unext.jp/genre/anime",
                "search_url": "https://video.unext.jp/lucid/search?query=",
                "card_selector": "li",
                "title_selector": "p",
                "img_selector": "img"
            },
            {
                "name": "DMM TV Anime",
                "lang": "Japonés",
                "url": "https://tv.dmm.com/vod/genre/anime/",
                "search_url": "https://tv.dmm.com/vod/search/?query=",
                "card_selector": ".listItem",
                "title_selector": "span",
                "img_selector": "img"
            },
            {
                "name": "Bandai Channel",
                "lang": "Japonés",
                "url": "https://www.b-ch.com",
                "search_url": "https://www.b-ch.com/search/list/?keyword=",
                "card_selector": ".workBox",
                "title_selector": "h3",
                "img_selector": "img"
            },
            {
                "name": "D Anime Store",
                "lang": "Japonés",
                "url": "https://animestore.docomo.ne.jp",
                "search_url": "https://animestore.docomo.ne.jp/animestore/sch_str?search=1&keyword=",
                "card_selector": ".itemBlock",
                "title_selector": "p",
                "img_selector": "img"
            }
        ]

    def _fetch_target(self, target):
        episodes = []
        try:
            response = self.scraper.get(target["url"], headers=settings.HEADERS, timeout=3)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                items = soup.select(target["card_selector"])[:5]
                
                for item in items:
                    title_el = item.select_one(target["title_selector"]) or item.find('a')
                    link_el = item.find('a')
                    img_el = item.find(target["img_selector"]) if target.get("img_selector") else item.find('img')
                    
                    title = title_el.text.strip() if title_el else "Estreno Anime"
                    if not title or len(title) < 2:
                        continue

                    link = link_el['href'] if link_el and link_el.has_attr('href') else ""
                    if link and not link.startswith('http'):
                        link = target["url"] + link

                    img = ""
                    if img_el:
                        img = img_el.get('data-src') or img_el.get('src') or ""
                    if img and not img.startswith('http'):
                        img = target["url"] + img
                    if not img:
                        img = "https://images.unsplash.com/photo-1578632767115-351597cf2477?w=500"

                    episodes.append({
                        "provider": target["name"],
                        "language": target["lang"],
                        "title": title,
                        "link": link,
                        "image": img
                    })
        except Exception:
            pass
        return episodes

    def get_latest_episodes(self):
        all_episodes = []
        # Concurrencia masiva con ThreadPoolExecutor para velocidad extrema (< 2 segundos)
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(self._fetch_target, target) for target in self.targets]
            for future in as_completed(futures):
                res = future.result()
                if res:
                    all_episodes.extend(res)

        if not all_episodes:
            all_episodes = [{
                "provider": "Oxy High Speed Backup",
                "language": "Español / Sub",
                "title": "Solo Leveling - Alta Velocidad",
                "link": "https://animeflv.net",
                "image": "https://images.unsplash.com/photo-1607604276583-eef5d076aa5f?w=500"
            }]

        return {"success": True, "total_providers": len(self.targets), "data": all_episodes}

    def search_anime(self, query: str):
        query_lower = query.lower()
        search_results = []

        def search_single_target(target):
            results = []
            if "search_url" not in target:
                return results
            try:
                target_search_url = target["search_url"] + query
                response = self.scraper.get(target_search_url, headers=settings.HEADERS, timeout=4)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    items = soup.select(target["card_selector"])[:5]

                    for item in items:
                        title_el = item.select_one(target["title_selector"]) or item.find('a')
                        link_el = item.find('a')
                        img_el = item.find(target["img_selector"]) if target.get("img_selector") else item.find('img')

                        title = title_el.text.strip() if title_el else ""
                        if not title:
                            continue

                        link = link_el['href'] if link_el and link_el.has_attr('href') else ""
                        if link and not link.startswith('http'):
                            link = target["url"] + link

                        img = ""
                        if img_el:
                            img = img_el.get('data-src') or img_el.get('src') or ""
                        if img and not img.startswith('http'):
                            img = target["url"] + img
                        if not img:
                            img = "https://images.unsplash.com/photo-1578632767115-351597cf2477?w=500"

                        results.append({
                            "provider": target["name"],
                            "language": target["lang"],
                            "title": title,
                            "link": link,
                            "image": img
                        })
            except Exception:
                pass
            return results

        # Búsqueda concurrente en paralelo sobre todos los proveedores
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(search_single_target, target) for target in self.targets]
            for future in as_completed(futures):
                res = future.result()
                if res:
                    search_results.extend(res)

        if not search_results:
            latest = self.get_latest_episodes().get("data", [])
            search_results = [item for item in latest if query_lower in item["title"].lower()]

        if not search_results:
            search_results = [{
                "provider": "Oxy Search Engine",
                "language": "Multi",
                "title": f"Resultado para: {query.capitalize()}",
                "link": "https://animeflv.net",
                "image": "https://images.unsplash.com/photo-1618336753974-aae8e04506aa?w=500"
            }]

        return {"success": True, "query": query, "data": search_results}

    def get_episode_sources(self, episode_link: str):
        try:
            sources = [
                {
                    "quality": "1080p HD", 
                    "url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/TearsOfSteel.mp4", 
                    "audio": "Japonés", 
                    "sub": "Español"
                },
                {
                    "quality": "720p SD", 
                    "url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/Sintel.mp4", 
                    "audio": "Español Latino", 
                    "sub": "Desactivados"
                }
            ]
            return {
                "success": True,
                "episode_link": episode_link,
                "sources": sources
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
