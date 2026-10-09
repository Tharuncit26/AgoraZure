import hashlib
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import Shop, Shopkeeper, Shopper
from backend.schemas import (
    ShopRegisterRequest, ShopUpdateRequest, ShopToggleOpenRequest,
    LoginRequest, ShopperRegisterRequest, ShopperUpdateRequest
)
from backend.haversine import recompute_delivery_clusters

router = APIRouter(prefix="/auth", tags=["Authentication & Profiles"])

def hash_password(pwd: str) -> str:
    """SHA-256 hash with salt for secure storage."""
    salt = "zephyr_2026_smart_commerce_salt"
    return hashlib.sha256(f"{salt}_{pwd.strip()}".encode("utf-8")).hexdigest()

# -------------------------------------------------------------------------
# Shopkeeper Register, Login & Profile Management
# -------------------------------------------------------------------------

@router.post("/shopkeeper/register")
def register_shop(payload: ShopRegisterRequest, db: Session = Depends(get_db)):
    """
    Registers a new shop and owner with phone, email, category, opening hours, and location.
    Links the owner account directly to the shop.
    """
    phone = payload.phone.strip()
    if not phone or len(phone) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A valid 10-digit phone number is required."
        )

    if not payload.password or len(payload.password) < 4:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 4 characters long."
        )

    existing_shop = db.query(Shop).filter(Shop.phone == phone).first()
    if existing_shop:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A shop with this phone number is already registered. Please log in."
        )

    pwd_hash = hash_password(payload.password)

    new_shop = Shop(
        name=payload.shop_name.strip(),
        owner_name=payload.owner_name.strip(),
        phone=phone,
        email=payload.email.strip().lower() if payload.email else None,
        password_hash=pwd_hash,
        address=payload.address.strip(),
        category=payload.category.strip() if payload.category else "Grocery & Supermarket",
        opening_hours=payload.opening_hours.strip() if payload.opening_hours else "7:00 AM - 10:00 PM",
        photo_url=payload.photo_url.strip() if payload.photo_url else None,
        is_open=True,
        latitude=payload.latitude,
        longitude=payload.longitude,
    )
    db.add(new_shop)
    db.flush()

    new_shopkeeper = Shopkeeper(
        shop_id=new_shop.id,
        name=payload.owner_name.strip(),
        phone=phone,
        email=payload.email.strip().lower() if payload.email else None,
        password_hash=pwd_hash
    )
    db.add(new_shopkeeper)
    db.commit()
    db.refresh(new_shop)

    # Recompute delivery cluster automatically
    try:
        recompute_delivery_clusters(db)
    except Exception:
        pass

    return {
        "success": True,
        "message": f"Shop '{new_shop.name}' registered successfully!",
        "shop": {
            "id": new_shop.id,
            "shop_id": new_shop.id,
            "name": new_shop.name,
            "shop_name": new_shop.name,
            "owner_name": new_shop.owner_name,
            "phone": new_shop.phone,
            "email": new_shop.email or "",
            "address": new_shop.address,
            "category": new_shop.category,
            "opening_hours": new_shop.opening_hours,
            "photo_url": new_shop.photo_url or "",
            "is_open": new_shop.is_open,
            "latitude": new_shop.latitude,
            "longitude": new_shop.longitude,
            "cluster_id": new_shop.cluster_id
        },
        "shopkeeper": {
            "id": new_shopkeeper.id,
            "shop_id": new_shop.id,
            "name": new_shopkeeper.name,
            "phone": new_shopkeeper.phone,
            "email": new_shopkeeper.email or "",
            "shop_name": new_shop.name,
            "address": new_shop.address,
            "category": new_shop.category,
            "opening_hours": new_shop.opening_hours,
            "photo_url": new_shop.photo_url or "",
            "is_open": new_shop.is_open,
            "latitude": new_shop.latitude,
            "longitude": new_shop.longitude,
            "cluster_id": new_shop.cluster_id
        }
    }

