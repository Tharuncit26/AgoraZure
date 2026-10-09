import os
from pathlib import Path
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse

from backend.config import APP_NAME, API_PREFIX, BASE_DIR
from backend.database import engine, Base
from backend.routes.auth import router as auth_router
from backend.routes.stock import router as stock_router
from backend.routes.billing import router as billing_router
from backend.routes.alerts import router as alerts_router
from backend.routes.insights import router as insights_router
from backend.routes.orders import router as orders_router
from backend.routes.shopper import router as shopper_router
from backend.routes.delivery import router as delivery_router
from backend.routes.loyalty_offers import router as loyalty_offers_router

from backend.database import engine, Base, ensure_schema_migrations

# Ensure all database tables exist
Base.metadata.create_all(bind=engine)
try:
    ensure_schema_migrations(engine)
except Exception:
    pass

# Auto-seed if hosted database is freshly provisioned
try:
    from seed import seed_if_empty
    seed_if_empty()
except Exception:
    pass

app = FastAPI(
    title=APP_NAME,
    description="Smart Commerce Platform connecting local shops & shoppers (Zéphyr 2026 AI Hackathon - PS-2)",
    version="1.0.0"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include all API routers
app.include_router(auth_router, prefix=API_PREFIX)
app.include_router(stock_router, prefix=API_PREFIX)
app.include_router(billing_router, prefix=API_PREFIX)
app.include_router(alerts_router, prefix=API_PREFIX)
app.include_router(insights_router, prefix=API_PREFIX)
app.include_router(orders_router, prefix=API_PREFIX)
app.include_router(shopper_router, prefix=API_PREFIX)
app.include_router(delivery_router, prefix=API_PREFIX)
app.include_router(loyalty_offers_router, prefix=API_PREFIX)

# Frontend directories
FRONTEND_DIR = BASE_DIR / "frontend"

if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
    app.mount("/css", StaticFiles(directory=str(FRONTEND_DIR / "css")), name="css")
    app.mount("/js", StaticFiles(directory=str(FRONTEND_DIR / "js")), name="js")
    if (FRONTEND_DIR / "images").exists():
        app.mount("/images", StaticFiles(directory=str(FRONTEND_DIR / "images")), name="images")

@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "app": APP_NAME,
        "database": "SQLite",
        "hackathon": "Zéphyr 2026 - PS-2 Smart Commerce"
    }

# Top-level Web Page Routes
@app.get("/", response_class=FileResponse)
def get_index():
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return HTMLResponse("<h1>AgoraZure Backend Running</h1><p>Frontend files initializing...</p>")

@app.get("/shopper", response_class=FileResponse)
@app.get("/shopper.html", response_class=FileResponse)
def get_shopper_page():
    page = FRONTEND_DIR / "shopper.html"
    return FileResponse(page)

@app.get("/shopkeeper", response_class=FileResponse)
@app.get("/shopkeeper.html", response_class=FileResponse)
def get_shopkeeper_page():
    page = FRONTEND_DIR / "shopkeeper.html"
    return FileResponse(page)

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    reload = os.environ.get("ENV", "production") == "development"
    uvicorn.run("backend.main:app", host=host, port=port, reload=reload)
