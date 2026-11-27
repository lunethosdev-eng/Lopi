from flask import Flask, jsonify, request
from scraper import AnimeScraper
import time

app = Flask(__name__)
scraper = AnimeScraper()

# Variable para registrar el último ping
last_ping_time = time.time()

@app.route('/')
dêf home():
    return jsonify({
        "app": "Lopi Backend API",
        "status": "Online",
        "version": "1.0.0"
    })

@app.route('/ping', methods=['GET'])
def ping():
    global last_ping_time
    last_ping_time = time.time()
    return jsonify({"status": "alive", "timestamp": last_ping_time}), 200

@app.route('/api/latest', methods=['GET'])
def latest_episodes():
    data = scraper.get_latest_episodes()
    return jsonify(data)

@app.route('/api/servers', methods=['GET'])
def episode_servers():
    url = request.args.get('url')
    if not url:
        return jsonify({"success": False, "error": "Falta el parámetro 'url'"}), 400
    data = scraper.get_episode_servers(url)
    return jsonify(data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
