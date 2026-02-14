#!/bin/bash
# RedVerse Payment Server Launcher

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Load environment variables if .env exists
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed or not in PATH"
    exit 1
fi

# Check if required packages are installed
echo "🔍 Checking dependencies..."
python3 -c "import flask, stripe, flask_cors, dotenv" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "📦 Installing required packages..."
    pip install flask flask-cors stripe python-dotenv
fi

# Start the server
echo ""
echo "🔥 Starting RedVerse Payment Server..."
echo "   Press Ctrl+C to stop"
echo ""

python3 server.py
