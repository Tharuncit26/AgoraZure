from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from backend.config import DATABASE_URL

import os
import shutil
from pathlib import Path
from backend.config import BASE_DIR

# Normalize postgres:// to postgresql:// for cloud compatibility (Render/Heroku/Railway)
db_url = DATABASE_URL

# In serverless environments (Vercel / AWS Lambda), the deployment directory is read-only.
# Copy SQLite database to /tmp so write operations succeed seamlessly.
if (os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME")) and db_url.startswith("sqlite"):
    tmp_db = Path("/tmp/agorazure.db")
    if not tmp_db.exists():
        src_db = BASE_DIR / "agorazure.db"
        if src_db.exists():
            shutil.copy2(src_db, tmp_db)
    db_url = f"sqlite:///{tmp_db}"

if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+pg8000://", 1)
elif db_url.startswith("postgresql://") and "+pg8000" not in db_url and "+psycopg2" not in db_url:
    db_url = db_url.replace("postgresql://", "postgresql+pg8000://", 1)

# SQLAlchemy database engine
connect_args = {"check_same_thread": False} if "sqlite" in db_url else {}

engine = create_engine(
    db_url,
    connect_args=connect_args,
    pool_pre_ping=True,
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """Dependency that yields a database session and closes it cleanly."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
