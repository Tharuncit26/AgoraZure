import os
from pathlib import Path
from dotenv import load_dotenv

# Base directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env if present
load_dotenv(BASE_DIR / ".env")

# Database URL (SQLite now, easy to switch to PostgreSQL via connection string)
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR}/agorazure.db")

# Azure OpenAI settings
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "").strip()
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY", "").strip()
AZURE_OPENAI_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o-mini").strip()
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview").strip()

# App settings
APP_NAME = "AgoraZure"
API_PREFIX = "/api"
SECRET_KEY = os.getenv("SECRET_KEY", "agorazure-zephyr-2026-secret-key-ps2")
