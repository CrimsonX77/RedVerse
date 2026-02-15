# Installer Detection Feature

## Overview

The RedVerse installer scripts (`setup_redverse.sh` and `setup_redverse.ps1`) now include comprehensive component detection that runs before any installation steps. This ensures a faster, more efficient setup experience by:

1. **Detecting existing components** on the system and in the repository
2. **Skipping unnecessary installations** when components are already present
3. **Automatically updating** RedVerse if it's already installed
4. **Providing immediate feedback** about what's installed and what's missing

## How It Works

### Detection Phase

When you run the installer, it performs a thorough scan for:

#### 1. **Ollama** (AI Engine)
- Checks if `ollama` command is available system-wide
- Verifies it can be executed

#### 2. **Oracle Model** (AI Model)
- If Ollama is found, checks if `CrimsonDragonX7/Oracle` model is pulled
- Uses `ollama list` to verify model availability

#### 3. **Python 3.10+** (Runtime)
- Searches for `python3` and `python` commands
- Extracts version using portable `sed` command (macOS/Linux compatible)
- Validates version is 3.10 or higher using correct logic:
  - Python 3.10+ ✓
  - Python 4.0+ ✓
  - Python 3.9 ✗

#### 4. **Python Packages** (Dependencies)
- Checks for required packages with correct import names:
  - `edge-tts` → imports as `edge_tts`
  - `SpeechRecognition` → imports as `speech_recognition`
  - `PyQt6` → imports as `PyQt6`
  - `Pillow` → imports as `PIL`
  - `flask` → imports as `flask`
  - `ollama` → imports as `ollama`

#### 5. **ffmpeg** (Media Processing)
- Checks if `ffmpeg` command is available
- Required for audio/video processing features

#### 6. **RedVerse Repository** (Application)
- Checks both:
  - Script directory (if running from cloned repo)
  - Standard install location (`~/RedVerse` or `%USERPROFILE%\RedVerse`)
- Validates presence of `.git` directory and `serve_edrive.py`

### Smart Installation Flow

#### Scenario 1: All Components Found ✓
```
═══════════════════════════════════════════════════
    ✓ All components already installed!
═══════════════════════════════════════════════════

System is ready to use!

Checking for RedVerse updates...
✓ RedVerse is already up to date

To start the RedVerse backend:
  cd ~/RedVerse
  python3 serve_edrive.py

Start the RedVerse server now? [Y/n]
```

**What happens:**
- Shows success message
- Checks for and pulls any RedVerse updates
- Offers to start the server immediately
- **Exits without running any installation steps**

#### Scenario 2: Some Components Missing ⚠
```
Detection Summary:
  ✗ Ollama needs installation
  ✗ Python packages need installation
  ✗ ffmpeg needs installation

Proceeding with installation of missing components...
```

**What happens:**
- Shows which components need installation
- Proceeds with installing **only** the missing components
- Skips components that are already installed
- Each step checks flags and skips if not needed

#### Scenario 3: Fresh Installation 🆕
```
Detection Summary:
  ✗ Ollama needs installation
  ✗ Oracle model needs to be pulled
  ✗ Python 3.10+ needs installation
  ✗ Python packages need installation
  ✗ ffmpeg needs installation
  ✗ RedVerse repository needs cloning

Proceeding with installation of missing components...
```

**What happens:**
- Full installation of all components
- Downloads and installs everything needed
- Clones RedVerse repository
- Sets up everything for first use

## Technical Details

### Cross-Platform Compatibility

#### Linux/macOS (Bash)
- Uses portable `sed` instead of `grep -P` for regex (BSD grep compatible)
- Handles both `apt`, `dnf`, and `pacman` package managers on Linux
- Uses Homebrew on macOS
- Properly handles symlinks and directory detection

#### Windows (PowerShell)
- Uses PowerShell-native regex matching
- Leverages `winget` for package installation
- Handles Windows PATH refresh after installations
- Uses proper PowerShell error handling

### Version Detection Logic

Both scripts use mathematically correct version comparison:

```bash
# Correct logic (implemented)
if [[ $major -gt 3 || ($major -eq 3 && $minor -ge 10) ]]

# What this accepts:
# - Python 3.10 ✓
# - Python 3.11 ✓
# - Python 3.12+ ✓
# - Python 4.0+ ✓

# What this rejects:
# - Python 3.9 ✗
# - Python 2.7 ✗
```

### Repository Detection

The installer checks multiple locations in priority order:

1. **Script directory** (`$(dirname "$0")/..`)
   - If running from `installers/` in a cloned repo
   - Allows testing and development without moving files

2. **Standard install location** (`~/RedVerse` or `%USERPROFILE%\RedVerse`)
   - Default installation path
   - Where the installer clones to if not found

### Update Detection

When RedVerse is already installed, the installer:

```bash
git fetch origin main
LOCAL=$(git rev-parse @)
REMOTE=$(git rev-parse @{u})

if [ "$LOCAL" != "$REMOTE" ]; then
  git pull origin main
fi
```

This safely:
- Fetches latest changes without modifying working directory
- Compares local and remote commits
- Only pulls if there's an update
- Preserves local modifications if any

## Benefits

### For Users
- **Faster re-runs**: No waiting for unnecessary downloads/installations
- **Clear feedback**: Know exactly what's installed and what's missing
- **Automatic updates**: Get latest RedVerse version automatically
- **Better reliability**: Reduced chance of conflicts or duplicate installations

### For Developers
- **Easier testing**: Run installer multiple times without issues
- **Better debugging**: Clear detection output helps diagnose problems
- **Flexible workflows**: Works from repo directory or standard location

## Usage Examples

### First-Time Installation
```bash
# Linux/macOS
curl -fsSL https://raw.githubusercontent.com/CrimsonX77/RedVerse/main/installers/setup_redverse.sh | bash

# Or download and run
bash installers/setup_redverse.sh
```

```powershell
# Windows
irm https://raw.githubusercontent.com/CrimsonX77/RedVerse/main/installers/setup_redverse.ps1 | iex

# Or download and run
.\installers\setup_redverse.ps1
```

### Update Existing Installation
Simply run the installer again - it will detect everything is installed and offer to update:

```bash
bash installers/setup_redverse.sh
# Output: ✓ All components already installed!
# Checking for RedVerse updates...
```

### Verify Installation
Run the installer to see what's installed:

```bash
bash installers/setup_redverse.sh
# Shows detection results for all components
```

## Troubleshooting

### "Python version check failed"
- Ensure Python 3.10 or higher is installed
- Try: `python3 --version`

### "RedVerse repository not found"
- The installer will clone it automatically
- Or manually clone: `git clone https://github.com/CrimsonX77/RedVerse.git`

### "Ollama not found"
- The installer will install it automatically
- Or manually install from: https://ollama.com

### Detection shows wrong results
- Run with verbose output to see detection details
- Check permissions (installer needs execute permissions)
- Ensure commands are in PATH

## Contributing

When modifying the installer:

1. **Test both scripts** (Bash and PowerShell)
2. **Test all scenarios**:
   - Fresh installation
   - Partial installation
   - Full installation
   - Update-only mode
3. **Maintain cross-platform compatibility**
4. **Update this documentation**

## Future Enhancements

Potential improvements for the detection system:

- [ ] Detect and handle virtual environments
- [ ] Check for specific Python package versions
- [ ] Detect GPU availability for SD setup
- [ ] Parallel component checking for faster detection
- [ ] Interactive component selection (choose what to install)
- [ ] Export detection results to JSON for automation
- [ ] Integration with CI/CD systems
