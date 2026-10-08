from datetime import datetime, timedelta
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Product, Batch, Shop
from backend.schemas import ShrinkageCheckRequest

router = APIRouter(prefix="/alerts", tags=["Shopkeeper Alerts"])

# -------------------------------------------------------------------------
# Low Stock Alert
# -------------------------------------------------------------------------

@router.get("/low-stock")
def get_low_stock_alerts(
    shop_id: int = Query(..., description="Shop ID"),
    db: Session = Depends(get_db)
):
    """
    Returns all products whose live total stock across batches is less than or
    equal to their low_stock_threshold.
    """
    products = db.query(Product).filter(Product.shop_id == shop_id).all()
    alerts = []

    for p in products:
        batches = db.query(Batch).filter(
            Batch.product_id == p.id,
            Batch.quantity > 0
        ).all()
        current_stock = sum(b.quantity for b in batches)

        if current_stock <= p.low_stock_threshold:
            alerts.append({
                "product_id": p.id,
                "name": p.name,
                "barcode": p.barcode,
                "price": p.price,
                "current_stock": current_stock,
                "threshold": p.low_stock_threshold,
                "severity": "CRITICAL" if current_stock == 0 else "WARNING",
                "message": (
                    f"Out of stock! (0 units left)"
                    if current_stock == 0
                    else f"Low stock alert: {current_stock} units left (Threshold: {p.low_stock_threshold})"
                )
            })

    return {
        "success": True,
        "count": len(alerts),
        "alerts": alerts
    }

# -------------------------------------------------------------------------
# Shrinkage Alert
# -------------------------------------------------------------------------

@router.post("/shrinkage-check")
def check_shrinkage(
    payload: ShrinkageCheckRequest,
    shop_id: int = Query(..., description="Shop ID"),
    db: Session = Depends(get_db)
):
    """
    Shrinkage Alert:
    Shopkeeper enters physical counted quantity. System compares expected stock
    vs counted quantity and flags any discrepancy (theft, damage, leakage).
    """
    product = db.query(Product).filter(
        Product.id == payload.product_id,
        Product.shop_id == shop_id
    ).first()

    if not product:
        raise HTTPException(status_code=404, detail="Product not found in this shop.")

    batches = db.query(Batch).filter(
        Batch.product_id == product.id,
        Batch.quantity > 0
    ).all()
    expected_qty = sum(b.quantity for b in batches)
    counted_qty = payload.counted_quantity
    diff = counted_qty - expected_qty  # Negative means missing / shrinkage

    has_shrinkage = diff < 0
    surplus = diff > 0
    mismatch = diff != 0

    financial_impact = abs(diff) * product.price

    status_str = "MATCH"
    msg = f"Physical count matches expected stock perfectly ({expected_qty} units)."

    if has_shrinkage:
        status_str = "SHRINKAGE_DETECTED"
        msg = (
            f"⚠️ SHRINKAGE DETECTED! Expected {expected_qty} units, but physically counted {counted_qty} units. "
            f"Missing: {abs(diff)} units (Estimated financial loss: ₹{financial_impact:.2f})."
        )
    elif surplus:
        status_str = "SURPLUS_DETECTED"
        msg = (
            f"ℹ️ Physical count ({counted_qty}) is greater than recorded system stock ({expected_qty}). "
            f"Surplus: {diff} extra units detected."
        )

    return {
        "success": True,
        "product_id": product.id,
        "product_name": product.name,
        "expected_quantity": expected_qty,
        "counted_quantity": counted_qty,
        "discrepancy": diff,
        "mismatch": mismatch,
        "status": status_str,
        "financial_impact": financial_impact,
        "message": msg
    }

# -------------------------------------------------------------------------
# Expiry Alert
# -------------------------------------------------------------------------

@router.get("/expiry")
def get_expiry_alerts(
    shop_id: int = Query(..., description="Shop ID"),
    days_threshold: int = Query(30, description="Flag batches expiring within N days"),
    db: Session = Depends(get_db)
):
    """
    Expiry Alert:
    Finds batches nearing expiry (within N days) or already expired,
    highlighting the FEFO priority so older stock is cleared first.
    """
    now = datetime.utcnow().date()
    target_date = now + timedelta(days=days_threshold)
    target_str = target_date.strftime("%Y-%m-%d")
    today_str = now.strftime("%Y-%m-%d")

    # Fetch active batches for this shop with expiry_date <= target_str
    batches = db.query(Batch).join(Product).filter(
        Batch.shop_id == shop_id,
        Batch.quantity > 0,
        Batch.expiry_date <= target_str
    ).order_by(Batch.expiry_date.asc()).all()

    alerts = []
    for b in batches:
        prod = b.product
        try:
            exp_date = datetime.strptime(b.expiry_date, "%Y-%m-%d").date()
            days_left = (exp_date - now).days
        except Exception:
            days_left = 0

        is_expired = days_left < 0
        severity = "EXPIRED" if is_expired else ("CRITICAL" if days_left <= 7 else "WARNING")

        alerts.append({
            "batch_id": b.id,
            "batch_number": b.batch_number,
            "product_id": prod.id,
            "product_name": prod.name,
            "barcode": prod.barcode,
            "price": prod.price,
            "quantity": b.quantity,
            "expiry_date": b.expiry_date,
            "days_left": days_left,
            "is_expired": is_expired,
            "severity": severity,
            "fefo_advice": (
                f"Batch {b.batch_number} is EXPIRED ({abs(days_left)} days ago). Remove from shelves!"
                if is_expired
                else f"Batch {b.batch_number} expires in {days_left} days! Sell first via FEFO or put in 'Use Soon' deals."
            )
        })

    return {
        "success": True,
        "count": len(alerts),
        "days_window": days_threshold,
        "alerts": alerts
    }
