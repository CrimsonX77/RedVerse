#!/bin/bash

# RedVerse Authentication - Complete Setup Script
# This is the master setup script - run this ONCE to configure everything

set -e

PROJECT_ROOT="/home/crimson/Desktop/Laptop"
cd "$PROJECT_ROOT"

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Title
clear
cat << "EOF"
╔══════════════════════════════════════════════════════════║
║                                                          ║
║  🔐 RedVerse Google OAuth2 Authentication Setup         ║
║                                                          ║
║  This script will:                                      ║
║  1. Verify your environment                            ║
║  2. Install all dependencies                           ║
║  3. Create configuration files                         ║
║  4. Perform pre-launch checks                          ║
║                                                          ║
║  Time required: ~5 minutes                             ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝

EOF

# Step counters
STEP=1
success_count=0
fail_count=0

print_header() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}[STEP $STEP] $1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    STEP=$((STEP + 1))
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
    ((success_count++))
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
    ((fail_count++))
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${CYAN}ℹ $1${NC}"
}

# ============================================================================
# Step 1: Check permissions
# ============================================================================

print_header "Checking permissions and environment"

if [ ! -w "$PROJECT_ROOT" ]; then
    print_error "No write permission in $PROJECT_ROOT"
    exit 1
fi

print_success "Write permission verified"

if [ ! "$(pwd)" = "$PROJECT_ROOT" ]; then
    print_error "Not in project directory: $PROJECT_ROOT"
    exit 1
fi

print_success "Working directory is correct"

# ============================================================================
# Step 2: Check Python
# ============================================================================

print_header "Verifying Python installation"

if command -v python3.15 &> /dev/null; then
    PYTHON_CMD="python3.15"
    VERSION=$($PYTHON_CMD --version 2>&1 | cut -d' ' -f2)
    print_success "Python $VERSION found (python3.15)"
elif command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
    VERSION=$($PYTHON_CMD --version 2>&1 | cut -d' ' -f2)
    print_warning "Using python3 ($VERSION) instead of python3.15"
else
    print_error "Python 3 not found. Please install Python 3.15 or higher."
    exit 1
fi

# ============================================================================
# Step 3: Check/Create virtual environment
# ============================================================================

print_header "Setting up virtual environment"

if [ ! -d "venv" ]; then
    print_info "Creating virtual environment..."
    $PYTHON_CMD -m venv venv
    print_success "Virtual environment created"
else
    print_success "Virtual environment already exists"
fi

# Activate venv
source venv/bin/activate
print_success "Virtual environment activated"

# ============================================================================
# Step 4: Check dependencies
# ============================================================================

print_header "Verifying dependencies"

if [ ! -f "requirements.txt" ]; then
    print_error "requirements.txt not found"
    exit 1
fi

print_success "requirements.txt found"

# Install/update dependencies
print_info "Installing dependencies..."
pip install -q --upgrade pip setuptools wheel

# Core packages only (skip numpy which has issues with Python 3.15)
CORE_PACKAGES=(
    "Flask==3.1.3"
    "flask-cors==6.0.2"
    "Flask-Session==0.8.0"
    "google-auth==2.49.2"
    "google-auth-oauthlib==1.3.1"
    "google-auth-httplib2==0.3.1"
    "google-api-python-client==2.194.0"
    "requests==2.32.3"
    "python-dotenv==1.0.1"
)

for package in "${CORE_PACKAGES[@]}"; do
    pip install -q "$package"
done

print_success "Core dependencies installed"

# Verify critical packages
for pkg in flask google-auth requests; do
    if $PYTHON_CMD -c "import ${pkg//-/_}" 2>/dev/null; then
        print_success "Verified: $pkg"
    else
        print_error "Failed to install: $pkg"
        exit 1
    fi
done

# ============================================================================
# Step 5: Check credentials file
# ============================================================================

print_header "Checking Google OAuth credentials"

CREDENTIALS_FILE="client_secret_999940301372-lsv85hnhe6ucju10uhhg2u36k1j8is9f.apps.googleusercontent.com.json"

if [ -f "$CREDENTIALS_FILE" ]; then
    print_success "Credentials file found: $CREDENTIALS_FILE"
    
    # Validate JSON
    if $PYTHON_CMD -c "import json; json.load(open('$CREDENTIALS_FILE'))" 2>/dev/null; then
        print_success "Credentials file is valid JSON"
    else
        print_error "Credentials file is not valid JSON"
        print_info "Delete the file and re-download from Google Cloud Console"
        exit 1
    fi
