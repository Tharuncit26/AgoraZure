from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import (
    Shop, Product, Batch, Shopper, MissedSearch, Notification,
    LoyaltyPoint, Offer, DeliveryCluster, DeliveryPerson
)
from backend.haversine import haversine_distance
from backend.ai_service import suggest_substitutes
from backend.schemas import MissedSearchLogRequest

router = APIRouter(prefix="/shopper-portal", tags=["Shopper Experience"])

# -------------------------------------------------------------------------
# Search Nearby Shops with Live Stock & Distance
# -------------------------------------------------------------------------

@router.get("/search")
async def search_products(
    q: Optional[str] = Query(None, description="Product search query"),
    shop_id: Optional[int] = Query(None, description="Filter by Shop ID"),
    shopper_lat: float = Query(12.9716, description="Shopper latitude"),
    shopper_lon: float = Query(77.5946, description="Shopper longitude"),
    shopper_id: Optional[str] = Query(None, description="Shopper ID for missed search logging"),
    db: Session = Depends(get_db)
):
    """
    Search for a product across nearby shops.
    Ranks results: exact match first, starts-with second, contains third.
    Applies active seasonal offers / discounts and calculates Haversine distance in km.
    """
    shopper_id_int = int(shopper_id) if (shopper_id and str(shopper_id).strip().isdigit()) else None
    all_shops = db.query(Shop).all()
    query_str = (q or "").strip()

    # Query active seasonal offers
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    active_offers = db.query(Offer).filter(
        Offer.active == True,
        Offer.valid_from <= today_str,
        Offer.valid_to >= today_str
    ).all()

    product_offers = {}
    store_offers = {}
    for off in active_offers:
        if off.product_id:
            product_offers[(off.shop_id, off.product_id)] = off
        else:
            if off.shop_id not in store_offers or off.discount_percent > store_offers[off.shop_id].discount_percent:
                store_offers[off.shop_id] = off

    # Pre-calculate distances to all shops
    shop_distances = {}
    for s in all_shops:
        dist = haversine_distance(shopper_lat, shopper_lon, s.latitude, s.longitude)
        has_delivery = False
        if s.cluster_id:
            cluster_rider = db.query(DeliveryPerson).filter(DeliveryPerson.cluster_id == s.cluster_id).first()
            if cluster_rider:
                has_delivery = True

        shop_distances[s.id] = {
            "shop": s,
            "distance_km": dist,
            "has_shared_delivery": has_delivery
        }

    matches = []
    available_catalog = []

    # Collect products
    all_products = db.query(Product).all()
    q_clean = query_str.lower()

    for prod in all_products:
        if shop_id is not None and prod.shop_id != shop_id:
            continue

        shop_info = shop_distances.get(prod.shop_id)
        if not shop_info:
            continue

        active_batches = [b for b in prod.batches if b.quantity > 0]
        live_stock = sum(b.quantity for b in active_batches)
        earliest_exp = sorted(b.expiry_date for b in active_batches)[0] if active_batches else "Out of Stock"

        # Apply seasonal offer if available
        matched_offer = product_offers.get((prod.shop_id, prod.id)) or store_offers.get(prod.shop_id)
        if matched_offer:
            discount_pct = matched_offer.discount_percent
            effective_price = round(prod.price * (1.0 - discount_pct / 100.0), 2)
            has_offer = True
            offer_title = matched_offer.title
        else:
            discount_pct = 0.0
            effective_price = prod.price
            has_offer = False
            offer_title = None

        item_repr = {
            "id": prod.id,
            "name": prod.name,
            "barcode": prod.barcode,
            "price": effective_price,
            "original_price": prod.price,
            "discount_percent": discount_pct,
            "has_offer": has_offer,
            "offer_title": offer_title,
            "category": prod.category,
            "live_stock": live_stock,
            "earliest_expiry": earliest_exp,
            "shop_id": prod.shop_id,
            "shop_name": shop_info["shop"].name,
            "shop_address": shop_info["shop"].address,
            "shop_phone": shop_info["shop"].phone,
            "distance_km": shop_info["distance_km"],
            "has_shared_delivery": shop_info["has_shared_delivery"]
        }

        if live_stock > 0:
            available_catalog.append(item_repr)

        if q_clean:
            name_lower = prod.name.strip().lower()
            cat_lower = prod.category.strip().lower()
            shop_lower = shop_info["shop"].name.strip().lower()
            barcode_lower = prod.barcode.strip().lower()

            in_name = q_clean in name_lower
            in_cat = q_clean in cat_lower
            in_shop = q_clean in shop_lower
            in_barcode = (q_clean == barcode_lower or q_clean in barcode_lower)

            if not (in_name or in_cat or in_shop or in_barcode):
                continue

            # Ranking: Exact match first, starts-with second, contains third
            name_words = name_lower.split()
            cat_words = cat_lower.split()
            shop_words = shop_lower.split()

            if name_lower == q_clean:
                rank = 1
            elif cat_lower == q_clean:
                rank = 2
            elif shop_lower == q_clean:
                rank = 3
            elif barcode_lower == q_clean:
                rank = 4
            elif name_lower.startswith(q_clean) or any(w.startswith(q_clean) for w in name_words):
                rank = 10
            elif cat_lower.startswith(q_clean) or any(w.startswith(q_clean) for w in cat_words):
                rank = 11
            elif shop_lower.startswith(q_clean) or any(w.startswith(q_clean) for w in shop_words):
                rank = 12
            elif in_name:
                rank = 20
            elif in_cat:
                rank = 21
            elif in_shop:
                rank = 22
            else:
                rank = 25
            item_repr["match_rank"] = rank
        else:
            item_repr["match_rank"] = 50

        matches.append(item_repr)

    # Sort matches by match_rank (exact > starts-with > contains), then distance, then live stock
    matches.sort(key=lambda x: (x["match_rank"], x["distance_km"], -x["live_stock"]))

    # Check if this search was unmet (zero results OR all matching have 0 stock)
    in_stock_matches = [m for m in matches if m["live_stock"] > 0]
    is_missed = (query_str != "") and (len(in_stock_matches) == 0)

    smart_substitutes = []
    if is_missed:
        # 1. Log Missed Search in DB (Unmet-Demand Loop)
        ms = MissedSearch(
            shopper_id=shopper_id_int,
            query_text=query_str,
            resolved=False
        )
        db.add(ms)
        db.commit()

        # 2. Get AI Smart Substitutes from available items nearby
        smart_substitutes = await suggest_substitutes(query_str, available_catalog)

    return {
        "success": True,
        "query": query_str,
        "results_count": len(matches),
        "in_stock_count": len(in_stock_matches),
        "is_missed_search": is_missed,
        "products": matches,
        "smart_substitutes": smart_substitutes
    }

