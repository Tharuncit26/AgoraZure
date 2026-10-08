from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import Product, Batch, Shop, MissedSearch, Notification
from backend.schemas import ProductCreateRequest, ProductUpdateRequest, BatchCreateRequest

router = APIRouter(prefix="/stock", tags=["Stock Management"])

def trigger_notify_back_for_product(db: Session, product_name: str, shop_name: str):
    """
    Unmet Demand Loop - Notify-Back:
    When a product is added or new stock arrives, find shoppers who previously
    searched for this item and were logged in missed_searches, and generate
    in-app notifications for them.
    """
    prod_lower = product_name.lower().strip()
    # Find matching unresolved missed searches
    unresolved = db.query(MissedSearch).filter(
        MissedSearch.resolved == False,
        MissedSearch.shopper_id.isnot(None)
    ).all()

    for ms in unresolved:
        q_lower = ms.query_text.lower().strip()
        # If query is substring of product name or vice-versa
        if q_lower in prod_lower or prod_lower in q_lower:
            # Create notification
            notif = Notification(
                shopper_id=ms.shopper_id,
                title="Item Now in Stock!",
                message=f"Good news! '{product_name}' that you previously searched for has just arrived at {shop_name}."
            )
            db.add(notif)
            ms.resolved = True

    db.commit()

# -------------------------------------------------------------------------
# Product & Batch Retrieval
# -------------------------------------------------------------------------

@router.get("/products")
def list_products(
    shop_id: int = Query(..., description="Shop ID to filter stock for"),
    db: Session = Depends(get_db)
):
    """
    Lists all products for a shop with live total quantity across all batches,
    nearest expiry date, and batch breakdown.
    """
    products = db.query(Product).filter(Product.shop_id == shop_id).all()
    results = []

    for p in products:
        batches = db.query(Batch).filter(
            Batch.product_id == p.id,
            Batch.quantity > 0
        ).order_by(Batch.expiry_date.asc()).all()

        total_qty = sum(b.quantity for b in batches)
        earliest_expiry = batches[0].expiry_date if batches else "No active batches"

        results.append({
            "id": p.id,
            "name": p.name,
            "barcode": p.barcode,
            "price": p.price,
            "category": p.category,
            "low_stock_threshold": p.low_stock_threshold,
            "total_quantity": total_qty,
            "is_low_stock": total_qty <= p.low_stock_threshold,
            "earliest_expiry": earliest_expiry,
            "batches": [
                {
                    "id": b.id,
                    "batch_number": b.batch_number,
                    "quantity": b.quantity,
                    "expiry_date": b.expiry_date
                }
                for b in batches
            ]
        })

    return {"success": True, "products": results}

@router.get("/product/barcode/{barcode}")
def get_product_by_barcode(
    barcode: str,
    shop_id: int = Query(..., description="Shop ID"),
    db: Session = Depends(get_db)
):
    """Lookup a product by its barcode for a specific shop."""
    product = db.query(Product).filter(
        Product.shop_id == shop_id,
        Product.barcode == barcode.strip()
    ).first()

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No product with barcode '{barcode}' found in this shop."
        )

    batches = db.query(Batch).filter(
        Batch.product_id == product.id,
        Batch.quantity > 0
    ).order_by(Batch.expiry_date.asc()).all()

    total_qty = sum(b.quantity for b in batches)

    return {
        "success": True,
        "product": {
            "id": product.id,
            "name": product.name,
            "barcode": product.barcode,
            "price": product.price,
            "category": product.category,
            "low_stock_threshold": product.low_stock_threshold,
            "total_quantity": total_qty,
            "earliest_expiry": batches[0].expiry_date if batches else "N/A",
            "batches": [
                {
                    "id": b.id,
                    "batch_number": b.batch_number,
                    "quantity": b.quantity,
                    "expiry_date": b.expiry_date
                }
                for b in batches
            ]
        }
    }

# -------------------------------------------------------------------------
# Product Creation & Editing
# -------------------------------------------------------------------------

