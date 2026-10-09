import os
import shutil
import logging
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker
from backend.config import DATABASE_URL, BASE_DIR

logger = logging.getLogger(__name__)

# Normalize postgres URL for SQLAlchemy
db_url = os.environ.get("DATABASE_URL", DATABASE_URL)

# In serverless environments (Vercel / AWS Lambda), if SQLite is specified, fallback to /tmp
if (os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME")) and db_url.startswith("sqlite"):
    tmp_db = Path("/tmp/agorazure.db")
    if not tmp_db.exists():
        src_db = BASE_DIR / "agorazure.db"
        if src_db.exists():
            try:
                shutil.copy2(src_db, tmp_db)
            except Exception:
                pass
    db_url = f"sqlite:///{tmp_db}"

connect_args = {}
if "sqlite" in db_url:
    connect_args = {"check_same_thread": False}
else:
    # Cloud PostgreSQL (Supabase / Neon / Render / AWS)
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql+pg8000://", 1)
    elif db_url.startswith("postgresql://") and "+pg8000" not in db_url and "+psycopg2" not in db_url:
        # Default to pg8000 for pure-python cross-platform serverless reliability
        db_url = db_url.replace("postgresql://", "postgresql+pg8000://", 1)

engine = create_engine(
    db_url,
    connect_args=connect_args,
    pool_pre_ping=True,
    pool_recycle=300,
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def ensure_schema_migrations(conn_engine):
    """
    Safely adds newly introduced columns to existing database tables if they do not exist yet.
    Ensures zero disruption on local SQLite or cloud PostgreSQL (Supabase).
    """
    migrations = [
        # Table, Column, Type
        ("shops", "email", "VARCHAR(120)"),
        ("shops", "category", "VARCHAR(100) DEFAULT 'Grocery & Supermarket'"),
        ("shops", "opening_hours", "VARCHAR(100) DEFAULT '7:00 AM - 10:00 PM'"),
        ("shops", "photo_url", "TEXT"),
        ("shops", "is_open", "BOOLEAN DEFAULT TRUE"),
        ("shopkeepers", "email", "VARCHAR(120)"),
        ("shoppers", "email", "VARCHAR(120)"),
        ("products", "brand", "VARCHAR(100) DEFAULT 'General'"),
        ("products", "description", "TEXT"),
        ("products", "mrp", "FLOAT"),
        ("products", "unit", "VARCHAR(50) DEFAULT '1 pc'"),
        ("products", "image_url", "TEXT"),
        ("products", "is_available", "BOOLEAN DEFAULT TRUE"),
        ("orders", "delivery_address", "VARCHAR(255)"),
        ("orders", "payment_method", "VARCHAR(50) DEFAULT 'Cash on Delivery'"),
        ("orders", "payment_status", "VARCHAR(50) DEFAULT 'pending'"),
        ("orders", "subtotal", "FLOAT DEFAULT 0.0"),
        ("orders", "delivery_fee", "FLOAT DEFAULT 0.0"),
        ("orders", "tax_amount", "FLOAT DEFAULT 0.0"),
        ("orders", "discount_amount", "FLOAT DEFAULT 0.0"),
        ("orders", "reject_reason", "VARCHAR(255)"),
        ("orders", "updated_at", "TIMESTAMP"),
        ("offers", "banner_text", "VARCHAR(255)"),
    ]

    with conn_engine.connect() as conn:
        for table, col, col_type in migrations:
            try:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"))
                conn.commit()
            except Exception:
                # Column already exists or table not yet created
                pass

def get_db():
    """Dependency that yields a database session and closes it cleanly."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
