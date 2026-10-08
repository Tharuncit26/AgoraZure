from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import LoyaltyPoint, Offer, Product, Shopper, Shop
from backend.schemas import OfferCreateRequest

router = APIRouter(prefix="/marketing", tags=["Loyalty & Seasonal Offers"])

# -------------------------------------------------------------------------
# Shopkeeper Loyalty Points View
# -------------------------------------------------------------------------

@router.get("/loyalty-summary")
def get_shop_loyalty_summary(
    shop_id: int = Query(..., description="Shop ID"),
    db: Session = Depends(get_db)
):
    """
    Shopkeeper can see loyalty points earned by customers at their shop.
    """
    points_records = db.query(LoyaltyPoint).filter(
        LoyaltyPoint.shop_id == shop_id
    ).order_by(LoyaltyPoint.created_at.desc()).all()

    # Aggregate by customer
    customer_summary = {}
    for r in points_records:
        shopper = r.shopper
        if not shopper:
            continue
        if shopper.id not in customer_summary:
            customer_summary[shopper.id] = {
                "shopper_id": shopper.id,
                "name": shopper.name,
                "phone": shopper.phone,
                "total_points_earned": 0,
                "total_transactions": 0,
                "last_active": r.created_at.strftime("%Y-%m-%d %H:%M")
            }
        if r.transaction_type == "earned":
            customer_summary[shopper.id]["total_points_earned"] += r.points
        customer_summary[shopper.id]["total_transactions"] += 1

    return {
        "success": True,
        "total_rewards_issued": sum(r.points for r in points_records if r.transaction_type == "earned"),
        "total_customers_enrolled": len(customer_summary),
        "customers": list(customer_summary.values()),
        "recent_transactions": [
            {
                "id": r.id,
                "customer_name": r.shopper.name if r.shopper else "Shopper",
                "points": r.points,
                "type": r.transaction_type,
                "description": r.description,
                "timestamp": r.created_at.strftime("%Y-%m-%d %H:%M")
            }
            for r in points_records[:20]
        ]
    }

# -------------------------------------------------------------------------
# Seasonal Offers CRUD
# -------------------------------------------------------------------------

@router.get("/offers")
def list_offers(
    shop_id: int = Query(..., description="Shop ID"),
    db: Session = Depends(get_db)
):
    """Lists all active and scheduled seasonal offers created by the shopkeeper."""
    offers = db.query(Offer).filter(Offer.shop_id == shop_id).order_by(Offer.created_at.desc()).all()
    return {
        "success": True,
        "offers": [
            {
                "id": o.id,
                "title": o.title,
                "discount_percent": o.discount_percent,
                "product_id": o.product_id,
                "product_name": o.product.name if o.product else "All Products (Store-wide)",
                "valid_from": o.valid_from,
                "valid_to": o.valid_to,
                "active": o.active
            }
            for o in offers
        ]
    }

@router.post("/offers")
def create_offer(
    payload: OfferCreateRequest,
    shop_id: int = Query(..., description="Shop ID"),
    db: Session = Depends(get_db)
):
    """Shopkeeper creates a new seasonal offer or festive discount."""
    shop = db.query(Shop).filter(Shop.id == shop_id).first()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found.")

    new_offer = Offer(
        shop_id=shop_id,
        product_id=payload.product_id,
        title=payload.title.strip(),
        discount_percent=payload.discount_percent,
        valid_from=payload.valid_from.strip(),
        valid_to=payload.valid_to.strip(),
        active=True
    )
    db.add(new_offer)
    db.commit()
    db.refresh(new_offer)

    return {
        "success": True,
        "message": f"Seasonal offer '{new_offer.title}' created successfully!",
        "offer_id": new_offer.id
    }

@router.delete("/offers/{offer_id}")
def delete_offer(
    offer_id: int,
    shop_id: int = Query(..., description="Shop ID"),
    db: Session = Depends(get_db)
):
    """Removes a seasonal offer."""
    offer = db.query(Offer).filter(Offer.id == offer_id, Offer.shop_id == shop_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found.")

    db.delete(offer)
    db.commit()
    return {"success": True, "message": "Offer deleted."}
