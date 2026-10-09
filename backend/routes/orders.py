from datetime import datetime
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Order, OrderItem, Shop, Shopper, Product, Batch, LoyaltyPoint, Offer
from backend.schemas import OrderCreateRequest, OrderStatusUpdateRequest

router = APIRouter(prefix="/orders", tags=["Online Orders & Tracking"])

VALID_STATUSES = [
    "pending", "accepted", "preparing", "ready", "out_for_delivery",
    "delivered", "rejected", "cancelled", "picked_up", "completed"
]

STATUS_DISPLAY = {
    "pending": "Order Placed",
    "accepted": "Order Accepted",
    "preparing": "Preparing & Packing",
    "ready": "Ready for Pickup",
    "out_for_delivery": "Out for Delivery",
    "delivered": "Delivered",
    "picked_up": "Delivered",
    "completed": "Delivered",
    "rejected": "Rejected",
    "cancelled": "Cancelled"
}

# -------------------------------------------------------------------------
# Create Online Order (Shopper)
# -------------------------------------------------------------------------

@router.post("/create")
def create_order(
    payload: OrderCreateRequest,
    shopper_id: int = Query(..., description="Shopper ID"),
    db: Session = Depends(get_db)
):
    """
    Shopper places an order with delivery address, collect option, and payment method.
    Calculates item subtotal, delivery fee, taxes, and applies active seasonal offers.
    Saves order and all items transactionally in the database.
    """
    shopper = db.query(Shopper).filter(Shopper.id == shopper_id).first()
    if not shopper:
        raise HTTPException(status_code=404, detail="Shopper account not found.")

    shop = db.query(Shop).filter(Shop.id == payload.shop_id).first()
    if not shop:
        raise HTTPException(status_code=404, detail="Selected shop not found.")

    if not shop.is_open:
        raise HTTPException(
            status_code=400,
            detail=f"{shop.name} is currently closed. Please order from another nearby store."
        )

    if not payload.items or len(payload.items) == 0:
        raise HTTPException(status_code=400, detail="Cannot place an empty order. Please add items.")

    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    order_num = f"AZ-{datetime.utcnow().strftime('%Y%m%d%H%M')}-{uuid.uuid4().hex[:4].upper()}"

    # Calculate delivery fee: 25 for home delivery, 0 for pickup
    delivery_fee = 25.0 if payload.collect_option == "home_delivery" else 0.0
    delivery_addr = (payload.delivery_address or shopper.address or "Indiranagar, Bengaluru").strip()

    new_order = Order(
        shopper_id=shopper.id,
        shop_id=shop.id,
        order_number=order_num,
        order_type=payload.order_type or "buy_from_home",
        collect_option=payload.collect_option or "pickup",
        delivery_address=delivery_addr,
        payment_method=payload.payment_method or "Cash on Delivery",
        payment_status="pending",
        status="pending",
        subtotal=0.0,
        delivery_fee=delivery_fee,
        tax_amount=0.0,
        discount_amount=0.0,
        total_amount=0.0
    )
    db.add(new_order)
    db.flush()

    subtotal = 0.0
    discount_total = 0.0

    for item_data in payload.items:
        product = db.query(Product).filter(
            Product.id == item_data.product_id,
            Product.shop_id == payload.shop_id
        ).first()

        if not product:
            raise HTTPException(status_code=404, detail=f"Product #{item_data.product_id} not found in this shop.")

        # Check total active stock across batches
        batches = db.query(Batch).filter(
            Batch.product_id == product.id,
            Batch.quantity > 0
        ).all()
        avail_stock = sum(b.quantity for b in batches)

        if avail_stock < item_data.quantity:
            raise HTTPException(
                status_code=400,
                detail=f"'{product.name}' only has {avail_stock} units available in stock."
            )

        # Check for active seasonal offer
        offer = db.query(Offer).filter(
            Offer.shop_id == payload.shop_id,
            Offer.active == True,
            Offer.valid_from <= today_str,
            Offer.valid_to >= today_str,
            (Offer.product_id == product.id) | (Offer.product_id == None)
        ).order_by(Offer.product_id.desc(), Offer.discount_percent.desc()).first()

        unit_price = product.price
        if offer:
            disc = round(product.price * (offer.discount_percent / 100.0), 2)
            unit_price = round(product.price - disc, 2)
            discount_total += round(disc * item_data.quantity, 2)

        line_subtotal = round(unit_price * item_data.quantity, 2)
        subtotal += line_subtotal

        order_item = OrderItem(
            order_id=new_order.id,
            product_id=product.id,
            quantity=item_data.quantity,
            unit_price=unit_price
        )
        db.add(order_item)

    # 5% GST taxes
    tax = round(subtotal * 0.05, 2)
    grand_total = round(subtotal + delivery_fee + tax, 2)

    new_order.subtotal = round(subtotal, 2)
    new_order.delivery_fee = round(delivery_fee, 2)
    new_order.tax_amount = round(tax, 2)
    new_order.discount_amount = round(discount_total, 2)
    new_order.total_amount = grand_total

    db.commit()
    db.refresh(new_order)

    return {
        "success": True,
        "message": f"Order {new_order.order_number} placed successfully!",
        "order": {
            "id": new_order.id,
            "orderId": new_order.id,
            "order_id": new_order.id,
            "order_number": new_order.order_number,
            "shopId": new_order.shop_id,
            "shop_id": new_order.shop_id,
            "shop_name": shop.name,
            "shop_phone": shop.phone,
            "shopperId": shopper.id,
            "shopper_name": shopper.name,
            "shopper_phone": shopper.phone,
            "delivery_address": new_order.delivery_address,
            "payment_method": new_order.payment_method,
            "order_type": new_order.order_type,
            "collect_option": new_order.collect_option,
            "status": new_order.status,
            "subtotal": new_order.subtotal,
            "delivery_fee": new_order.delivery_fee,
            "tax_amount": new_order.tax_amount,
            "discount_amount": new_order.discount_amount,
            "total_amount": new_order.total_amount,
            "total": new_order.total_amount,
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
    """Shopkeeper views all orders placed for their shop."""
    query = db.query(Order).filter(Order.shop_id == shop_id)
    if status_filter and status_filter.strip():
        st = status_filter.strip().lower()
        if st in ["completed", "delivered", "picked_up"]:
            query = query.filter(Order.status.in_(["delivered", "completed", "picked_up"]))
        else:
            query = query.filter(Order.status == st)

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
            "delivery_address": o.delivery_address or (shopper.address if shopper else ""),
            "payment_method": o.payment_method or "Cash on Delivery",
            "payment_status": o.payment_status or "pending",
            "status": o.status,
            "status_display": STATUS_DISPLAY.get(o.status, o.status.replace("_", " ").capitalize()),
            "reject_reason": o.reject_reason or "",
            "shopper_name": shopper.name if shopper else "Shopper",
            "shopper_phone": shopper.phone if shopper else "",
            "items": items,
            "quantity": total_qty,
            "subtotal": o.subtotal,
            "delivery_fee": o.delivery_fee,
            "tax_amount": o.tax_amount,
            "total": o.total_amount,
            "total_amount": o.total_amount,
            "time": time_str,
            "created_at": time_str,
            "shopper": {
                "id": shopper.id if shopper else None,
                "name": shopper.name if shopper else "Shopper",
                "phone": shopper.phone if shopper else "",
                "address": o.delivery_address or (shopper.address if shopper else "")
            }
        })

    # Summary counts
    counts = {
        "all": len(results),
        "pending": sum(1 for o in results if o["status"] == "pending"),
        "accepted": sum(1 for o in results if o["status"] == "accepted"),
        "preparing": sum(1 for o in results if o["status"] == "preparing"),
        "ready": sum(1 for o in results if o["status"] == "ready"),
        "out_for_delivery": sum(1 for o in results if o["status"] == "out_for_delivery"),
        "delivered": sum(1 for o in results if o["status"] in ["delivered", "completed", "picked_up"]),
        "rejected": sum(1 for o in results if o["status"] in ["rejected", "cancelled"]),
    }

    return {"success": True, "count": len(results), "counts": counts, "orders": results}