@router.post("/product")
def add_product(
    payload: ProductCreateRequest,
    shop_id: int = Query(..., description="Shop ID"),
    db: Session = Depends(get_db)
):
    """
    Adds a new product and creates its initial stock batch if quantity > 0.
    Triggers notify-back to shoppers if matching unmet demand exists.
    """
    shop = db.query(Shop).filter(Shop.id == shop_id).first()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found.")

    existing = db.query(Product).filter(
        Product.shop_id == shop_id,
        Product.barcode == payload.barcode.strip()
    ).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Product with barcode '{payload.barcode}' already exists. Use 'Add Batch' instead."
        )

    new_prod = Product(
        shop_id=shop_id,
        name=payload.name.strip(),
        barcode=payload.barcode.strip(),
        price=payload.price,
        category=payload.category.strip() if payload.category else "General",
        low_stock_threshold=payload.low_stock_threshold or 5
    )
    db.add(new_prod)
    db.flush()

    # Create initial batch if quantity > 0
    if payload.initial_quantity and payload.initial_quantity > 0:
        batch_num = f"B-{datetime.utcnow().strftime('%y%m%d%H%M')}"
        new_batch = Batch(
            product_id=new_prod.id,
            shop_id=shop_id,
            batch_number=batch_num,
            quantity=payload.initial_quantity,
            expiry_date=payload.expiry_date or "2026-12-31"
        )
        db.add(new_batch)

    db.commit()
    db.refresh(new_prod)

    # Check unmet-demand loop notify-back
    trigger_notify_back_for_product(db, new_prod.name, shop.name)

    return {
        "success": True,
        "message": f"Product '{new_prod.name}' registered successfully!",
        "product_id": new_prod.id
    }

@router.put("/product/{product_id}")
def update_product(
    product_id: int,
    payload: ProductUpdateRequest,
    shop_id: int = Query(..., description="Shop ID"),
    db: Session = Depends(get_db)
):
    """Edits product details (name, price, category, low stock threshold)."""
    product = db.query(Product).filter(
        Product.id == product_id,
        Product.shop_id == shop_id
    ).first()

    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")

    if payload.name is not None:
        product.name = payload.name.strip()
    if payload.price is not None:
        product.price = payload.price
    if payload.category is not None:
        product.category = payload.category.strip()
    if payload.low_stock_threshold is not None:
        product.low_stock_threshold = payload.low_stock_threshold

    db.commit()
    return {"success": True, "message": "Product updated successfully."}

# -------------------------------------------------------------------------
# Add Goods / New Batch
# -------------------------------------------------------------------------

@router.post("/batch")
def add_batch(
    payload: BatchCreateRequest,
    shop_id: int = Query(..., description="Shop ID"),
    db: Session = Depends(get_db)
):
    """
    Adds a new batch when new goods arrive:
    Scan barcode -> enter quantity + hand-entered expiry date -> batch added.
    """
    shop = db.query(Shop).filter(Shop.id == shop_id).first()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found.")

    product = db.query(Product).filter(
        Product.shop_id == shop_id,
        Product.barcode == payload.barcode.strip()
    ).first()

    if not product:
        raise HTTPException(
            status_code=404,
            detail=f"No product with barcode '{payload.barcode}' found. Please add the product first."
        )

    batch_num = payload.batch_number or f"B-{datetime.utcnow().strftime('%y%m%d%H%M')}"
    new_batch = Batch(
        product_id=product.id,
        shop_id=shop_id,
        batch_number=batch_num,
        quantity=payload.quantity,
        expiry_date=payload.expiry_date.strip()
    )
    db.add(new_batch)
    db.commit()

    # Trigger notify-back
    trigger_notify_back_for_product(db, product.name, shop.name)

    return {
        "success": True,
        "message": f"Batch of {payload.quantity} units added for '{product.name}' (Expires: {payload.expiry_date})",
        "batch_id": new_batch.id,
        "product_name": product.name
    }