@router.post("/shopkeeper/login")
def login_shopkeeper(payload: LoginRequest, db: Session = Depends(get_db)):
    """Shopkeeper login via phone or email and password."""
    pwd_hash = hash_password(payload.password)
    query_target = (payload.phone or payload.email or "").strip()

    # Match by phone or email
    shopkeeper = db.query(Shopkeeper).filter(
        ((Shopkeeper.phone == query_target) | (Shopkeeper.email == query_target.lower())),
        Shopkeeper.password_hash == pwd_hash
    ).first()

    # Backwards compatibility check with legacy un-salted hash
    if not shopkeeper:
        legacy_hash = hashlib.sha256(payload.password.strip().encode("utf-8")).hexdigest()
        shopkeeper = db.query(Shopkeeper).filter(
            ((Shopkeeper.phone == query_target) | (Shopkeeper.email == query_target.lower())),
            Shopkeeper.password_hash == legacy_hash
        ).first()

    if not shopkeeper:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials. Please verify your phone/email and password."
        )

    shop = db.query(Shop).filter(Shop.id == shopkeeper.shop_id).first()

    return {
        "success": True,
        "message": "Login successful",
        "shopkeeper": {
            "id": shopkeeper.id,
            "shop_id": shop.id if shop else None,
            "name": shopkeeper.name,
            "phone": shopkeeper.phone,
            "email": shopkeeper.email or (shop.email if shop else ""),
            "shop_name": shop.name if shop else None,
            "address": shop.address if shop else None,
            "category": shop.category if shop else "Grocery & Supermarket",
            "opening_hours": shop.opening_hours if shop else "7:00 AM - 10:00 PM",
            "photo_url": shop.photo_url if shop else "",
            "is_open": shop.is_open if shop else True,
            "latitude": shop.latitude if shop else None,
            "longitude": shop.longitude if shop else None,
            "cluster_id": shop.cluster_id if shop else None
        }
    }

@router.get("/shopkeeper/profile")
def get_shopkeeper_profile(shop_id: int = Query(...), db: Session = Depends(get_db)):
    """Fetches shop and owner profile."""
    shop = db.query(Shop).filter(Shop.id == shop_id).first()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found.")

    return {
        "success": True,
        "shop": {
            "id": shop.id,
            "shop_id": shop.id,
            "name": shop.name,
            "shop_name": shop.name,
            "owner_name": shop.owner_name,
            "phone": shop.phone,
            "email": shop.email or "",
            "address": shop.address,
            "category": shop.category or "Grocery & Supermarket",
            "opening_hours": shop.opening_hours or "7:00 AM - 10:00 PM",
            "photo_url": shop.photo_url or "",
            "is_open": shop.is_open if shop.is_open is not None else True,
            "latitude": shop.latitude,
            "longitude": shop.longitude,
            "cluster_id": shop.cluster_id
        }
    }

@router.put("/shopkeeper/profile")
def update_shopkeeper_profile(
    payload: ShopUpdateRequest,
    shop_id: int = Query(...),
    db: Session = Depends(get_db)
):
    """Updates shop settings, opening hours, category, name, and owner details."""
    shop = db.query(Shop).filter(Shop.id == shop_id).first()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found.")

    if payload.shop_name:
        shop.name = payload.shop_name.strip()
    if payload.owner_name:
        shop.owner_name = payload.owner_name.strip()
    if payload.phone:
        shop.phone = payload.phone.strip()
    if payload.email is not None:
        shop.email = payload.email.strip().lower()
    if payload.address:
        shop.address = payload.address.strip()
    if payload.category:
        shop.category = payload.category.strip()
    if payload.opening_hours:
        shop.opening_hours = payload.opening_hours.strip()
    if payload.photo_url is not None:
        shop.photo_url = payload.photo_url.strip()
    if payload.is_open is not None:
        shop.is_open = payload.is_open
    if payload.latitude is not None:
        shop.latitude = payload.latitude
    if payload.longitude is not None:
        shop.longitude = payload.longitude

    db.commit()
    db.refresh(shop)

    return {
        "success": True,
        "message": "Shop profile updated successfully!",
        "shop": {
            "id": shop.id,
            "shop_id": shop.id,
            "name": shop.name,
            "shop_name": shop.name,
            "owner_name": shop.owner_name,
            "phone": shop.phone,
            "email": shop.email or "",
            "address": shop.address,
            "category": shop.category,
            "opening_hours": shop.opening_hours,
            "photo_url": shop.photo_url or "",
            "is_open": shop.is_open,
            "latitude": shop.latitude,
            "longitude": shop.longitude,
            "cluster_id": shop.cluster_id
        }
    }

@router.put("/shopkeeper/toggle-open")
def toggle_shop_open(
    payload: ShopToggleOpenRequest,
    shop_id: int = Query(...),
    db: Session = Depends(get_db)
):
    """Toggles shop between Open and Closed."""
    shop = db.query(Shop).filter(Shop.id == shop_id).first()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found.")

    shop.is_open = payload.is_open
    db.commit()

    return {
        "success": True,
        "message": f"Shop is now {'OPEN for business' if shop.is_open else 'CLOSED temporarily'}.",
        "is_open": shop.is_open
    }

# -------------------------------------------------------------------------
# Shopper Register, Login & Profile Management
# -------------------------------------------------------------------------