# -------------------------------------------------------------------------
# "Use Soon" Deals (Near-Expiry discounted stock)
# -------------------------------------------------------------------------

@router.get("/use-soon-deals")
def get_use_soon_deals(
    shopper_lat: float = Query(12.9716),
    shopper_lon: float = Query(77.5946),
    days_window: int = Query(14, description="Items expiring within N days"),
    db: Session = Depends(get_db)
):
    """
    "Use Soon" Deals:
    Near-expiry items are shown to customers as "Use soon" discounted offers
    so stock is sold, not wasted.
    """
    now = datetime.utcnow().date()
    target_date = now + timedelta(days=days_window)
    target_str = target_date.strftime("%Y-%m-%d")

    # Find batches expiring between today and target_date with quantity > 0
    near_batches = db.query(Batch).filter(
        Batch.quantity > 0,
        Batch.expiry_date <= target_str,
        Batch.expiry_date >= now.strftime("%Y-%m-%d")
    ).order_by(Batch.expiry_date.asc()).all()

    deals = []
    seen_products = set()

    for b in near_batches:
        prod = b.product
        shop = prod.shop
        if prod.id in seen_products:
            continue
        seen_products.add(prod.id)

        try:
            exp_date = datetime.strptime(b.expiry_date, "%Y-%m-%d").date()
            days_left = max((exp_date - now).days, 0)
        except Exception:
            days_left = 1

        dist = haversine_distance(shopper_lat, shopper_lon, shop.latitude, shop.longitude)

        # Dynamic discount: 30% discount for use-soon clearance
        discount_pct = 30
        deal_price = round(prod.price * (1 - discount_pct / 100), 2)

        deals.append({
            "product_id": prod.id,
            "product_name": prod.name,
            "category": prod.category,
            "original_price": prod.price,
            "deal_price": deal_price,
            "discount_percent": discount_pct,
            "quantity_available": b.quantity,
            "expiry_date": b.expiry_date,
            "days_left": days_left,
            "shop_id": shop.id,
            "shop_name": shop.name,
            "shop_address": shop.address,
            "distance_km": dist
        })

    deals.sort(key=lambda x: (x["days_left"], x["distance_km"]))
    return {"success": True, "deals_count": len(deals), "deals": deals}

# -------------------------------------------------------------------------
# Notifications (Notify-Back from Unmet-Demand Loop)
# -------------------------------------------------------------------------

@router.get("/notifications")
def get_shopper_notifications(
    shopper_id: int = Query(..., description="Shopper ID"),
    db: Session = Depends(get_db)
):
    """Fetches in-app notifications for the shopper, including notify-backs."""
    notifs = db.query(Notification).filter(
        Notification.shopper_id == shopper_id
    ).order_by(Notification.created_at.desc()).all()

    return {
        "success": True,
        "notifications": [
            {
                "id": n.id,
                "title": n.title,
                "message": n.message,
                "is_read": n.is_read,
                "created_at": n.created_at.strftime("%Y-%m-%d %H:%M")
            }
            for n in notifs
        ]
    }

@router.put("/notifications/{notif_id}/read")
def mark_notification_read(
    notif_id: int,
    shopper_id: int = Query(..., description="Shopper ID"),
    db: Session = Depends(get_db)
):
    """Marks a notification as read."""
    notif = db.query(Notification).filter(
        Notification.id == notif_id,
        Notification.shopper_id == shopper_id
    ).first()

    if notif:
        notif.is_read = True
        db.commit()

    return {"success": True}

# -------------------------------------------------------------------------
# Loyalty Points
# -------------------------------------------------------------------------

@router.get("/loyalty-points")
def get_shopper_loyalty_points(
    shopper_id: int = Query(..., description="Shopper ID"),
    db: Session = Depends(get_db)
):
    """
    Shoppers earn points on purchases and can see their points balance
    to turn one-time visitors into repeat customers.
    """
    pts = db.query(LoyaltyPoint).filter(
        LoyaltyPoint.shopper_id == shopper_id
    ).order_by(LoyaltyPoint.created_at.desc()).all()

    total_earned = sum(p.points for p in pts if p.transaction_type == "earned")
    total_redeemed = sum(p.points for p in pts if p.transaction_type == "redeemed")
    balance = total_earned - total_redeemed

    history = [
        {
            "id": p.id,
            "points": p.points,
            "transaction_type": p.transaction_type,
            "description": p.description,
            "shop_name": p.shop.name if p.shop else "AgoraZure Store",
            "created_at": p.created_at.strftime("%Y-%m-%d %H:%M")
        }
        for p in pts
    ]

    return {
        "success": True,
        "points_balance": balance,
        "total_earned": total_earned,
        "total_redeemed": total_redeemed,
        "history": history
    }
