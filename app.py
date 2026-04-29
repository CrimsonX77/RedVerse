"""
RedVerse Main Application Flask Server
Integrates Google OAuth2, Stripe checkout, and static file serving

Run:
  export GOOGLE_CLIENT_SECRETS='path/to/client_secret_*.json'
  export STRIPE_SECRET_KEY='sk_live_...'
  python app.py
"""

import json
import mimetypes
import os
import threading
import importlib.util
from pathlib import Path
from flask import Flask, send_from_directory, jsonify, request

# Ensure browsers receive correct MIME types for video/audio formats
mimetypes.add_type('video/mp4',        '.mp4')
mimetypes.add_type('video/webm',       '.webm')
mimetypes.add_type('video/quicktime',  '.mov')
mimetypes.add_type('video/x-matroska','.mkv')
mimetypes.add_type('audio/mpeg',       '.mp3')
mimetypes.add_type('audio/ogg',        '.ogg')
mimetypes.add_type('audio/wav',        '.wav')
mimetypes.add_type('audio/flac',       '.flac')
mimetypes.add_type('audio/mp4',        '.m4a')
from flask_cors import CORS
from auth import init_auth, require_auth, get_current_user

# ── APP SETUP ──────────────────────────────────────────────────────

app = Flask(
    __name__,
    static_folder='.',
    static_url_path='',
)

# Enable CORS
CORS(app, resources={
    r"/api/*": {"origins": ["localhost", "127.0.0.1"]},
    r"/auth/*": {"origins": ["localhost", "127.0.0.1"]},
})

# Initialize authentication
init_auth(app)


# ── GDM (Gaussian Delta Memory) Integration ──────────────────────────────────

_GDM_MODULE = None
_GDM_LOCK = threading.Lock()
_GDM_INSTANCES = {}