@router.put("/status/{order_id}")
def update_order_status(
    order_id: int,
    payload: OrderStatusUpdateRequest,
    shop_id: int = Query(..., description="Shop ID"),
    db: Session = Depends(get_db)
):
    """
    Shopkeeper explicitly and manually updates order status:
    Pending -> Accepted -> Preparing -> Ready -> Out for Delivery -> Delivered (or Rejected with reason).
    NO automatic rejection or timers.
    """
    raw_status = payload.status.strip().lower()
    # Normalize aliases
    if raw_status in ["completed", "picked_up"]:
        new_status = "delivered"
    else:
        new_status = raw_status

    if new_status not in VALID_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{payload.status}'. Must be one of: pending, accepted, preparing, ready, out_for_delivery, delivered, rejected, cancelled."
        )

    order = db.query(Order).filter(
        Order.id == order_id,
        Order.shop_id == shop_id
    ).first()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found for this shop.")

    old_status = order.status.lower()

    # Apply new status
    order.status = new_status
    order.updated_at = datetime.utcnow()

    if new_status in ["rejected", "cancelled"]:
        order.reject_reason = (payload.reject_reason or "Cancelled by store").strip()
    else:
        order.reject_reason = None

    # Stock deductions on transition from pending to active status
    if old_status == "pending" and new_status in ["accepted", "preparing", "ready", "out_for_delivery", "delivered"]:
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

    # Restore stock if rejected after having been accepted/preparing/ready
    if new_status in ["rejected", "cancelled"] and old_status in ["accepted", "preparing", "ready", "out_for_delivery"]:
        for it in order.items:
            batch = db.query(Batch).filter(Batch.product_id == it.product_id).first()
            if batch:
                batch.quantity += it.quantity

    # Award loyalty points when delivered
    if new_status in ["delivered", "completed"] and old_status not in ["delivered", "completed"]:
        order.payment_status = "completed"
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
        "message": f"Order #{order.order_number} status updated to '{STATUS_DISPLAY.get(order.status, order.status)}'.",
        "new_status": order.status,
        "orderId": order.id,
        "status": order.status,
        "reject_reason": order.reject_reason
    }

