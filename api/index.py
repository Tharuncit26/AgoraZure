import sys
from pathlib import Path

# Add project root to Python module search path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.main import app

# Normalization middleware for Vercel serverless functions
@app.middleware("http")
async def normalize_vercel_api_path(request, call_next):
    scope = request.scope
    path = scope.get("path", "")
    if not path.startswith("/api") and not path.startswith("/docs") and not path.startswith("/openapi.json"):
        scope["path"] = "/api" + path
    return await call_next(request)
