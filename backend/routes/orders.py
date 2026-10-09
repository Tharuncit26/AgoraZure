from datetime import datetime
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Order, OrderItem, Shop, Shopper, Product, Batch, LoyaltyPoint, Offer
from backend.schemas import OrderCreateRequest, OrderStatusUpdateRequest

router = APIRouter(prefix="/orders", tags=["Online Orders & Pre-books"])

VALID_STATUSES = [
    "pending", "accepted", "preparing", "ready", "delivered", "rejected",
    "picked_up", "out_for_delivery", "completed"
]

# -------------------------------------------------------------------------
# Create Online Order / Pre-Book (Shopper)
# -------------------------------------------------------------------------

@router.post("/create")
def create_order(
    payload: OrderCreateRequest,
    shopper_id: int = Query(..., description="Shopper ID"),
    db: Session = Depends(get_db)
):
    """
    Shopper places an order (Buy from Home or Pre-book) with collect option
    (Queue-free Pickup or Home Delivery). Applies active seasonal discounts.
    """
    shopper = db.query(Shopper).filter(Shopper.id == shopper_id).first()
    if not shopper:
        raise HTTPException(status_code=404, detail="Shopper not found.")

    shop = db.query(Shop).filter(Shop.id == payload.shop_id).first()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found.")

    # Home delivery check: shop must belong to a cluster with an assigned delivery rider
    if payload.collect_option == "home_delivery":
        if not shop.cluster_id or not shop.cluster or not shop.cluster.delivery_persons:
            raise HTTPException(
                status_code=400,
                detail="Home Delivery is not available for this shop because it is not part of an active delivery cluster. Please choose Queue-Free Pickup."
            )

    if not payload.items:
        raise HTTPException(status_code=400, detail="Cannot place empty order.")

    order_num = f"ORD-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"
    total_amount = 0.0

    new_order = Order(
        shopper_id=shopper_id,
        shop_id=payload.shop_id,
        order_number=order_num,
        order_type=payload.order_type,
        collect_option=payload.collect_option,
        status="pending",
        total_amount=0.0
    )
    db.add(new_order)
    db.flush()

    today_str = datetime.utcnow().strftime("%Y-%m-%d")

    for item_data in payload.items:
        product = db.query(Product).filter(
            Product.id == item_data.product_id,
            Product.shop_id == payload.shop_id
        ).first()

        if not product:
            raise HTTPException(status_code=404, detail=f"Product {item_data.product_id} not found.")

        # Check stock across batches
        batches = db.query(Batch).filter(
            Batch.product_id == product.id,
            Batch.quantity > 0
        ).all()
        avail = sum(b.quantity for b in batches)

        if avail < item_data.quantity:
            raise HTTPException(
                status_code=400,
                detail=f"Item '{product.name}' only has {avail} units available."
            )

        # Check for active seasonal offer on product or store-wide
        offer = db.query(Offer).filter(
            Offer.shop_id == payload.shop_id,
            Offer.active == True,
            Offer.valid_from <= today_str,
            Offer.valid_to >= today_str,
            (Offer.product_id == product.id) | (Offer.product_id == None)
        ).order_by(Offer.product_id.desc(), Offer.discount_percent.desc()).first()

        unit_price = product.price
        if offer:
            unit_price = round(product.price * (1.0 - offer.discount_percent / 100.0), 2)

        line_subtotal = round(unit_price * item_data.quantity, 2)
        total_amount += line_subtotal

        order_item = OrderItem(
            order_id=new_order.id,
            product_id=product.id,
            quantity=item_data.quantity,
            unit_price=unit_price
        )
        db.add(order_item)

    new_order.total_amount = round(total_amount, 2)
    db.commit()
    db.refresh(new_order)

    return {
        "success": True,
        "message": f"Order {new_order.order_number} placed successfully!",
        "order": {
            "id": new_order.id,
            "orderId": new_order.id,
            "shopId": new_order.shop_id,
            "order_number": new_order.order_number,
            "shop_name": shop.name,
            "order_type": new_order.order_type,
            "collect_option": new_order.collect_option,
            "status": new_order.status,
            "total_amount": new_order.total_amount,
            "created_at": new_order.created_at.strftime("%Y-%m-%d %H:%M:%S")
        }
    }

# -------------------------------------------------------------------------
# Shopkeeper Order List & Status Updates
# -------------------------------------------------------------------------

@router.get("/shopkeeper/list")
def list_shopkeeper_orders(
    shop_id: int = Query(..., description="Shop ID"),
    status_filter: Optional[str] = Query(None, description="Optional status filter"),
    db: Session = Depends(get_db)
):
    """Shopkeeper views all incoming and active orders."""
    query = db.query(Order).filter(Order.shop_id == shop_id)
    if status_filter:
        query = query.filter(Order.status == status_filter.strip())

    orders = query.order_by(Order.created_at.desc()).all()
    results = []

    for o in orders:
        shopper = o.shopper
        items = [
            {
                "product_id": it.product_id,
                "product_name": it.product.name if it.product else f"Product #{it.product_id}",
                "quantity": it.quantity,
                "unit_price": it.unit_price,
                "subtotal": round(it.quantity * it.unit_price, 2)
            }
            for it in o.items
        ]

        total_qty = sum(it["quantity"] for it in items)
        time_str = o.created_at.strftime("%Y-%m-%d %H:%M:%S")

        results.append({
            "id": o.id,
            "orderId": o.id,
            "shopId": o.shop_id,
            "shop_id": o.shop_id,
            "order_number": o.order_number,
            "order_type": o.order_type,
            "collect_option": o.collect_option,
            "status": o.status,
            "shopper_name": shopper.name if shopper else "Shopper",
            "shopper_phone": shopper.phone if shopper else "",
            "items": items,
            "quantity": total_qty,
            "total": o.total_amount,
            "total_amount": o.total_amount,
            "time": time_str,
            "created_at": time_str,
            "shopper": {
                "id": shopper.id if shopper else None,
                "name": shopper.name if shopper else "Shopper",
                "phone": shopper.phone if shopper else "",
                "address": shopper.address if shopper else ""
            }
        })

    return {"success": True, "count": len(results), "orders": results}

