# Google Auth Test Commands

# 1. Start the server
source venv/bin/activate && python app.py

# 2. Test health endpoint
curl http://localhost:8800/health

# 3. Test auth status
curl http://localhost:8800/auth/status
