#!/bin/bash
###############################################################################
# RedVerse Quick Start Setup
# 
# This script sets up the development environment with Google Auth integration
#
# Usage: bash setup.sh
###############################################################################

set -e  # Exit on error

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║  🏰 RedVerse Setup Script                                      ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found!"
    echo "   Create it first: python3.15 -m venv venv"
    exit 1
fi

# Activate venv
echo "✓ Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "✓ Installing dependencies from requirements.txt..."
python -m pip install -q -r requirements.txt

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "✓ Creating .env file..."
    cat > .env << 'EOF'
# Google OAuth Configuration
GOOGLE_CLIENT_SECRETS=/home/crimson/Desktop/Laptop/client_secret_999940301372-lsv85hnhe6ucju10uhhg2u36k1j8is9f.apps.googleusercontent.com.json
GOOGLE_REDIRECT_URI=http://localhost:8800/auth/google/callback
SESSION_SECRET=dev-session-secret-change-in-production

# Stripe Configuration (if using checkout)
# STRIPE_SECRET_KEY=sk_test_YOUR_KEY_HERE

# Server Configuration
PORT=8800
FLASK_ENV=development
EOF
    echo "   ⚠️  Update .env with your actual secrets!"
else
    echo "✓ .env file already exists"
fi

# Check for Google credentials
if [ ! -f "client_secret_999940301372-lsv85hnhe6ucju10uhhg2u36k1j8is9f.apps.googleusercontent.com.json" ]; then
    echo ""
    echo "⚠️  WARNING: Google OAuth credentials not found!"
    echo "   Download from: https://console.cloud.google.com/apis/credentials"
    echo "   Save as: client_secret_999940301372-lsv85hnhe6ucju10uhhg2u36k1j8is9f.apps.googleusercontent.com.json"
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Update .env with your actual secrets:"
echo "     nano .env"
echo ""
echo "  2. Download Google OAuth credentials from:"
echo "     https://console.cloud.google.com/apis/credentials"
echo ""
echo "  3. Start the server:"
echo "     python app.py"
echo "     OR use the repo entrypoint: python main.py --auto-start"
echo ""
echo "  4. Open in browser:"
echo "     http://127.0.0.1:8800/login.html"
echo ""
echo "For more info, see GOOGLE_AUTH_SETUP.md"
echo ""