else
    print_warning "Credentials file not found: $CREDENTIALS_FILE"
    echo ""
    echo -e "${YELLOW}ACTION REQUIRED:${NC}"
    echo "1. Go to: https://console.cloud.google.com/apis/credentials"
    echo "2. Click: '+ Create Credentials' → 'OAuth 2.0 Client ID'"
    echo "3. Select: 'Web application'"
    echo "4. Add Authorized redirect URIs:"
    echo "   - http://localhost:8800/auth/google/callback"
    echo "   - http://127.0.0.1:8800/auth/google/callback"
    echo "5. Download JSON file"
    echo "6. Save as: $CREDENTIALS_FILE"
    echo "7. Run this script again"
    echo ""
fi

# ============================================================================
# Step 6: Create .env file
# ============================================================================

print_header "Configuring environment variables"

ENV_FILE=".env"

if [ -f "$ENV_FILE" ]; then
    print_warning ".env file already exists"
    print_info "Skipping .env creation (existing config preserved)"
else
    cat > "$ENV_FILE" << 'ENVFILE'
# Google OAuth Configuration
GOOGLE_CLIENT_SECRETS=/home/crimson/Desktop/Laptop/client_secret_999940301372-lsv85hnhe6ucju10uhhg2u36k1j8is9f.apps.googleusercontent.com.json
GOOGLE_REDIRECT_URI=http://localhost:8800/auth/google/callback

# Session Configuration  
SESSION_SECRET=dev-session-secret-please-change-in-production

# Server Configuration
PORT=8800
FLASK_ENV=development
FLASK_DEBUG=1
ENVFILE

    print_success "Created .env file"
fi

# ============================================================================
# Step 7: Verify application files
# ============================================================================

print_header "Verifying application files"

REQUIRED_FILES=(
    "auth.py"
    "app.py"
    "js/auth-client.js"
    "GOOGLE_AUTH_SETUP.md"
    "requirements.txt"
)

ALL_FILES_EXIST=true

for file in "${REQUIRED_FILES[@]}"; do
    if [ -f "$file" ]; then
        print_success "$file"
    else
        print_error "$file is missing"
        ALL_FILES_EXIST=false
    fi
done

if [ "$ALL_FILES_EXIST" = false ]; then
    print_error "Some required files are missing"
    exit 1
fi

# ============================================================================
# Step 8: Syntax validation
# ============================================================================

print_header "Validating Python syntax"

$PYTHON_CMD -m py_compile auth.py 2>/dev/null
print_success "auth.py syntax valid"

$PYTHON_CMD -m py_compile app.py 2>/dev/null
print_success "app.py syntax valid"

# ============================================================================
# Step 9: Import tests
# ============================================================================

print_header "Testing module imports"

if $PYTHON_CMD -c "from auth import *" 2>/dev/null; then
    print_success "auth.py imports successfully"
else
    print_error "auth.py import failed"
    exit 1
fi

if $PYTHON_CMD -c "from app import app" 2>/dev/null; then
    print_success "app.py imports successfully"
else
    print_error "app.py import failed"
    exit 1
fi

# ============================================================================
# Step 10: Summary and next steps
# ============================================================================

print_header "Setup complete!"

echo ""
echo -e "${GREEN}✓ Environment successfully configured${NC}"
echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

echo -e "${YELLOW}📋 NEXT STEPS:${NC}"
echo ""
echo "1. Verify credentials file exists:"
echo -e "   ${CYAN}ls -l $CREDENTIALS_FILE${NC}"
echo ""
echo "2. Start the server:"
echo -e "   ${CYAN}python app.py${NC}"
echo ""
echo "3. Open browser:"
echo -e "   ${CYAN}http://localhost:8800${NC}"
echo ""
echo "4. Test Google Sign-In:"
echo "   - Click 'Sign In' button"
echo "   - Authenticate with Google"
echo "   - Verify redirect back to home page"
echo ""

echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

echo -e "${YELLOW}📚 DOCUMENTATION:${NC}"
echo ""
echo "Setup Guide:"
echo -e "  ${CYAN}cat GOOGLE_AUTH_SETUP.md${NC}"
echo ""
echo "Integration Examples:"
echo -e "  ${CYAN}cat INTEGRATION_EXAMPLES.md${NC}"
echo ""
echo "API Reference:"
echo -e "  ${CYAN}cat API_REFERENCE.md${NC}"
echo ""
echo "Troubleshooting:"
echo -e "  ${CYAN}cat TROUBLESHOOTING.md${NC}"
echo ""

echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

echo -e "${GREEN}Setup status: SUCCESS${NC}"
echo "Timestamp: $(date)"
echo ""

deactivate
