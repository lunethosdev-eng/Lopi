import cloudscraper
from bs4 import BeautifulSoup
from config import settings

class AnimeScraper:
    def __init__(self):
        # cloudscraper maneja automáticamente Cloudflare y retos de JS
        self.scraper = cloudscraper.create_scraper(
            browser={'browser': 'chrome', 'platform': 'android', 'desktop': False}
        )
        
        # Lista de múltiples objetivos (targets) con sus selectores personalizados
        self.targets = [
            {
                "name": "AnimeFlv-Like",
                "url": "https://animeflv.net",  # Puedes cambiar o añadir URLs reales
                "card_selector": "article.anime",
                "title_selector": "h3",
            },
            {
                "name": "JkAnime-Like",
                "url": "https://jkanime.net",  # Servidor alternativo de respaldo
                "card_selector": ".elemento",
                "title_selector": "h3",
            }
        ]

    def get_latest_episodes(self):
        all_episodes = []
        
        # Itera sobre cada target configurado para recolectar contenido
        for target in self.targets:
            try:
                response = self.scraper.get(target["url"], headers=settings.HEADERS, timeout=10)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    items = soup.select(target["card_selector"])[:15]
                    for item in items:
                        title_el = item.select_one(target["title_selector"])
                        link_el = item.find('a')
                        
                        title = title_el.text.strip() if title_el else "Sin título"
                        link = link_el['href'] if link_el and link_el.has_attr('href') else ""
                        
                        # Asegurar que el enlace sea absoluto
                        if link and not link.startswith('http'):
                            link = target["url"] + link

                        all_episodes.append({
                            "source": target["name"],
                            "title": title,
                            "link": link
                        })
            except Exception as e:
                # Si un target falla o bloquea la IP, pasa al siguiente de forma transparente
                continue

        if not all_episodes:
            return {"success": False, "error": "No se pudieron obtener episodios de ningún servidor objetivo."}

        return {"success": True, "data": all_episodes}

    def get_episode_sources(self, episode_link: str):
        try:
            response = self.scraper.get(episode_link, headers=settings.HEADERS, timeout=10)
            if response.status_code != 200:
                return {"success": False, "error": "No se pudo acceder al enlace del episodio"}
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Aquí puedes implementar la extracción dinámica de los iframes o enlaces .mp4/.m3u8 
            # inspirada en la lógica de repositorios de APIs de anime en español.
            sources = [
                {"quality": "1080p", "url": "https://example.com/video_1080p.mp4", "audio": "Japonés", "sub": "Español"},
                {"quality": "720p", "url": "https://example.com/video_720p.mp4", "audio": "Español Latino", "sub": "Desactivados"}
            ]
            
            return {
                "success": True,
                "episode_link": episode_link,
                "sources": sources
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
