#!/bin/bash

# RedVerse Authentication Quick Start
# Complete setup in under 5 minutes

set -e

PROJECT_ROOT="/home/crimson/Desktop/Laptop"
CREDENTIALS_FILE="client_secret_999940301372-lsv85hnhe6ucju10uhhg2u36k1j8is9f.apps.googleusercontent.com.json"

echo "╔════════════════════════════════════╗"
echo "║  RedVerse Auth Quick Start Setup   ║"
echo "╚════════════════════════════════════╝"
echo ""

# Step 1: Activate venv
echo "📦 Step 1: Activating virtual environment..."
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found!"
    echo "   Create with: python3.15 -m venv venv"
    exit 1
fi

source venv/bin/activate
echo "✓ Virtual environment activated"
echo ""

# Step 2: Check dependencies
echo "📚 Step 2: Verifying dependencies..."
pip -q install -r requirements.txt 2>/dev/null
echo "✓ Dependencies installed"
echo ""

# Step 3: Check credentials
echo "🔑 Step 3: Checking Google credentials..."
if [ ! -f "$CREDENTIALS_FILE" ]; then
    echo "❌ Credentials file not found!"
    echo ""
    echo "   Download from: https://console.cloud.google.com/apis/credentials"
    echo "   Steps:"
    echo "   1. Click: Create Credentials → OAuth 2.0 Client ID"
    echo "   2. Choose: Web application"
    echo "   3. Add Authorized redirect URIs:"
    echo "      - http://localhost:8800/auth/google/callback"
    echo "      - http://127.0.0.1:8800/auth/google/callback"
    echo "   4. Download JSON"
    echo "   5. Save as: $CREDENTIALS_FILE"
    echo ""
    exit 1
fi
echo "✓ Credentials file found"
echo ""

# Step 4: Create .env file
echo "⚙️  Step 4: Configuring environment..."
if [ ! -f ".env" ]; then
    cat > .env << 'EOF'
# Google OAuth Configuration
GOOGLE_CLIENT_SECRETS=/home/crimson/Desktop/Laptop/client_secret_999940301372-lsv85hnhe6ucju10uhhg2u36k1j8is9f.apps.googleusercontent.com.json
GOOGLE_REDIRECT_URI=http://localhost:8800/auth/google/callback
SESSION_SECRET=dev-session-secret-change-in-production

# Server Configuration
PORT=8800
FLASK_ENV=development
FLASK_DEBUG=1
EOF
    echo "✓ Created .env file"
else
    echo "✓ .env file already exists"
fi
echo ""

# Step 5: Verify application files
echo "📄 Step 5: Verifying application files..."
REQUIRED_FILES=(
    "auth.py"
    "app.py"
    "js/auth-client.js"
    "GOOGLE_AUTH_SETUP.md"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "  ✓ $file"
    else
        echo "  ❌ $file (missing)"
    fi
done
echo ""

# Step 6: Ready to start
echo "🚀 Step 6: Ready to launch!"
echo ""
echo "╔════════════════════════════════════╗"
echo "║  SETUP COMPLETE - START SERVER     ║"
echo "╚════════════════════════════════════╝"
echo ""
echo "Run:"
echo "  python app.py"
echo ""
echo "Then open browser to:"
echo "  http://localhost:8800"
echo ""
echo "Test the OAuth flow:"
echo "  1. Click 'Sign In' button"
echo "  2. Authenticate with Google"
echo "  3. Verify redirect back to home page"
echo ""
echo "Documentation:"
echo "  📖 Setup Guide:       GOOGLE_AUTH_SETUP.md"
echo "  📖 Examples:          INTEGRATION_EXAMPLES.md"
echo "  📖 Troubleshooting:   TROUBLESHOOTING.md"
echo "  📖 Testing:           test-auth.sh"
echo ""

deactivate
