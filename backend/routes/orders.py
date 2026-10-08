from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Order, OrderItem, Shop, Shopper, Product, Batch, LoyaltyPoint
from backend.schemas import OrderCreateRequest, OrderStatusUpdateRequest

router = APIRouter(prefix="/orders", tags=["Online Orders & Pre-books"])

VALID_STATUSES = ["pending", "accepted", "ready", "picked_up", "out_for_delivery", "completed"]

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
    (Queue-free Pickup or Home Delivery).
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

    order_num = f"ORD-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
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

        line_subtotal = round(product.price * item_data.quantity, 2)
        total_amount += line_subtotal

        order_item = OrderItem(
            order_id=new_order.id,
            product_id=product.id,
            quantity=item_data.quantity,
            unit_price=product.price
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
                "product_name": it.product.name,
                "quantity": it.quantity,
                "unit_price": it.unit_price,
                "subtotal": round(it.quantity * it.unit_price, 2)
            }
            for it in o.items
        ]

        results.append({
            "id": o.id,
            "order_number": o.order_number,
            "order_type": o.order_type,
            "collect_option": o.collect_option,
            "status": o.status,
            "total_amount": o.total_amount,
            "created_at": o.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "shopper": {
                "id": shopper.id,
                "name": shopper.name,
                "phone": shopper.phone,
                "address": shopper.address
            },
            "items": items
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
    accepted -> ready -> picked_up / out_for_delivery -> completed.
    When completed, awards loyalty points to the shopper!
    """
    if payload.status not in VALID_STATUSES:
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

    old_status = order.status
    order.status = payload.status

    # If transitioning to accepted, deduct stock from batches using FEFO
    if old_status == "pending" and payload.status == "accepted":
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

    # If completed, award loyalty points (1 point per 50 spent)
    if payload.status == "completed" and old_status != "completed":
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
        "message": f"Order #{order.order_number} status updated from '{old_status}' to '{payload.status}'.",
        "new_status": order.status
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
                "product_name": it.product.name,
                "quantity": it.quantity,
                "unit_price": it.unit_price,
                "subtotal": round(it.quantity * it.unit_price, 2)
            }
            for it in o.items
        ]

        results.append({
            "id": o.id,
            "order_number": o.order_number,
            "shop_name": o.shop.name,
            "shop_phone": o.shop.phone,
            "order_type": o.order_type,
            "collect_option": o.collect_option,
            "status": o.status,
            "total_amount": o.total_amount,
            "created_at": o.created_at.strftime("%Y-%m-%d %H:%M:%S"),
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
