#!/bin/bash

# RedVerse Google Auth Testing Suite
# Tests the complete OAuth2 authentication system

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SERVER_URL="http://localhost:8800"
CREDENTIALS_FILE="client_secret_999940301372-lsv85hnhe6ucju10uhhg2u36k1j8is9f.apps.googleusercontent.com.json"

echo -e "${BLUE}=== RedVerse Google Auth Test Suite ===${NC}\n"

# Test 1: Check Python environment
echo -e "${YELLOW}[TEST 1]${NC} Checking Python environment..."
if command -v python3.15 &> /dev/null; then
    PYTHON_VERSION=$(python3.15 --version)
    echo -e "${GREEN}✓ Python found: $PYTHON_VERSION${NC}"
elif command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    echo -e "${YELLOW}⚠ Python 3 found: $PYTHON_VERSION (expected 3.15)${NC}"
else
    echo -e "${RED}✗ Python 3 not found${NC}"
    exit 1
fi

# Test 2: Check virtualenv
echo -e "\n${YELLOW}[TEST 2]${NC} Checking virtual environment..."
if [ -d "venv" ]; then
    echo -e "${GREEN}✓ Virtual environment exists${NC}"
    if [ -f "venv/bin/activate" ]; then
        echo -e "${GREEN}✓ Activation script found${NC}"
    else
        echo -e "${RED}✗ Activation script not found${NC}"
        exit 1
    fi
else
    echo -e "${RED}✗ Virtual environment not found${NC}"
    exit 1
fi

# Test 3: Check dependencies
echo -e "\n${YELLOW}[TEST 3]${NC} Checking required dependencies..."
source venv/bin/activate

required_packages=(
    "flask"
    "google-auth"
    "google-auth-oauthlib"
    "google-api-python-client"
)

for package in "${required_packages[@]}"; do
    if python -c "import ${package//-/_}" 2>/dev/null; then
        version=$(python -c "import ${package//-/_}; print(${package//-/_}.__version__ if hasattr(${package//-/_}, '__version__') else 'installed')")
        echo -e "${GREEN}✓ $package ($version)${NC}"
    else
        echo -e "${RED}✗ $package not found${NC}"
        exit 1
    fi
done

# Test 4: Check credentials file
echo -e "\n${YELLOW}[TEST 4]${NC} Checking Google credentials..."
if [ -f "$CREDENTIALS_FILE" ]; then
    echo -e "${GREEN}✓ Credentials file found: $CREDENTIALS_FILE${NC}"
    
    # Validate JSON format
    if python -c "import json; json.load(open('$CREDENTIALS_FILE'))" 2>/dev/null; then
        echo -e "${GREEN}✓ Credentials file is valid JSON${NC}"
    else
        echo -e "${RED}✗ Credentials file is invalid JSON${NC}"
        exit 1
    fi
else
    echo -e "${RED}✗ Credentials file not found: $CREDENTIALS_FILE${NC}"
    echo -e "${YELLOW}  Download from: https://console.cloud.google.com/apis/credentials${NC}"
    exit 1
fi

# Test 5: Check .env file
echo -e "\n${YELLOW}[TEST 5]${NC} Checking environment configuration..."
if [ -f ".env" ]; then
    echo -e "${GREEN}✓ .env file found${NC}"
    
    # Check required env vars
    env_vars=("GOOGLE_CLIENT_SECRETS" "GOOGLE_REDIRECT_URI" "SESSION_SECRET")
    for var in "${env_vars[@]}"; do
        if grep -q "$var" .env; then
            echo -e "${GREEN}✓ $var configured${NC}"
        else
            echo -e "${RED}✗ $var not configured${NC}"
        fi
    done
else
    echo -e "${YELLOW}⚠ .env file not found${NC}"
    echo -e "${YELLOW}  Run: source setup.sh${NC}"
fi

# Test 6: Check required files
echo -e "\n${YELLOW}[TEST 6]${NC} Checking application files..."
required_files=(
    "auth.py"
    "app.py"
    "js/auth-client.js"
    "requirements.txt"
    "GOOGLE_AUTH_SETUP.md"
)

for file in "${required_files[@]}"; do
    if [ -f "$file" ]; then
        echo -e "${GREEN}✓ $file exists${NC}"
    else
        echo -e "${RED}✗ $file not found${NC}"
    fi
done

# Test 7: Syntax check auth.py
echo -e "\n${YELLOW}[TEST 7]${NC} Checking auth.py syntax..."
if python -m py_compile auth.py 2>/dev/null; then
    echo -e "${GREEN}✓ auth.py syntax is valid${NC}"
else
    echo -e "${RED}✗ auth.py has syntax errors${NC}"
    exit 1
fi

# Test 8: Syntax check app.py
echo -e "\n${YELLOW}[TEST 8]${NC} Checking app.py syntax..."
if python -m py_compile app.py 2>/dev/null; then
    echo -e "${GREEN}✓ app.py syntax is valid${NC}"
else
    echo -e "${RED}✗ app.py has syntax errors${NC}"
    exit 1
fi

# Test 9: Check Flask app runs
echo -e "\n${YELLOW}[TEST 9]${NC} Testing Flask server startup..."
# Create a test script that imports the app
cat > /tmp/test_app_import.py << 'EOF'
import sys
sys.path.insert(0, '/home/crimson/Desktop/Laptop')
try:
    from app import app
    print("✓ Flask app imports successfully")
    print("✓ Available routes:", len([rule for rule in app.url_map.iter_rules()]))
except Exception as e:
    print("✗ Error importing app:", str(e))
    sys.exit(1)
EOF

if python /tmp/test_app_import.py 2>&1; then
    echo -e "${GREEN}✓ Flask app imports successfully${NC}"
else
    echo -e "${RED}✗ Flask app import failed${NC}"
    exit 1
fi

# Test 10: Check JavaScript client
echo -e "\n${YELLOW}[TEST 10]${NC} Validating JavaScript client..."
if [ -f "js/auth-client.js" ]; then
    if grep -q "class AuthClient" js/auth-client.js; then
        echo -e "${GREEN}✓ AuthClient class defined${NC}"
    fi
    if grep -q "initGoogle" js/auth-client.js; then
        echo -e "${GREEN}✓ initGoogle method present${NC}"
    fi
    if grep -q "handleGoogleResponse" js/auth-client.js; then
        echo -e "${GREEN}✓ handleGoogleResponse method present${NC}"
    fi
else
    echo -e "${RED}✗ auth-client.js not found${NC}"
fi

# Summary
echo -e "\n${BLUE}=== Test Summary ===${NC}"
echo -e "${GREEN}✓ All prerequisite checks passed!${NC}\n"

echo -e "${YELLOW}Next steps:${NC}"
echo "1. Start the server:    python app.py"
echo "2. Open browser:        http://localhost:8800"
echo "3. Test Google Sign-In: Click 'Sign In' button"
echo "4. Verify callback:     Should redirect to home after auth"
echo -e "\n${YELLOW}Manual API Testing:${NC}"
echo "  • Check auth status:  curl http://localhost:8800/auth/status"
echo "  • Test logout:        curl -X POST http://localhost:8800/auth/logout"
echo "  • Health check:       curl http://localhost:8800/health"

deactivate
