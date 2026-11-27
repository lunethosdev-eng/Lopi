import cloudscraper
from bs4 import BeautifulSoup

class AnimeScraper:
    def __init__(self):
        # cloudscraper maneja automáticamente los retos de Cloudflare (JavaScript / Cookies)
        self.scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'firefox',
                'platform': 'android',
                'desktop': False
            }
        )
        self.base_url = "https://tu-sitio-de-anime-ejemplo.com" # Reemplaza con la fuente real

    def get_latest_episodes(self):
        try:
            response = self.scraper.get(self.base_url)
            if response.status_code != 200:
                return {"error": "No se pudo conectar con la fuente", "status": response.status_code}
            
            soup = BeautifulSoup(response.text, 'html.parser')
            episodes = []

            # Selector de ejemplo para extraer elementos (ajústalo según la página objetivo)
            for item in soup.select('.anime-card-class'):
                title = item.find('h3').get_text(strip=True) if item.find('h3') else "Sin título"
                link = item.find('a')['href'] if item.find('a') else ""
                image = item.find('img')['src'] if item.find('img') else ""
                
                episodes.append({
                    "title": title,
                    "link": link,
                    "image": image
                })

            return {"success": True, "data": episodes}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_episode_servers(self, episode_url):
        try:
            response = self.scraper.get(episode_url)
            soup = BeautifulSoup(response.text, 'html.parser')
            servers = []

            # Extraer reproductores de video (iframe, links directos mp4, m3u8)
            for server in soup.select('.player-server-selector'):
                servers.append({
                    "name": server.get_text(strip=True),
                    "url": server.get('data-video', '')
                })

            return {"success": True, "servers": servers}
        except Exception as e:
            return {"success": False, "error": str(e)}