@router.put("/status/{order_id}")
def update_order_status(
    order_id: int,
    payload: OrderStatusUpdateRequest,
    shop_id: int = Query(..., description="Shop ID"),
    db: Session = Depends(get_db)
):
    """
    Shopkeeper updates order status:
    Pending -> Accepted -> Preparing -> Ready -> Delivered / Rejected.
    Awards loyalty points when delivered / completed.
    """
    new_status = payload.status.strip().lower()
    if new_status not in VALID_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{payload.status}'. Must be one of {VALID_STATUSES}"
        )

    order = db.query(Order).filter(
        Order.id == order_id,
        Order.shop_id == shop_id
    ).first()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")

    old_status = order.status.lower()
    order.status = new_status

    # If transitioning from pending to accepted/preparing/ready/delivered, deduct stock using FEFO
    if old_status == "pending" and new_status in ["accepted", "preparing", "ready", "delivered", "completed"]:
        for it in order.items:
            batches = db.query(Batch).filter(
                Batch.product_id == it.product_id,
                Batch.quantity > 0
            ).order_by(Batch.expiry_date.asc()).all()

            rem = it.quantity
            for b in batches:
                if rem == 0:
                    break
                ded = min(b.quantity, rem)
                b.quantity -= ded
                rem -= ded

    # If rejected after having been accepted/preparing/ready, restore stock
    if new_status == "rejected" and old_status in ["accepted", "preparing", "ready"]:
        for it in order.items:
            batch = db.query(Batch).filter(Batch.product_id == it.product_id).first()
            if batch:
                batch.quantity += it.quantity

    # If delivered or completed, award loyalty points (1 point per 50 spent)
    if new_status in ["delivered", "completed"] and old_status not in ["delivered", "completed"]:
        pts = max(int(order.total_amount // 50), 1)
        lp = LoyaltyPoint(
            shopper_id=order.shopper_id,
            shop_id=order.shop_id,
            points=pts,
            transaction_type="earned",
            description=f"Reward for Order #{order.order_number}"
        )
        db.add(lp)

    db.commit()

    return {
        "success": True,
        "message": f"Order #{order.order_number} status updated to '{order.status.capitalize()}'.",
        "new_status": order.status,
        "orderId": order.id,
        "status": order.status
    }

# -------------------------------------------------------------------------
# Shopper Order History & Digital Receipt
# -------------------------------------------------------------------------

@router.get("/shopper/history")
def list_shopper_orders(
    shopper_id: int = Query(..., description="Shopper ID"),
    db: Session = Depends(get_db)
):
    """Shopper views their past orders and live statuses."""
    orders = db.query(Order).filter(Order.shopper_id == shopper_id).order_by(Order.created_at.desc()).all()
    results = []

    for o in orders:
        items = [
            {
                "product_name": it.product.name if it.product else f"Product #{it.product_id}",
                "quantity": it.quantity,
                "unit_price": it.unit_price,
                "subtotal": round(it.quantity * it.unit_price, 2)
            }
            for it in o.items
        ]

        total_qty = sum(it["quantity"] for it in items)
        time_str = o.created_at.strftime("%Y-%m-%d %H:%M:%S")

        results.append({
            "id": o.id,
            "orderId": o.id,
            "shopId": o.shop_id,
            "shop_id": o.shop_id,
            "order_number": o.order_number,
            "shop_name": o.shop.name if o.shop else "Shop",
            "shop_phone": o.shop.phone if o.shop else "",
            "order_type": o.order_type,
            "collect_option": o.collect_option,
            "status": o.status,
            "total_amount": o.total_amount,
            "total": o.total_amount,
            "quantity": total_qty,
            "time": time_str,
            "created_at": time_str,
            "items": items
        })

    return {"success": True, "orders": results}

@router.get("/receipt/{order_number}")
def get_order_digital_receipt(order_number: str, db: Session = Depends(get_db)):
    """Fetch digital receipt for an order."""
    order = db.query(Order).filter(Order.order_number == order_number.strip()).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order receipt not found.")

    shop = order.shop
    shopper = order.shopper

    items = [
        {
            "product_name": it.product.name,
            "quantity": it.quantity,
            "unit_price": it.unit_price,
            "subtotal": round(it.quantity * it.unit_price, 2)
        }
        for it in order.items
    ]

    return {
        "success": True,
        "receipt": {
            "order_number": order.order_number,
            "order_type": order.order_type,
            "collect_option": order.collect_option,
            "status": order.status,
            "timestamp": order.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "shop": {
                "name": shop.name,
                "phone": shop.phone,
                "address": shop.address
            },
            "shopper": {
                "name": shopper.name,
                "phone": shopper.phone,
                "address": shopper.address
            },
            "items": items,
            "total_amount": order.total_amount
        }
    }
