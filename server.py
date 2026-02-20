#!/usr/bin/env python3
"""
RedVerse Backend Server
Handles Stripe payment processing for the Support Chapel
"""

import os
import urllib.parse
import stripe
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for frontend requests

# Serve static music files
from flask import send_from_directory

@app.route('/assets/music/<path:filename>')
def serve_music(filename):
    music_dir = os.path.join(os.path.dirname(__file__), 'assets', 'music')
    return send_from_directory(music_dir, filename)

# Configure Stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'RedVerse Payment Server',
        'stripe_configured': bool(stripe.api_key)
    }), 200

@app.route('/create-payment-intent', methods=['POST'])
def create_payment_intent():
    """
    Create a Stripe PaymentIntent for the requested amount
    
    Expected payload:
    {
        "amount": 500  // Amount in cents (e.g., 500 = $5.00)
    }
    
    Returns:
    {
        "clientSecret": "pi_xxx_secret_xxx"
    }
    """
    try:
        data = request.get_json()
        
        # Validate amount
        amount = data.get('amount')
        if not amount or not isinstance(amount, int) or amount <= 0:
            return jsonify({
                'error': 'Invalid amount. Must be a positive integer in cents.'
            }), 400
        
        # Enforce minimum amount (50 cents / $0.50)
        if amount < 50:
            return jsonify({
                'error': 'Amount too small. Minimum is $0.50 USD.'
            }), 400
        
        # Enforce maximum amount ($999,999.99)
        if amount > 99999999:
            return jsonify({
                'error': 'Amount too large. Maximum is $999,999.99 USD.'
            }), 400
        
        # Create PaymentIntent
        payment_intent = stripe.PaymentIntent.create(
            amount=amount,
            currency='usd',
            automatic_payment_methods={
                'enabled': True,
            },
            metadata={
                'source': 'RedVerse Support Chapel',
                'project': 'The Church'
            }
        )
        
        return jsonify({
            'clientSecret': payment_intent.client_secret
        }), 200
        
    except stripe.error.StripeError as e:
        # Handle Stripe-specific errors
        return jsonify({
            'error': f'Stripe error: {str(e)}'
        }), 500
        
    except Exception as e:
        # Handle general errors
        return jsonify({
            'error': f'Server error: {str(e)}'
        }), 500

@app.route('/api/music/list', methods=['GET'])
def list_music():
    """
    List all music files in the assets/music folder
    Returns a JSON array of file paths ready to play
    """
    try:
        music_dir = os.path.join(os.path.dirname(__file__), 'assets', 'music')
        
        if not os.path.exists(music_dir):
            return jsonify({'files': []}), 200
        
        # Get all audio files (mp3, wav, ogg, m4a)
        audio_extensions = {'.mp3', '.wav', '.ogg', '.m4a', '.flac'}
        files = []
        
        for filename in sorted(os.listdir(music_dir)):
            if os.path.splitext(filename)[1].lower() in audio_extensions:
                # Return absolute URL-encoded path that can be served
                file_path = '/assets/music/' + urllib.parse.quote(filename)
                files.append(file_path)
        
        return jsonify({
            'files': files,
            'count': len(files),
            'directory': music_dir
        }), 200
        
    except Exception as e:
        return jsonify({
            'error': f'Failed to list music files: {str(e)}',
            'files': []
        }), 500

@app.route('/webhook', methods=['POST'])
def webhook():
    """
    Stripe webhook endpoint for payment events
    Configure this URL in your Stripe dashboard
    """
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')
    webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
    except ValueError:
        # Invalid payload
        return jsonify({'error': 'Invalid payload'}), 400
    except stripe.error.SignatureVerificationError:
        # Invalid signature
        return jsonify({'error': 'Invalid signature'}), 400
    
    # Handle the event
    if event['type'] == 'payment_intent.succeeded':
        payment_intent = event['data']['object']
        print(f"✅ Payment succeeded: {payment_intent['id']} for ${payment_intent['amount']/100:.2f}")
        # Here you could:
        # - Send confirmation email
        # - Update database
        # - Trigger fulfillment
        
    elif event['type'] == 'payment_intent.payment_failed':
        payment_intent = event['data']['object']
        print(f"❌ Payment failed: {payment_intent['id']}")
        
    return jsonify({'received': True}), 200

if __name__ == '__main__':
    # Check if Stripe key is configured
    if not stripe.api_key:
        print("⚠️  WARNING: STRIPE_SECRET_KEY not configured!")
        print("   Set it in your .env file to enable payments.")
    else:
        print(f"✅ Stripe configured with key: {stripe.api_key[:7]}...")
    
    # Start the server
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_ENV') == 'development'
    
    print(f"🔥 RedVerse Payment Server starting on port {port}")
    print(f"   Health check: http://localhost:{port}/health")
    print(f"   Payment endpoint: http://localhost:{port}/create-payment-intent")
    
    app.run(host='0.0.0.0', port=port, debug=debug)
