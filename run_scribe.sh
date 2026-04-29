#!/bin/bash
# Launch script for Scribe with Google Cloud credentials

# Set Google Cloud credentials
export GOOGLE_APPLICATION_CREDENTIALS="/home/crimson/Desktop/hello/open-webui/scribe-486923-ffbe3bcd944a.json"

# Verify credentials file exists
if [ ! -f "$GOOGLE_APPLICATION_CREDENTIALS" ]; then
    echo "❌ Error: Credentials file not found at $GOOGLE_APPLICATION_CREDENTIALS"
    exit 1
fi

echo "✅ Using credentials: $GOOGLE_APPLICATION_CREDENTIALS"

# Activate virtual environment
source /home/crimson/Desktop/hello/open-webui/.venv/bin/activate

# Verify google-cloud-speech is installed
if ! python -c "import google.cloud.speech" 2>/dev/null; then
    echo "Installing google-cloud-speech..."
    pip install google-cloud-speech
fi

# Run scribe with environment variable explicitly set
exec python /home/crimson/Desktop/hello/open-webui/RedTool/scribe.py
