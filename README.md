# 🔴 The RedVerse

**Canonical Crimson Chronicles — An Interactive Digital Experience**

The RedVerse is an immersive web-based platform combining theatrical HTML interfaces with powerful Python backend tools for AI interaction, media processing, and emotional simulation.

---

## 🌟 Features

### Web Interface
- **Church Entrance** (`index_entrance.html`) - Animated video door landing experience
- **Main RedVerse** (`redverse.html`) - Interactive cognitive map and canonical chronicles
- **Support Chapel** (`support.html`) - Patronage and support page (requires backend setup)

> **Note:** The support page uses Stripe for payments. The included key is a **test key only** for demonstration. To accept real payments, you need to:
> 1. Create a Stripe account at https://stripe.com
> 2. Replace the test key with your publishable key
> 3. Set up a backend server to handle `/create-payment-intent` endpoint
> 4. See Stripe documentation: https://stripe.com/docs/payments/accept-a-payment

### Python Tools

#### 🐉 Dragon Forge (`dragon_forge.py`)
Media converter with PyQt6 GUI for images, audio, and video format conversion.

#### 💓 E-Drive Ring Simulator (`edrive_heart_v2.py`)
Advanced emotional simulation system with:
- Three-ring architecture (Inner/Middle/Outer)
- Real-time emotion visualization
- Ollama AI integration
- Enhanced prompt engineering with emotional context

#### 🧠 Memory Bridge (`memory_bridge.py`)
Relational context and session persistence system tracking:
- Conversation events
- Emotional trajectories
- Relational patterns
- Meta-aware context

#### 🎭 Soul Stacker (`soulstacker.py`)
YAML-based personality configuration stacking and crystallization tool.

#### 🗣️ Speaker (`speaker.py`)
Text-to-speech and speech-to-text interface with multiple TTS engines.

#### ✍️ Scribe (`scribe.py`)
Advanced transcription and voice recognition tool with Google Cloud Speech support.

---

## 📋 Requirements

### System Dependencies
- Python 3.10+ (tested with 3.10.16)
- FFmpeg (for media conversion)
- PyQt6
- Ollama (for AI generation)

### Python Packages
```bash
pip install -r requirements.txt
```

**Core Dependencies:**
- PyQt6
- Pillow
- edge-tts
- pyaudio
- pygame
- openai
- whisper
- SpeechRecognition
- numpy
- requests
- ollama
- ffmpeg-python
- mss

---

## 🚀 Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd Redverse
   ```

2. **Set up Python environment**
   ```bash
   pyenv virtualenv 3.10.16 redverse-env
   pyenv activate redverse-env
   pip install -r requirements.txt
   ```

3. **Install FFmpeg**
   ```bash
   # Ubuntu/Debian
   sudo apt install ffmpeg
   
   # macOS
   brew install ffmpeg
   ```

4. **Configure paths** (Optional)
   - Edit `.sh` script files to match your installation directory
   - Update `dragon_forge.desktop` if using desktop integration

5. **Set up Google Cloud credentials** (Optional, for Scribe)
   - Place your `scribe-*.json` credentials file in the project directory
   - Or set `GOOGLE_APPLICATION_CREDENTIALS` environment variable

---

## 💻 Usage

### Web Interface
Open in a web browser:
```bash
# Start with the entrance
open index_entrance.html

# Or go directly to the main page
open redverse.html
```

### Python Tools

**Dragon Forge (Media Converter)**
```bash
python dragon_forge.py
# Or use the shell script:
./dragon_forge.sh
```

**E-Drive Ring Simulator**
```bash
python edrive_heart_v2.py
# Or:
./edrive.sh
```

**Speaker (TTS/STT)**
```bash
python speaker.py
# Or:
./speaker.sh
```

**Soul Stacker**
```bash
python soulstacker.py
```

**Scribe (Transcription)**
```bash
python scribe.py
```

---

## 📁 Project Structure

```
Redverse/
├── index_entrance.html      # Landing page with video doors
├── redverse.html            # Main interactive interface
├── support.html             # Support/patronage page
├── dragon_forge.py          # Media converter tool
├── edrive_heart_v2.py       # Emotional simulation system
├── memory_bridge.py         # Context persistence
├── soulstacker.py           # Personality configuration
├── speaker.py               # TTS/STT interface
├── scribe.py               # Transcription tool
├── requirements.txt         # Python dependencies
├── assets/                  # Media files (videos, audio, images)
├── ctx_rules/              # Context and instruction rules
├── foundations/            # Theme and styling components
├── pads/                   # YAML configuration pads
├── SoulDrafts/            # Soul configuration drafts
└── upgrades/              # System upgrades and extensions
```

---

## ⚙️ Configuration

### Soul System (YAML Pads)
The `pads/` directory contains YAML configuration files for:
- **Characters** (`character_*.yaml`)
- **Locations** (`location_*.yaml`)
- **Scenarios** (`scenario_*.yaml`)
- **Transitions** (`transition_*.yaml`)

### Context Rules
The `ctx_rules/` directory defines:
- Instruction sets
- Stacker rules
- Required prompt appends
- Transition logic

---

## 🎨 Theming

The RedVerse uses a custom **Crimson Cathedral** theme with:
- **Primary**: Crimson red (`#c41230`)
- **Secondary**: Gold (`#d4a846`)
- **Accent**: Silver (`#b8c0cc`)
- **Typography**: Cinzel (display), Crimson Pro (body), JetBrains Mono (code)

Theme files located in `foundations/`

---

## 🔒 Security Notes

- Never commit credential files (`.json` keys)
- Use environment variables for API keys
- The `Sables_Room/` directory is excluded from version control
- Review `.gitignore` before committing

---

## 🛠️ Development

### Path Configuration
The `.sh` launcher scripts contain hardcoded paths. Update these for your system:

```bash
# In dragon_forge.sh, edrive.sh, speaker.sh
cd /path/to/your/Redverse
/path/to/your/python edrive_heart_v2.py "$@"
```

### Desktop Integration (Linux)
```bash
# Copy and edit dragon_forge.desktop
cp dragon_forge.desktop ~/.local/share/applications/
# Update Exec and Icon paths to absolute paths
```

---

## 📝 License

[Add your license here]

---

## 💖 Support

Visit the Support Chapel (`support.html`) or contribute to the development of The RedVerse.

---

## 🤝 Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Open a Pull Request

---

**Built with ❤️ in the Crimson Cathedral**
