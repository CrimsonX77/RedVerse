# 🚀 Setup Guide for RedVerse

This guide will help you configure RedVerse for your system after cloning from GitHub.

## Quick Start

### 1. Initial Setup

```bash
# Clone the repository
git clone <your-repo-url>
cd Redverse

# Create Python virtual environment
pyenv virtualenv 3.10.16 redverse-env
# OR use venv:
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt
```

### 2. System Dependencies

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install ffmpeg python3-pyqt6 portaudio19-dev
```

**macOS:**
```bash
brew install ffmpeg portaudio
```

**Windows:**
- Download FFmpeg from https://ffmpeg.org/download.html
- Add FFmpeg to your PATH

### 3. Configure Paths

#### Option A: Using Environment Variables (Recommended)

```bash
# Copy the environment template
cp .env.example .env

# Edit .env with your actual paths
nano .env  # or use your preferred editor
```

Update these values in `.env`:
```bash
PYTHON_EXECUTABLE=/your/path/to/python
PROJECT_DIR=/your/path/to/Redverse
```

#### Option B: Edit Launch Scripts Directly

Edit each `.sh` file:

**dragon_forge.sh:**
```bash
#!/bin/bash
cd /YOUR/ACTUAL/PATH/TO/Redverse
/YOUR/ACTUAL/PYTHON/PATH edrive_heart_v2.py "$@"
```

**edrive.sh:**
```bash
#!/bin/bash
cd /YOUR/ACTUAL/PATH/TO/Redverse
/YOUR/ACTUAL/PYTHON/PATH edrive_heart_v2.py "$@"
```

**speaker.sh:**
```bash
#!/bin/bash
cd /YOUR/ACTUAL/PATH/TO/Redverse
/YOUR/ACTUAL/PYTHON/PATH speaker.py "$@"
```

Then make them executable:
```bash
chmod +x dragon_forge.sh edrive.sh speaker.sh
```

### 4. Optional: Desktop Integration (Linux)

```bash
# Edit dragon_forge.desktop
nano dragon_forge.desktop

# Update these lines with absolute paths:
# Exec=/YOUR/ACTUAL/PATH/TO/Redverse/dragon_forge.sh
# Icon=/YOUR/ACTUAL/PATH/TO/Redverse/dragon_forge_icon.svg

# Install desktop file
cp dragon_forge.desktop ~/.local/share/applications/
```

### 5. Setup Ollama (for E-Drive)

```bash
# Install Ollama from https://ollama.ai
curl https://ollama.ai/install.sh | sh

# Pull a model (example: llama2)
ollama pull CrimsonDragonX7/Oracle:latest

# Start Ollama service
ollama serve
```

### 6. Optional: Google Cloud Speech Setup (for Scribe)

1. Create a Google Cloud project at https://console.cloud.google.com
2. Enable the Speech-to-Text API
3. Create a service account and download credentials JSON
4. Save credentials and set environment variable:
   ```bash
   export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your/credentials.json"
   # Or add to .env file
   ```

## Testing Your Installation

### Test Web Interface
```bash
# Open in your default browser
xdg-open index_entrance.html  # Linux
open index_entrance.html       # macOS
start index_entrance.html      # Windows
```

### Test Python Tools

**Dragon Forge:**
```bash
python dragon_forge.py
# Should open a GUI window
```

**E-Drive:**
```bash
python edrive_heart_v2.py
# Should display the ring simulator
```

**Speaker:**
```bash
python speaker.py
# Should open TTS/STT interface
```

## Troubleshooting

### "Module not found" errors
```bash
# Make sure you're in the virtual environment
pip install -r requirements.txt
```

### "FFmpeg not found" error
```bash
# Test FFmpeg installation
ffmpeg -version

# If not installed, refer to System Dependencies section
```

### PyAudio installation fails
```bash
# Linux
sudo apt-get install portaudio19-dev python3-pyaudio

# macOS
brew install portaudio
pip install pyaudio

# Windows - download wheel from:
# https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio
```

### Ollama connection error
```bash
# Make sure Ollama is running
curl http://localhost:11434/api/tags

# If not running:
ollama serve
```

### Permission denied on .sh files
```bash
chmod +x *.sh
```

## Development Setup

### Creating Soul Configurations

1. Copy templates from `pads/` directory
2. Customize YAML files for your characters/scenarios
3. Load them in Soul Stacker or E-Drive

### Adding Custom Themes

1. Create new CSS file in `foundations/`
2. Reference in HTML files
3. Follow existing color variable patterns

### Working with Memory Bridge

Memory files are stored in `memory/` (auto-created).
- Session files: `session_*.jsonl`
- Trajectory data: `trajectory_*.json`

These are excluded from Git by default.

## Production Deployment

### As a Web Application

1. Set up a web server (nginx, Apache, or Node.js)
2. Serve HTML files from project root
3. Ensure `assets/` directory is accessible
4. Consider using a CDN for media files

### Python Tools as Services

Use systemd (Linux) or similar to run tools as background services:

```ini
[Unit]
Description=RedVerse E-Drive Service
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/path/to/Redverse
ExecStart=/path/to/python edrive_heart_v2.py
Restart=always

[Install]
WantedBy=multi-user.target
```

## Security Checklist

- [ ] Never commit `.env` file
- [ ] Keep credentials JSON files private
- [ ] Review `.gitignore` before pushing
- [ ] Use environment variables for sensitive data
- [ ] Ensure `Sables_Room/` is excluded
- [ ] Rotate API keys if accidentally committed

## Getting Help

- Check the main README.md
- Review configuration files in `ctx_rules/`
- Examine example YAML files in `pads/`
- Open an issue on GitHub

---

**Ready to enter The RedVerse? 🔴**
