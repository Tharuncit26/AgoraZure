from datetime import datetime
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

router = APIRouter(prefix="/shopper-portal", tags=["Shopper Experience"])

# -------------------------------------------------------------------------
# Search Autocomplete Suggestions (Dropdown)
# -------------------------------------------------------------------------

@router.get("/suggestions")
def get_search_suggestions(
    q: Optional[str] = Query("", description="Query prefix"),
    shop_id: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Returns quick suggestions for the search autocomplete dropdown:
    matching product titles, brands, and categories.
    """
    clean_q = (q or "").strip().lower()
    if not clean_q or len(clean_q) < 1:
        # Default trending suggestions
        popular = [
            {"text": "Milk", "type": "product", "category": "Dairy & Breakfast"},
            {"text": "Whole Wheat Bread", "type": "product", "category": "Bakery"},
            {"text": "Farm Fresh Eggs", "type": "product", "category": "Eggs & Meat"},
            {"text": "Basmati Rice", "type": "product", "category": "Staples & Grains"},
            {"text": "Maggi Noodles", "type": "product", "category": "Snacks & Instant Food"},
            {"text": "Amul Butter", "type": "product", "category": "Dairy & Breakfast"},
        ]
        return {"success": True, "suggestions": popular}

    filter_shop_id = None
    if shop_id is not None and not hasattr(shop_id, "default"):
        try:
            filter_shop_id = int(shop_id)
        except (ValueError, TypeError):
            filter_shop_id = None

    query = db.query(Product)
    if filter_shop_id is not None:
        query = query.filter(Product.shop_id == filter_shop_id)

    all_prods = query.all()
    suggestions = []
    seen = set()

    for p in all_prods:
        name_lower = p.name.lower()
        brand_lower = (p.brand or "").lower()
        cat_lower = (p.category or "").lower()

        # Product name match
        if clean_q in name_lower and p.name not in seen:
            seen.add(p.name)
            suggestions.append({
                "text": p.name,
                "type": "product",
                "category": p.category,
                "price": p.price,
                "image_url": p.image_url or "",
                "product_id": p.id
            })

        # Brand match
        if p.brand and clean_q in brand_lower and p.brand not in seen:
            seen.add(p.brand)
            suggestions.append({
                "text": p.brand,
                "type": "brand",
                "category": p.category
            })

        # Category match
        if p.category and clean_q in cat_lower and p.category not in seen:
            seen.add(p.category)
            suggestions.append({
                "text": p.category,
                "type": "category",
                "category": p.category
            })

        if len(suggestions) >= 10:
            break

    return {"success": True, "suggestions": suggestions}

# -------------------------------------------------------------------------
# Search Nearby Shops with Live Stock & Distance
# -------------------------------------------------------------------------

@router.get("/search")
async def search_products(
    q: Optional[str] = Query(None, description="Product search query"),
    shop_id: Optional[int] = Query(None, description="Filter by Shop ID"),
    category: Optional[str] = Query(None, description="Filter by Category"),
    shopper_lat: float = Query(12.9716, description="Shopper latitude"),
    shopper_lon: float = Query(77.5946, description="Shopper longitude"),
    shopper_id: Optional[str] = Query(None, description="Shopper ID for missed search logging"),
    db: Session = Depends(get_db)
):
    """
    Search for products across shops with case-insensitivity, trimmed queries,
    ranked results (exact > starts-with > contains across name, category, brand, shop name).
    Applies active seasonal offers / discounts and calculates Haversine distance in km.
    """
    shopper_id_int = int(shopper_id) if (shopper_id and str(shopper_id).strip().isdigit()) else None
    all_shops = db.query(Shop).all()
    query_str = (q or "").strip()
    q_clean = query_str.lower()

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

    # Safe numeric latitude/longitude
    try:
        s_lat = float(shopper_lat) if (shopper_lat is not None and not hasattr(shopper_lat, "default")) else 12.9716
    except Exception:
        s_lat = 12.9716
    try:
        s_lon = float(shopper_lon) if (shopper_lon is not None and not hasattr(shopper_lon, "default")) else 77.5946
    except Exception:
        s_lon = 77.5946

    # Pre-calculate distances to all shops
    shop_distances = {}
    for s in all_shops:
        dist = haversine_distance(s_lat, s_lon, s.latitude, s.longitude)
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

    # Clean filter_shop_id
    filter_shop_id = None
    if shop_id is not None and not hasattr(shop_id, "default"):
        try:
            filter_shop_id = int(shop_id)
        except (ValueError, TypeError):
            filter_shop_id = None

    # Clean filter_category
    filter_category = None
    if category is not None and not hasattr(category, "default"):
        c_str = str(category).strip()
        if c_str and c_str.lower() != "all":
            filter_category = c_str.lower()

    matches = []
    available_catalog = []

    all_products = db.query(Product).all()

    for prod in all_products:
        if filter_shop_id is not None and prod.shop_id != filter_shop_id:
            continue

        if filter_category and (prod.category or "").strip().lower() != filter_category:
            continue

        shop_info = shop_distances.get(prod.shop_id)
        if not shop_info:
            continue

        shop_obj = shop_info["shop"]

        # Calculate live stock across batches
        active_batches = [b for b in prod.batches if b.quantity > 0]
        live_stock = sum(b.quantity for b in active_batches)
        earliest_exp = sorted(b.expiry_date for b in active_batches)[0] if active_batches else "Out of Stock"
        in_stock = live_stock > 0 and (prod.is_available is not False)

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

        mrp_val = prod.mrp if prod.mrp is not None else round(prod.price * 1.15, 2)

        item_repr = {
            "id": prod.id,
            "product_id": prod.id,
            "name": prod.name,
            "barcode": prod.barcode,
            "brand": prod.brand or "General",
            "category": prod.category or "General",
            "description": prod.description or "",
            "price": effective_price,
            "original_price": prod.price,
            "mrp": mrp_val,
            "unit": prod.unit or "1 pc",
            "image_url": prod.image_url or "",
            "discount_percent": discount_pct,
            "has_offer": has_offer,
            "offer_title": offer_title,
            "live_stock": live_stock,
            "in_stock": in_stock,
            "is_available": prod.is_available if prod.is_available is not None else True,
            "earliest_expiry": earliest_exp,
            "shop_id": prod.shop_id,
            "shop_name": shop_obj.name,
            "shop_address": shop_obj.address,
            "shop_phone": shop_obj.phone,
            "shop_is_open": shop_obj.is_open if shop_obj.is_open is not None else True,
            "distance_km": shop_info["distance_km"],
            "has_shared_delivery": shop_info["has_shared_delivery"]
        }

        if in_stock:
            available_catalog.append(item_repr)

        if q_clean:
            name_lower = prod.name.strip().lower()
            cat_lower = (prod.category or "").strip().lower()
            brand_lower = (prod.brand or "").strip().lower()
            shop_lower = shop_obj.name.strip().lower()
            barcode_lower = (prod.barcode or "").strip().lower()

            in_name = q_clean in name_lower
            in_cat = q_clean in cat_lower
            in_brand = q_clean in brand_lower
            in_shop = q_clean in shop_lower
            in_barcode = (q_clean == barcode_lower or q_clean in barcode_lower)

            if not (in_name or in_cat or in_brand or in_shop or in_barcode):
                continue

            # Ranking: Exact match first, exact word in name, starts-with, contains
            name_words = name_lower.split()
            brand_words = brand_lower.split()

            if name_lower == q_clean:
                rank = 1
            elif any(w == q_clean for w in name_words):
                rank = 2
            elif any(w == q_clean for w in brand_words):
                rank = 3
            elif name_lower.startswith(q_clean):
                rank = 4
            elif any(w.startswith(q_clean) for w in name_words):
                rank = 5
            elif brand_lower.startswith(q_clean):
                rank = 6
            elif any(w.startswith(q_clean) for w in brand_words):
                rank = 7
            elif cat_lower.startswith(q_clean):
                rank = 8
            elif shop_lower.startswith(q_clean):
                rank = 9
            elif in_name:
                rank = 15
            elif in_brand:
                rank = 16
            elif in_cat:
                rank = 17
            elif in_shop:
                rank = 18
            else:
                rank = 25

            item_repr["match_rank"] = rank
        else:
            item_repr["match_rank"] = 50

        matches.append(item_repr)

    # Sort matches by match_rank (exact > starts-with > contains), then distance, then in_stock, then stock
    matches.sort(key=lambda x: (x["match_rank"], 0 if x["in_stock"] else 1, x["distance_km"], -x["live_stock"]))

    # Check unmet demand
    in_stock_matches = [m for m in matches if m["in_stock"]]
    is_missed = (query_str != "") and (len(in_stock_matches) == 0)

    smart_substitutes = []
    if is_missed:
        try:
            ms = MissedSearch(
                shopper_id=shopper_id_int,
                query_text=query_str,
                resolved=False
            )
            db.add(ms)
            db.commit()
        except Exception:
            pass

        try:
            smart_substitutes = await suggest_substitutes(query_str, available_catalog)
        except Exception:
            pass

    # Suggestions for empty search
    sample_suggestions = ["Milk", "Bread", "Eggs", "Atta", "Rice", "Bananas", "Butter", "Biscuits"]

    return {
        "success": True,
        "query": query_str,
        "count": len(matches),
        "results_count": len(matches),
        "in_stock_count": len(in_stock_matches),
        "is_missed_search": is_missed,
        "products": matches,
        "smart_substitutes": smart_substitutes,
        "popular_suggestions": sample_suggestions
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
    Near-expiry items are shown to customers as "Use soon" discounted offers.
    """
    all_shops = {s.id: s for s in db.query(Shop).all()}
    all_batches = db.query(Batch).filter(Batch.quantity > 0).all()

    today = datetime.utcnow().date()
    deals = []

    for b in all_batches:
        try:
            exp_date = datetime.strptime(b.expiry_date, "%Y-%m-%d").date()
        except Exception:
            continue

        days_left = (exp_date - today).days
        if 0 <= days_left <= days_window:
            prod = b.product
            shop = all_shops.get(b.shop_id)
            if not prod or not shop:
                continue

            # 25% automatic discount on use-soon deals
            discount = 25
            deal_price = round(prod.price * 0.75, 2)
            dist = haversine_distance(shopper_lat, shopper_lon, shop.latitude, shop.longitude)

            deals.append({
                "batch_id": b.id,
                "product_id": prod.id,
                "name": prod.name,
                "brand": prod.brand or "General",
                "category": prod.category,
                "unit": prod.unit or "1 pc",
                "image_url": prod.image_url or "",
                "original_price": prod.price,
                "mrp": prod.mrp or round(prod.price * 1.15, 2),
                "deal_price": deal_price,
                "discount_percent": discount,
                "days_left": days_left,
                "expiry_date": b.expiry_date,
                "quantity": b.quantity,
                "shop_id": shop.id,
                "shop_name": shop.name,
                "shop_address": shop.address,
                "distance_km": dist
            })

    deals.sort(key=lambda x: (x["days_left"], x["distance_km"]))
    return {"success": True, "deals": deals[:12]}

# -------------------------------------------------------------------------
# Notifications (Notify-Back Unmet Demand)
# -------------------------------------------------------------------------

@router.get("/notifications")
def get_notifications(
    shopper_id: int = Query(...),
    db: Session = Depends(get_db)
):
    """Fetches in-app notifications for shopper."""
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
def mark_notification_read(notif_id: int, db: Session = Depends(get_db)):
    """Marks a notification as read."""
    notif = db.query(Notification).filter(Notification.id == notif_id).first()
    if notif:
        notif.is_read = True
        db.commit()
    return {"success": True}

# -------------------------------------------------------------------------
# Customer Loyalty Points
# -------------------------------------------------------------------------

@router.get("/loyalty-points")
def get_shopper_loyalty_points(
    shopper_id: int = Query(...),
    db: Session = Depends(get_db)
):
    """Fetches total points and transaction history for the shopper."""
    records = db.query(LoyaltyPoint).filter(
        LoyaltyPoint.shopper_id == shopper_id
    ).order_by(LoyaltyPoint.created_at.desc()).all()

    earned = sum(r.points for r in records if r.transaction_type == "earned")
    redeemed = sum(r.points for r in records if r.transaction_type == "redeemed")
    balance = earned - redeemed

    return {
        "success": True,
        "total_points": balance,
        "history": [
            {
                "id": r.id,
                "shop_name": r.shop.name if r.shop else "Neighborhood Store",
                "points": r.points,
                "type": r.transaction_type,
                "description": r.description,
                "date": r.created_at.strftime("%Y-%m-%d %H:%M")
            }
            for r in records
        ]
    }
