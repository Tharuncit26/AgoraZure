import hashlib
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import Shop, Shopkeeper, Shopper
from backend.schemas import ShopRegisterRequest, LoginRequest, ShopperRegisterRequest
from backend.haversine import recompute_delivery_clusters

router = APIRouter(prefix="/auth", tags=["Authentication"])

def hash_password(pwd: str) -> str:
    """Simple SHA-256 hash for prototype security."""
    return hashlib.sha256(pwd.strip().encode("utf-8")).hexdigest()

# -------------------------------------------------------------------------
# Shopkeeper Register & Login
# -------------------------------------------------------------------------

@router.post("/shopkeeper/register")
def register_shop(payload: ShopRegisterRequest, db: Session = Depends(get_db)):
    """
    Registers a new shopkeeper and shop with latitude and longitude.
    Automatically recalculates 1 km delivery clusters and salary shares.
    """
    existing_shop = db.query(Shop).filter(Shop.phone == payload.phone).first()
    if existing_shop:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A shop with this phone number is already registered."
        )

    pwd_hash = hash_password(payload.password)

    # Create Shop
    new_shop = Shop(
        name=payload.shop_name.strip(),
        owner_name=payload.owner_name.strip(),
        phone=payload.phone.strip(),
        password_hash=pwd_hash,
        address=payload.address.strip(),
        latitude=payload.latitude,
        longitude=payload.longitude,
    )
    db.add(new_shop)
    db.flush()

    # Create Shopkeeper user associated with this shop
    new_shopkeeper = Shopkeeper(
        shop_id=new_shop.id,
        name=payload.owner_name.strip(),
        phone=payload.phone.strip(),
        password_hash=pwd_hash
    )
    db.add(new_shopkeeper)
    db.commit()
    db.refresh(new_shop)

    # Recompute clusters now that a new shop joined
    recompute_delivery_clusters(db)

    return {
        "success": True,
        "message": f"Shop '{new_shop.name}' registered successfully!",
        "shop": {
            "id": new_shop.id,
            "name": new_shop.name,
            "owner_name": new_shop.owner_name,
            "phone": new_shop.phone,
            "address": new_shop.address,
            "latitude": new_shop.latitude,
            "longitude": new_shop.longitude,
            "cluster_id": new_shop.cluster_id
        }
    }

@router.post("/shopkeeper/login")
def login_shopkeeper(payload: LoginRequest, db: Session = Depends(get_db)):
    """Shopkeeper login via phone and password."""
    pwd_hash = hash_password(payload.password)
    shopkeeper = db.query(Shopkeeper).filter(
        Shopkeeper.phone == payload.phone.strip(),
        Shopkeeper.password_hash == pwd_hash
    ).first()

    if not shopkeeper:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid phone number or password."
        )

    shop = db.query(Shop).filter(Shop.id == shopkeeper.shop_id).first()
    return {
        "success": True,
        "message": "Login successful",
        "shopkeeper": {
            "id": shopkeeper.id,
            "name": shopkeeper.name,
            "phone": shopkeeper.phone,
            "shop_id": shop.id if shop else None,
            "shop_name": shop.name if shop else None,
            "address": shop.address if shop else None,
            "latitude": shop.latitude if shop else None,
            "longitude": shop.longitude if shop else None,
            "cluster_id": shop.cluster_id if shop else None
        }
    }

# -------------------------------------------------------------------------
# Shopper Register & Login
# -------------------------------------------------------------------------

@router.post("/shopper/register")
def register_shopper(payload: ShopperRegisterRequest, db: Session = Depends(get_db)):
    """Registers a new shopper account."""
    existing = db.query(Shopper).filter(Shopper.phone == payload.phone.strip()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A shopper with this phone number is already registered."
        )

    pwd_hash = hash_password(payload.password)
    new_shopper = Shopper(
        name=payload.name.strip(),
        phone=payload.phone.strip(),
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
            "address": new_shopper.address,
            "latitude": new_shopper.latitude,
            "longitude": new_shopper.longitude
        }
    }

@router.post("/shopper/login")
def login_shopper(payload: LoginRequest, db: Session = Depends(get_db)):
    """Shopper login via phone and password."""
    pwd_hash = hash_password(payload.password)
    shopper = db.query(Shopper).filter(
        Shopper.phone == payload.phone.strip(),
        Shopper.password_hash == pwd_hash
    ).first()

    if not shopper:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid phone number or password."
        )

    return {
        "success": True,
        "message": "Login successful",
        "shopper": {
            "id": shopper.id,
            "name": shopper.name,
            "phone": shopper.phone,
            "address": shopper.address,
            "latitude": shopper.latitude,
            "longitude": shopper.longitude
        }
    }