# -------------------------------------------------------------------------
# Shopper Order History & Live Tracking (Swiggy / Zomato style)
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
            "shop_name": o.shop.name if o.shop else "Neighborhood Store",
            "shop_phone": o.shop.phone if o.shop else "",
            "order_type": o.order_type,
            "collect_option": o.collect_option,
            "delivery_address": o.delivery_address or "",
            "payment_method": o.payment_method or "Cash on Delivery",
            "status": o.status,
            "status_display": STATUS_DISPLAY.get(o.status, o.status.replace("_", " ").capitalize()),
            "reject_reason": o.reject_reason or "",
            "total_amount": o.total_amount,
            "total": o.total_amount,
            "quantity": total_qty,
            "time": time_str,
            "created_at": time_str,
            "items": items
        })

    return {"success": True, "orders": results}

@router.get("/track/{order_id}")
def get_order_tracking(order_id: int, db: Session = Depends(get_db)):
    """
    Live order tracking endpoint for shopper (Swiggy / Zomato style):
    Returns current stage, step timeline, shop contact, and details.
    """
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")

    shop = order.shop
    shopper = order.shopper
    status_lower = order.status.lower()

    # Canonical status sequence
    # Placed -> Accepted -> Preparing -> Out for Delivery / Ready for Pickup -> Delivered
    is_home_del = (order.collect_option == "home_delivery")
    stage_4_title = "Out for Delivery" if is_home_del else "Ready for Pickup"

    all_steps = [
        {"key": "pending", "title": "Order Placed", "desc": "Order received and sent to store"},
        {"key": "accepted", "title": "Order Accepted", "desc": f"{shop.name if shop else 'Store'} confirmed your order"},
        {"key": "preparing", "title": "Preparing Items", "desc": "Items are being packed with care"},
        {"key": "ready_or_out", "title": stage_4_title, "desc": "Rider en route" if is_home_del else "Ready at counter for pickup"},
        {"key": "delivered", "title": "Delivered", "desc": "Order delivered successfully"}
    ]

    status_index_map = {
        "pending": 0,
        "accepted": 1,
        "preparing": 2,
        "ready": 3,
        "out_for_delivery": 3,
        "ready_or_out": 3,
        "delivered": 4,
        "picked_up": 4,
        "completed": 4,
        "rejected": -1,
        "cancelled": -1
    }

    current_idx = status_index_map.get(status_lower, 0)
    is_failed = status_lower in ["rejected", "cancelled"]

    timeline = []
    for idx, step in enumerate(all_steps):
        if is_failed:
            timeline.append({
                "step": idx + 1,
                "title": step["title"],
                "desc": step["desc"],
                "completed": False,
                "current": False
            })
        else:
            timeline.append({
                "step": idx + 1,
                "title": step["title"],
                "desc": step["desc"],
                "completed": idx <= current_idx,
                "current": idx == current_idx
            })

    items = [
        {
            "product_name": it.product.name if it.product else f"Product #{it.product_id}",
            "quantity": it.quantity,
            "unit_price": it.unit_price,
            "subtotal": round(it.quantity * it.unit_price, 2)
        }
        for it in order.items
    ]

    return {
        "success": True,
        "order": {
            "id": order.id,
            "order_number": order.order_number,
            "status": order.status,
            "status_display": STATUS_DISPLAY.get(order.status, order.status),
            "is_rejected": is_failed,
            "reject_reason": order.reject_reason or "",
            "collect_option": order.collect_option,
            "order_type": order.order_type,
            "delivery_address": order.delivery_address or (shopper.address if shopper else ""),
            "payment_method": order.payment_method or "Cash on Delivery",
            "subtotal": order.subtotal,
            "delivery_fee": order.delivery_fee,
            "tax_amount": order.tax_amount,
            "discount_amount": order.discount_amount,
            "total_amount": order.total_amount,
            "created_at": order.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": order.updated_at.strftime("%Y-%m-%d %H:%M:%S") if order.updated_at else "",
            "shop": {
                "id": shop.id if shop else None,
                "name": shop.name if shop else "Store",
                "phone": shop.phone if shop else "",
                "address": shop.address if shop else ""
            },
            "shopper": {
                "id": shopper.id if shopper else None,
                "name": shopper.name if shopper else "Shopper",
                "phone": shopper.phone if shopper else ""
            },
            "items": items,
            "timeline": timeline,
            "current_step_index": current_idx
        }
    }