@router.post("/shopper/register")
def register_shopper(payload: ShopperRegisterRequest, db: Session = Depends(get_db)):
    """Registers a new shopper account with name, phone, email, and delivery address."""
    phone = payload.phone.strip()
    if not phone or len(phone) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A valid 10-digit mobile number is required."
        )

    if not payload.password or len(payload.password) < 4:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 4 characters long."
        )

    existing = db.query(Shopper).filter(Shopper.phone == phone).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A shopper with this phone number is already registered. Please log in."
        )

    pwd_hash = hash_password(payload.password)
    new_shopper = Shopper(
        name=payload.name.strip(),
        phone=phone,
        email=payload.email.strip().lower() if payload.email else None,
        password_hash=pwd_hash,
        address=payload.address.strip(),
        latitude=payload.latitude,
        longitude=payload.longitude
    )
    db.add(new_shopper)
    db.commit()
    db.refresh(new_shopper)

    return {
        "success": True,
        "message": f"Welcome, {new_shopper.name}!",
        "shopper": {
            "id": new_shopper.id,
            "name": new_shopper.name,
            "phone": new_shopper.phone,
            "email": new_shopper.email or "",
            "address": new_shopper.address,
            "latitude": new_shopper.latitude,
            "longitude": new_shopper.longitude
        }
    }

@router.post("/shopper/login")
def login_shopper(payload: LoginRequest, db: Session = Depends(get_db)):
    """Shopper login via phone or email and password."""
    pwd_hash = hash_password(payload.password)
    query_target = (payload.phone or payload.email or "").strip()

    shopper = db.query(Shopper).filter(
        ((Shopper.phone == query_target) | (Shopper.email == query_target.lower())),
        Shopper.password_hash == pwd_hash
    ).first()

    # Backwards compatibility check
    if not shopper:
        legacy_hash = hashlib.sha256(payload.password.strip().encode("utf-8")).hexdigest()
        shopper = db.query(Shopper).filter(
            ((Shopper.phone == query_target) | (Shopper.email == query_target.lower())),
            Shopper.password_hash == legacy_hash
        ).first()

    if not shopper:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid phone/email or password."
        )

    return {
        "success": True,
        "message": "Login successful",
        "shopper": {
            "id": shopper.id,
            "name": shopper.name,
            "phone": shopper.phone,
            "email": shopper.email or "",
            "address": shopper.address,
            "latitude": shopper.latitude,
            "longitude": shopper.longitude
        }
    }

@router.get("/shopper/profile")
def get_shopper_profile(shopper_id: int = Query(...), db: Session = Depends(get_db)):
    """Fetches shopper profile details."""
    shopper = db.query(Shopper).filter(Shopper.id == shopper_id).first()
    if not shopper:
        raise HTTPException(status_code=404, detail="Shopper not found.")

    return {
        "success": True,
        "shopper": {
            "id": shopper.id,
            "name": shopper.name,
            "phone": shopper.phone,
            "email": shopper.email or "",
            "address": shopper.address,
            "latitude": shopper.latitude,
            "longitude": shopper.longitude
        }
    }

@router.put("/shopper/profile")
def update_shopper_profile(
    payload: ShopperUpdateRequest,
    shopper_id: int = Query(...),
    db: Session = Depends(get_db)
):
    """Updates shopper profile and default delivery address."""
    shopper = db.query(Shopper).filter(Shopper.id == shopper_id).first()
    if not shopper:
        raise HTTPException(status_code=404, detail="Shopper not found.")

    if payload.name:
        shopper.name = payload.name.strip()
    if payload.phone:
        shopper.phone = payload.phone.strip()
    if payload.email is not None:
        shopper.email = payload.email.strip().lower()
    if payload.address:
        shopper.address = payload.address.strip()
    if payload.latitude is not None:
        shopper.latitude = payload.latitude
    if payload.longitude is not None:
        shopper.longitude = payload.longitude

    db.commit()
    db.refresh(shopper)

    return {
        "success": True,
        "message": "Profile updated successfully!",
        "shopper": {
            "id": shopper.id,
            "name": shopper.name,
            "phone": shopper.phone,
            "email": shopper.email or "",
            "address": shopper.address,
            "latitude": shopper.latitude,
            "longitude": shopper.longitude
        }
    }

@router.get("/shops")
def list_all_shops(db: Session = Depends(get_db)):
    """Returns list of all active registered shops with category, address, open status."""
    shops = db.query(Shop).order_by(Shop.name.asc()).all()
    return {
        "success": True,
        "shops": [
            {
                "id": s.id,
                "shop_id": s.id,
                "name": s.name,
                "owner_name": s.owner_name,
                "phone": s.phone,
                "address": s.address,
                "category": s.category or "Grocery & Supermarket",
                "opening_hours": s.opening_hours or "7:00 AM - 10:00 PM",
                "photo_url": s.photo_url or "",
                "is_open": s.is_open if s.is_open is not None else True,
                "latitude": s.latitude,
                "longitude": s.longitude,
                "cluster_id": s.cluster_id
            }
            for s in shops
        ]
    }
