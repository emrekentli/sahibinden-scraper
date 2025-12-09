from flask import Flask, render_template, jsonify, request, redirect, url_for
from flask_socketio import SocketIO, emit
import json
import os
import threading
import time
from datetime import datetime
from sahibinden_scraper import SahibindenScraper

app = Flask(__name__)
app.config['SECRET_KEY'] = 'sahibinden-scraper-secret-2024'
socketio = SocketIO(app, cors_allowed_origins="*")

# Global scraper instance
scraper_instance = None
scraper_thread = None
scraper_running = False

# Data directory
DATA_DIR = '/app/data' if os.path.exists('/app/data') else '.'
CONFIG_FILE = 'config.json'
LISTINGS_FILE = os.path.join(DATA_DIR, 'filtered_listings.json')
LOG_FILE = 'sahibinden_scraper.log'
COOKIES_FILE = os.path.join(DATA_DIR, 'sahibinden_cookies.json')

def load_config():
    """Load config.json"""
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        return {
            'check_interval_minutes': 30,
            'max_replaced_parts': 1,
            'max_painted_parts': 2,
            'brands': []
        }

def save_config(config):
    """Save config.json"""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

def load_listings():
    """Load filtered listings"""
    try:
        if os.path.exists(LISTINGS_FILE):
            with open(LISTINGS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    except:
        return []

def get_logs(limit=100):
    """Get last N lines from log file"""
    try:
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                return lines[-limit:]
        return []
    except:
        return []

def scraper_background_task():
    """Background task to run scraper"""
    global scraper_running
    try:
        scraper = SahibindenScraper()
        scraper.run()
    except Exception as e:
        print(f"Scraper error: {e}")
    finally:
        scraper_running = False

@app.route('/')
def index():
    """Dashboard home page"""
    config = load_config()
    listings = load_listings()
    logs = get_logs(50)

    stats = {
        'total_brands': len(config.get('brands', [])),
        'enabled_brands': len([b for b in config.get('brands', []) if b.get('enabled', True)]),
        'total_listings': len(listings),
        'scraper_running': scraper_running,
        'check_interval': config.get('check_interval_minutes', 30),
        'max_replaced': config.get('max_replaced_parts', 1),
        'max_painted': config.get('max_painted_parts', 2),
        'has_cookies': os.path.exists(COOKIES_FILE)
    }

    return render_template('index.html', stats=stats, listings=listings[:10], logs=logs)

@app.route('/api/config', methods=['GET', 'POST'])
def api_config():
    """Get or update config"""
    if request.method == 'POST':
        config = request.json
        save_config(config)
        return jsonify({'success': True, 'message': 'Configuration saved'})
    else:
        return jsonify(load_config())

@app.route('/api/listings')
def api_listings():
    """Get all listings"""
    return jsonify(load_listings())

@app.route('/api/logs')
def api_logs():
    """Get logs"""
    limit = request.args.get('limit', 100, type=int)
    return jsonify({'logs': get_logs(limit)})

@app.route('/api/stats')
def api_stats():
    """Get current stats"""
    config = load_config()
    listings = load_listings()

    return jsonify({
        'total_brands': len(config.get('brands', [])),
        'enabled_brands': len([b for b in config.get('brands', []) if b.get('enabled', True)]),
        'total_listings': len(listings),
        'scraper_running': scraper_running,
        'check_interval': config.get('check_interval_minutes', 30),
        'has_cookies': os.path.exists(COOKIES_FILE),
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/scraper/start', methods=['POST'])
def start_scraper():
    """Start scraper in background"""
    global scraper_thread, scraper_running

    if scraper_running:
        return jsonify({'success': False, 'message': 'Scraper is already running'})

    scraper_running = True
    scraper_thread = threading.Thread(target=scraper_background_task, daemon=True)
    scraper_thread.start()

    return jsonify({'success': True, 'message': 'Scraper started'})

@app.route('/api/scraper/stop', methods=['POST'])
def stop_scraper():
    """Stop scraper"""
    global scraper_running
    scraper_running = False
    return jsonify({'success': True, 'message': 'Scraper stop requested'})

@app.route('/api/scraper/run-now', methods=['POST'])
def run_scraper_now():
    """Run scraper once manually"""
    try:
        scraper = SahibindenScraper()
        # Run in a thread so we can return immediately
        threading.Thread(target=scraper.run_single_check, daemon=True).start()
        return jsonify({'success': True, 'message': 'Manual scrape started'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/cookie/upload', methods=['POST'])
def upload_cookie():
    """Upload cookie file"""
    try:
        if 'cookie' not in request.files:
            return jsonify({'success': False, 'message': 'No cookie file provided'})

        cookie_file = request.files['cookie']
        if cookie_file.filename == '':
            return jsonify({'success': False, 'message': 'No file selected'})

        # Save cookie file
        cookie_file.save(COOKIES_FILE)

        return jsonify({'success': True, 'message': 'Cookie uploaded successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/config')
def config_page():
    """Config editor page"""
    config = load_config()
    return render_template('config.html', config=config)

@app.route('/listings')
def listings_page():
    """Listings viewer page"""
    listings = load_listings()
    return render_template('listings.html', listings=listings)

@app.route('/logs')
def logs_page():
    """Logs viewer page"""
    logs = get_logs(200)
    return render_template('logs.html', logs=logs)

# WebSocket for real-time log streaming
@socketio.on('connect')
def handle_connect():
    """Client connected"""
    emit('connected', {'data': 'Connected to log stream'})

@socketio.on('request_logs')
def handle_request_logs():
    """Send logs to client"""
    logs = get_logs(50)
    emit('logs_update', {'logs': logs})

if __name__ == '__main__':
    # Start Flask with SocketIO
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)