# -------------------------------------------------------------------------
# Digital Receipt
# -------------------------------------------------------------------------

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
            "product_name": it.product.name if it.product else f"Product #{it.product_id}",
            "quantity": it.quantity,
            "unit_price": it.unit_price,
            "subtotal": round(it.quantity * it.unit_price, 2)
        }
        for it in order.items
    ]

    return {
        "success": True,
        "receipt": {
            "order_id": order.id,
            "order_number": order.order_number,
            "order_type": order.order_type,
            "collect_option": order.collect_option,
            "delivery_address": order.delivery_address or (shopper.address if shopper else ""),
            "payment_method": order.payment_method or "Cash on Delivery",
            "payment_status": order.payment_status or "pending",
            "status": order.status,
            "status_display": STATUS_DISPLAY.get(order.status, order.status),
            "reject_reason": order.reject_reason or "",
            "timestamp": order.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "shop": {
                "name": shop.name if shop else "Store",
                "phone": shop.phone if shop else "",
                "address": shop.address if shop else ""
            },
            "shopper": {
                "name": shopper.name if shopper else "Shopper",
                "phone": shopper.phone if shopper else "",
                "address": order.delivery_address or (shopper.address if shopper else "")
            },
            "items": items,
            "subtotal": order.subtotal,
            "delivery_fee": order.delivery_fee,
            "tax_amount": order.tax_amount,
            "discount_amount": order.discount_amount,
            "total_amount": order.total_amount
        }
    }