def _load_gdm_module():
    global _GDM_MODULE
    if _GDM_MODULE is not None:
        return _GDM_MODULE

    module_path = Path(__file__).resolve().parent / "control hall" / "gdm_core.py"
    if not module_path.exists():
        raise FileNotFoundError(f"GDM core not found: {module_path}")

    spec = importlib.util.spec_from_file_location("redverse_gdm_core", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load GDM module spec")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _GDM_MODULE = module
    return module


def _get_user_gdm(user_id: str):
    with _GDM_LOCK:
        if user_id in _GDM_INSTANCES:
            return _GDM_INSTANCES[user_id]

        gdm_module = _load_gdm_module()
        gdm_config_cls = getattr(gdm_module, "GDMConfig")
        gdm_engine_cls = getattr(gdm_module, "GaussianDeltaMemory")

        # Default to test embedding backend unless user explicitly set one.
        backend = os.environ.get("GDM_EMBED_BACKEND", "test")
        storage_path = str(Path(__file__).resolve().parent / "user_data" / "{soul_id}" / "gdm")

        config = gdm_config_cls.from_env()
        config.embedding_backend = backend
        config.storage_path = storage_path
        config.auto_persist_interval = 25

        gdm = gdm_engine_cls(config=config, soul_id=user_id)
        try:
            gdm.load()
        except Exception:
            pass

        _GDM_INSTANCES[user_id] = gdm
        return gdm

# ── STATIC FILES ───────────────────────────────────────────────────

@app.route('/', methods=['GET'])
def index():
    """Serve the main index page."""
    return send_from_directory('.', 'index.html')


@app.route('/assets/<path:filename>', methods=['GET'])
def serve_assets(filename):
    """Serve assets using a layered fallback strategy.

    HTML pages reference assets as ``assets/<name>`` but the actual files
    live in several locations within the repository:

    1. ``assets/<filename>``          - canonical location (populated over time)
    2. ``visualassets/<basename>``    - current home for all image assets
    3. ``E_Drive_rings/<basename>``   - E-Drive ring PNGs
    4. ``<basename>``                 - root-level files (mp4 videos, etc.)
    5. ``<filename>`` at repo root    - handles refs like assets/visualassets/x.png

    Adding a file to *any* of these locations makes it immediately available
    at the ``/assets/...`` URL the HTML already uses.
    """
    from werkzeug.utils import safe_join
    from werkzeug.exceptions import NotFound

    base_dir = os.path.dirname(os.path.abspath(__file__))

    # Sanitise the URL-supplied path: strip any component that would escape the
    # base directory (e.g. "../../etc/passwd").  Depending on the werkzeug
    # version, safe_join either raises NotFound or returns None for traversal
    # attempts; we handle both cases.
    def _safe_isfile(base, *parts):
        """Return the joined path only when it is a regular file and stays
        within *base*; return None on path-traversal attempts."""
        try:
            joined = safe_join(base, *parts)
        except NotFound:
            return None
        return joined if (joined is not None and os.path.isfile(joined)) else None

    # Extract just the final filename component (safe — basename never traverses).
    basename = os.path.basename(filename)

    # 1. Canonical assets/ directory (works once files are placed there)
    if _safe_isfile(base_dir, 'assets', filename):
        return send_from_directory(os.path.join(base_dir, 'assets'), filename)

    # 2 & 3. Named sub-directories at repo root
    for subdir in ('visualassets', 'E_Drive_rings'):
        if _safe_isfile(base_dir, subdir, basename):
            return send_from_directory(os.path.join(base_dir, subdir), basename)

    # 4. Repo root (mp4 videos sit here)
    if _safe_isfile(base_dir, basename):
        return send_from_directory(base_dir, basename)

    # 5. Full relative path from repo root (handles assets/visualassets/foo.png)
    if _safe_isfile(base_dir, filename):
        return send_from_directory(base_dir, filename)

    # Nothing found - return a proper 404 rather than a 500
    return jsonify({'error': 'Asset not found: ' + filename}), 404


@app.route('/api/music/list', methods=['GET'])
def list_music():
    """Return sorted list of music file paths for the player widget.

    Searches in priority order:
      1. ``assets/music/``  - canonical location
      2. ``assets/``        - loose files in the assets directory
      3. Repo root          - music dropped at the top level

    When none of those directories contain audio files the endpoint returns
    ``{"files": []}`` so the player widget degrades gracefully.
    Music files are NOT currently in the repository; drop .mp3/.ogg/.wav/.flac
    files into assets/music/ (create the folder first) to populate the player.
    """
    from urllib.parse import quote
    base_dir = os.path.dirname(os.path.abspath(__file__))
    audio_exts = ('.mp3', '.ogg', '.wav', '.flac', '.m4a')

    found = {}  # basename -> URL  (deduplicates across search dirs)

    search_locations = [
        (os.path.join(base_dir, 'assets', 'music'), '/assets/music/'),
        (os.path.join(base_dir, 'assets'),           '/assets/'),
        (base_dir,                                   '/'),
    ]
    for directory, url_prefix in search_locations:
        if not os.path.isdir(directory):
            continue
        for fname in sorted(os.listdir(directory)):
            if fname.lower().endswith(audio_exts) and fname not in found:
                found[fname] = url_prefix + quote(fname)

    return jsonify({'files': sorted(found.values())})


@app.get('/api/gdm/status')
@require_auth
def gdm_status():
    user = get_current_user() or {}
    user_id = user.get('id')
    if not user_id:
        return jsonify({'error': 'No authenticated user context'}), 401

    gdm = _get_user_gdm(user_id)
    stats = gdm.field_stats()
    return jsonify({'ok': True, 'user_id': user_id, 'stats': stats})


@app.post('/api/gdm/remember')
@require_auth
def gdm_remember():
    user = get_current_user() or {}
    user_id = user.get('id')
    if not user_id:
        return jsonify({'error': 'No authenticated user context'}), 401

    payload = request.get_json(silent=True) or {}
    content = (payload.get('content') or '').strip()
    if not content:
        return jsonify({'error': 'content is required'}), 400

    role = payload.get('role', 'user')
    tags = payload.get('tags') if isinstance(payload.get('tags'), list) else []
    emotional_weight = float(payload.get('emotional_weight', 0.0))

    gdm = _get_user_gdm(user_id)
    entry = gdm.remember(
        content=content,
        role=role,
        tags=tags,
        emotional_weight=max(0.0, min(1.0, emotional_weight)),
    )
    gdm.save()

    return jsonify({'ok': True, 'entry_id': entry.id})


@app.post('/api/gdm/recall')
@require_auth
def gdm_recall():
    user = get_current_user() or {}
    user_id = user.get('id')
    if not user_id:
        return jsonify({'error': 'No authenticated user context'}), 401

    payload = request.get_json(silent=True) or {}
    query = (payload.get('query') or '').strip()
    if not query:
        return jsonify({'error': 'query is required'}), 400

    k = int(payload.get('k', 5))
    temperature = float(payload.get('temperature', 1.0))

    gdm = _get_user_gdm(user_id)
    results = gdm.recall(context=query, k=max(1, min(k, 20)), temperature=temperature)
    gdm.save()

    return jsonify({
        'ok': True,
        'results': [
            {
                'id': r.entry.id,
                'role': r.entry.role,
                'content': r.entry.content,
                'probability': r.probability,
                'score': r.raw_score,
                'tags': r.entry.tags,
            }
            for r in results
        ]
    })


# ── Cinema Catalog API ─────────────────────────────────────────────

CINEMA_PRICES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cinema_prices.json')

def load_cinema_prices():
    """Load per-filename price overrides from cinema_prices.json."""
    try:
        with open(CINEMA_PRICES_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return {}

def save_cinema_prices(data):
    with open(CINEMA_PRICES_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def filename_to_title(name):
    """Convert a filename (no extension) to a human-readable title."""
    import re
    name = os.path.splitext(name)[0]
    name = name.replace('_', ' ').replace('-', ' ')
    name = re.sub(r'\s+', ' ', name).strip()
    return name.title()

@app.route('/api/cinema/catalog', methods=['GET'])
def cinema_catalog():
    """Scan assets/music and assets/film and return unified cinema catalog."""
    from urllib.parse import quote
    base = os.path.dirname(os.path.abspath(__file__))
    prices = load_cinema_prices()

    catalog = []

    music_dir = os.path.join(base, 'assets', 'music')
    if os.path.isdir(music_dir):
        for f in sorted(os.listdir(music_dir)):
            if f.lower().endswith(('.mp3', '.ogg', '.wav', '.flac', '.m4a')):
                price = prices.get(f, 0)
                catalog.append({
                    'id': 'fs_audio_' + quote(f, safe=''),
                    'type': 'audio',
                    'title': filename_to_title(f),
                    'filename': f,
                    'path': '/assets/music/' + quote(f),
                    'price': price,
                    'locked': price > 0,
                    'hasThumb': False,
                    'hasBlob': False,
                    'gems': 0,
                    'tags': ['music'],
                    'year': '',
                    'description': '',
                    'source': 'filesystem',
                })

    film_dir = os.path.join(base, 'assets', 'film')
    if os.path.isdir(film_dir):
        for f in sorted(os.listdir(film_dir)):
            if f.lower().endswith(('.mp4', '.webm', '.mov', '.mkv', '.avi')):
                price = prices.get(f, 0)
                catalog.append({
                    'id': 'fs_video_' + quote(f, safe=''),
                    'type': 'video',
                    'title': filename_to_title(f),
                    'filename': f,
                    'path': '/assets/film/' + quote(f),
                    'price': price,
                    'locked': price > 0,
                    'hasThumb': False,
                    'hasBlob': False,
                    'gems': 0,
                    'tags': ['film'],
                    'year': '',
                    'description': '',
                    'source': 'filesystem',
                })

    return jsonify(catalog)


@app.route('/api/cinema/prices', methods=['GET'])
def get_cinema_prices():
    """Get all price overrides."""
    return jsonify(load_cinema_prices())


@app.route('/api/cinema/prices', methods=['POST'])
def set_cinema_prices():
    """Set price overrides. Body: { filename: price_in_gems }"""
    try:
        data = request.get_json(force=True)
        if not isinstance(data, dict):
            return jsonify({'error': 'Expected JSON object'}), 400
        # Validate all values are non-negative numbers
        for k, v in data.items():
            if not isinstance(v, (int, float)) or v < 0:
                return jsonify({'error': f'Invalid price for {k}'}), 400
        save_cinema_prices(data)
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/gems/checkout', methods=['POST'])
def gems_checkout():
    """Create a Stripe checkout session for gem purchases.
    Body: { pack: { gems: int, price_cents: int, label: str } }
    """
    try:
        import stripe
        data = request.get_json(force=True)
        pack = data.get('pack', {})

        stripe.api_key = os.environ.get('STRIPE_SECRET_KEY', '')
        if not stripe.api_key:
            return jsonify({'error': 'Stripe not configured', 'demo': True}), 402

        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'unit_amount': pack.get('price_cents', 100),
                    'product_data': {
                        'name': f"{pack.get('gems', 0)} Soul Gems",
                        'description': 'Redverse Soul Gems — unlock premium cinema content',
                    },
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=request.host_url + 'gemsshoppage.html?purchase=success&gems=' + str(pack.get('gems', 0)),
            cancel_url=request.host_url + 'gemsshoppage.html?purchase=cancel',
        )
        return jsonify({'url': session.url})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/<path:path>', methods=['GET'])
def serve_static(path):
    """Serve static files (HTML, CSS, JS, etc.)."""
    if path.startswith('api/') or path.startswith('auth/'):
        return jsonify({'error': 'Not found'}), 404
    return send_from_directory('.', path)


# ── HEALTH CHECK ───────────────────────────────────────────────────

@app.route('/health', methods=['GET'])
def health():
    """API health check."""
    return jsonify({
        'status': 'ok',
        'service': 'redverse',
        'version': '1.0.0',
    })


# ── ERROR HANDLERS ─────────────────────────────────────────────────

@app.errorhandler(404)
def not_found(e):
    """Handle 404 errors by serving index.html for SPA routing."""
    return send_from_directory('.', 'index.html'), 200


@app.errorhandler(500)
def server_error(e):
    """Handle 500 errors."""
    return jsonify({'error': 'Internal server error'}), 500


# ── ENTRY POINT ────────────────────────────────────────────────────

if __name__ == '__main__':
    import sys

    port = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get('PORT', 8800))

    # ── Asset diagnostics ──────────────────────────────────────────
    _repo_root  = os.path.dirname(os.path.abspath(__file__))
    _img_count  = len(os.listdir(os.path.join(_repo_root, 'visualassets'))) if os.path.isdir(os.path.join(_repo_root, 'visualassets')) else 0
    _vid_count  = len([f for f in os.listdir(_repo_root) if f.lower().endswith(('.mp4', '.webm', '.mov'))])
    _audio_exts = ('.mp3', '.ogg', '.wav', '.flac', '.m4a')
    _music_dirs = [
        os.path.join(_repo_root, 'assets', 'music'),
        os.path.join(_repo_root, 'assets'),
        _repo_root,
    ]
    _music_count = sum(
        len([f for f in os.listdir(d) if f.lower().endswith(_audio_exts)])
        for d in _music_dirs if os.path.isdir(d)
    )
    _music_note = (
        f"{_music_count} file(s) found" if _music_count
        else "NONE — drop .mp3/.ogg files into assets/music/"
    )

    print(f"""
╔════════════════════════════════════════════════════════════════╗
║  🏰 REDVERSE Main Server                                       ║
║  Serving on http://127.0.0.1:{port:<34}║
║                                                                ║
║  📍 Routes:                                                    ║
║     • /                   → index.html (SPA)                  ║
║     • /auth/google/login  → Google OAuth2 flow                ║
║     • /auth/status        → Check auth status                 ║
║     • /health             → Health check                      ║
║                                                                ║
║  🖼  Images  (visualassets/): {_img_count:<33}║
║  🎬 Videos  (root *.mp4):    {_vid_count:<33}║
║  🎵 Music:                   {_music_note:<33}║
╚════════════════════════════════════════════════════════════════╝
    """)
    
    app.run(
        host='127.0.0.1',
        port=port,
        debug=True,
        use_reloader=True,
    )
