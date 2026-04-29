"""
RedVerse Shop — Stripe Checkout Backend
Run alongside redverse-shop.html for production Stripe checkout.

Setup:
  pip install flask stripe
  export STRIPE_SECRET_KEY='sk_live_YOUR_SECRET_KEY'
  python checkout_server.py

The HTML frontend sends cart items here, this server creates a
Stripe Checkout Session and returns the redirect URL.
"""

import os
import json
import threading
from pathlib import Path
from datetime import datetime, timezone
from flask import Flask, request, jsonify
from flask_cors import cross_origin

import stripe

app = Flask(__name__)
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY', 'sk_test_REPLACE')

# Where to redirect after checkout
YOUR_DOMAIN = os.environ.get('SHOP_DOMAIN', 'http://localhost:8800')
ENTITLEMENTS_FILE = Path(__file__).resolve().parent / 'entitlements.json'
_entitlements_lock = threading.Lock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_entitlements() -> dict:
    if not ENTITLEMENTS_FILE.exists():
        return {'users': {}}
    try:
        return json.loads(ENTITLEMENTS_FILE.read_text(encoding='utf-8'))
    except Exception:
        return {'users': {}}


def _save_entitlements(data: dict) -> None:
    ENTITLEMENTS_FILE.write_text(json.dumps(data, indent=2), encoding='utf-8')


def _user_key(user: dict) -> str:
    sub = (user or {}).get('sub', '').strip()
    email = (user or {}).get('email', '').strip().lower()
    return sub or email


def _grant_tools(user: dict, tool_ids: list[str], source: str = 'manual') -> tuple[bool, dict]:
    key = _user_key(user)
    if not key:
        return False, {'error': 'Missing user.sub or user.email'}

    clean_tool_ids = sorted({t.strip() for t in (tool_ids or []) if isinstance(t, str) and t.strip()})
    if not clean_tool_ids:
        return False, {'error': 'No tool_ids provided'}

    with _entitlements_lock:
        db = _load_entitlements()
        users = db.setdefault('users', {})
        row = users.get(key, {
            'sub': (user or {}).get('sub', ''),
            'email': (user or {}).get('email', ''),
            'name': (user or {}).get('name', ''),
            'tools': [],
            'created_at': _now_iso(),
        })

        existing = set(row.get('tools', []))
        existing.update(clean_tool_ids)
        row['tools'] = sorted(existing)
        row['updated_at'] = _now_iso()
        row['last_source'] = source
        if (user or {}).get('sub'):
            row['sub'] = user.get('sub')
        if (user or {}).get('email'):
            row['email'] = user.get('email')
        if (user or {}).get('name'):
            row['name'] = user.get('name')

        users[key] = row
        _save_entitlements(db)

    return True, {
        'ok': True,
        'user_key': key,
        'tools': row['tools'],
        'updated_at': row['updated_at'],
    }


@app.route('/create-checkout-session', methods=['POST'])
@cross_origin()
def create_checkout_session():
    """Create a Stripe Checkout Session from cart line items."""
    try:
        data = request.get_json()
        line_items = data.get('items', [])

        if not line_items:
            return jsonify({'error': 'No items in cart'}), 400

        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=line_items,
            mode='payment',
            success_url=YOUR_DOMAIN + '?checkout=success',
            cancel_url=YOUR_DOMAIN + '?checkout=cancel',
            # Optional: collect customer email
            # customer_email=data.get('email'),
        )

        return jsonify({'url': session.url})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'ok',
        'stripe_configured': bool(stripe.api_key),
        'entitlements_file': str(ENTITLEMENTS_FILE),
        'entitlements_exists': ENTITLEMENTS_FILE.exists(),
    })


@app.route('/entitlements/grant', methods=['POST'])
@cross_origin()
def grant_entitlements():
    """Grant one or more tool IDs to a user identity."""
    data = request.get_json(silent=True) or {}
    user = data.get('user') or {}
    tool_ids = data.get('tool_ids') or []
    source = data.get('source', 'manual')

    ok, payload = _grant_tools(user, tool_ids, source)
    if not ok:
        return jsonify(payload), 400
    return jsonify(payload)


@app.route('/entitlements/check', methods=['GET'])
@cross_origin()
def check_entitlement():
    """Check whether a user has access to a specific tool ID."""
    tool_id = (request.args.get('tool_id') or '').strip()
    sub = (request.args.get('sub') or '').strip()
    email = (request.args.get('email') or '').strip().lower()

    if not tool_id:
        return jsonify({'error': 'Missing tool_id'}), 400
    if not (sub or email):
        return jsonify({'error': 'Missing sub or email'}), 400

    key = sub or email
    with _entitlements_lock:
        db = _load_entitlements()
        row = db.get('users', {}).get(key, {})
        tools = row.get('tools', [])

    return jsonify({
        'tool_id': tool_id,
        'entitled': tool_id in tools,
        'user_key': key,
        'tools': tools,
    })


if __name__ == '__main__':
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get('PORT', 8915))
    print(f"🛒 RedVerse Checkout Server running on http://127.0.0.1:{port}")
    print(f"   Redirect domain: {YOUR_DOMAIN}")
    app.run(host='127.0.0.1', port=port, debug=True)
