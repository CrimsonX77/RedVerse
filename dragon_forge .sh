#!/bin/bash

# Dragon Forge Launcher
# Navigate to the application directory and launch Dragon Forge

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Change to the application directory
cd "$SCRIPT_DIR" || exit 1

# Set Python environment (adjust if needed)
export PATH="$HOME/.pyenv/shims:$PATH"
eval "$(pyenv init -)"
pyenv shell 3.10.16

# Launch Dragon Forge
python3 dragon_forge.py
