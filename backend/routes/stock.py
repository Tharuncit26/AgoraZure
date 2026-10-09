import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import Product, Batch, Shop, MissedSearch, Notification
from backend.schemas import (
    ProductCreateRequest, ProductUpdateRequest, ProductStockUpdateRequest,
    BatchCreateRequest, ShrinkageCheckRequest
)

router = APIRouter(prefix="/stock", tags=["Stock Management"])

def trigger_notify_back_for_product(db: Session, product_name: str, shop_name: str):
    """
    Unmet Demand Loop - Notify-Back:
    When a product is added or new stock arrives, find shoppers who previously
    searched for this item and generate in-app notifications for them.
    """
    prod_lower = product_name.lower().strip()
    unresolved = db.query(MissedSearch).filter(
        MissedSearch.resolved == False,
        MissedSearch.shopper_id.isnot(None)
    ).all()

    for ms in unresolved:
        q_lower = ms.query_text.lower().strip()
        if q_lower in prod_lower or prod_lower in q_lower:
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
    category: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Lists all products for a shop with live total quantity across all batches,
    nearest expiry date, and batch breakdown.
    """
    query = db.query(Product).filter(Product.shop_id == shop_id)
    if category and category != "All":
        query = query.filter(Product.category == category.strip())

    products = query.order_by(Product.name.asc()).all()
    results = []

    for p in products:
        batches = db.query(Batch).filter(
            Batch.product_id == p.id,
            Batch.quantity > 0
        ).order_by(Batch.expiry_date.asc()).all()

        total_qty = sum(b.quantity for b in batches)
        earliest_expiry = batches[0].expiry_date if batches else "No active batches"
        is_low_stock = total_qty <= (p.low_stock_threshold or 5)
        in_stock = total_qty > 0 and (p.is_available is not False)

        if status_filter == "in_stock" and not in_stock:
            continue
        if status_filter == "low_stock" and not is_low_stock:
            continue
        if status_filter == "out_of_stock" and total_qty > 0:
            continue

        results.append({
            "id": p.id,
            "product_id": p.id,
            "shop_id": p.shop_id,
            "name": p.name,
            "barcode": p.barcode,
            "brand": p.brand or "General",
            "category": p.category or "General",
            "description": p.description or "",
            "price": p.price,
            "mrp": p.mrp if p.mrp is not None else round(p.price * 1.15, 2),
            "unit": p.unit or "1 pc",
            "image_url": p.image_url or "",
            "is_available": p.is_available if p.is_available is not None else True,
            "low_stock_threshold": p.low_stock_threshold or 5,
            "total_quantity": total_qty,
            "stock": total_qty,
            "is_low_stock": is_low_stock,
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

    return {"success": True, "count": len(results), "products": results}

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
            "brand": product.brand or "General",
            "category": product.category or "General",
            "description": product.description or "",
            "price": product.price,
            "mrp": product.mrp if product.mrp is not None else round(product.price * 1.15, 2),
            "unit": product.unit or "1 pc",
            "image_url": product.image_url or "",
            "is_available": product.is_available if product.is_available is not None else True,
            "low_stock_threshold": product.low_stock_threshold,
            "total_quantity": total_qty,
            "stock": total_qty,
            "earliest_expiry": batches[0].expiry_date if batches else "N/A"
        }
    }

# -------------------------------------------------------------------------
# Product Creation, Editing, Stock Update & Delete
# -------------------------------------------------------------------------

@router.post("/product")
def add_product(
    payload: ProductCreateRequest,
    shop_id: int = Query(..., description="Shop ID"),
    db: Session = Depends(get_db)
):
    """
    Adds a new product and creates its initial stock batch.
    Triggers notify-back to shoppers if matching unmet demand exists.
    """
    shop = db.query(Shop).filter(Shop.id == shop_id).first()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found.")

    # Generate barcode if missing
    barcode_val = payload.barcode.strip() if payload.barcode and payload.barcode.strip() else f"890{uuid.uuid4().int % 1000000000:09d}"

    existing = db.query(Product).filter(
        Product.shop_id == shop_id,
        Product.barcode == barcode_val
    ).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Product with barcode '{barcode_val}' already exists. Please choose a unique barcode or edit existing."
        )

    new_prod = Product(
        shop_id=shop_id,
        name=payload.name.strip(),
        barcode=barcode_val,
        brand=payload.brand.strip() if payload.brand else "General",
        category=payload.category.strip() if payload.category else "General",
        description=payload.description.strip() if payload.description else "",
        price=float(payload.price),
        mrp=float(payload.mrp) if payload.mrp is not None else round(float(payload.price) * 1.15, 2),
        unit=payload.unit.strip() if payload.unit else "1 pc",
        image_url=payload.image_url.strip() if payload.image_url else None,
        is_available=payload.is_available if payload.is_available is not None else True,
        low_stock_threshold=payload.low_stock_threshold or 5
    )
    db.add(new_prod)
    db.flush()

    # Create initial batch
    initial_qty = payload.initial_quantity if payload.initial_quantity is not None else 10
    if initial_qty > 0:
        batch_num = f"B-{datetime.utcnow().strftime('%y%m%d%H%M')}"
        new_batch = Batch(
            product_id=new_prod.id,
            shop_id=shop_id,
            batch_number=batch_num,
            quantity=initial_qty,
            expiry_date=payload.expiry_date or "2027-12-31"
        )
        db.add(new_batch)

    db.commit()
    db.refresh(new_prod)

    # Check unmet-demand loop notify-back
    try:
        trigger_notify_back_for_product(db, new_prod.name, shop.name)
    except Exception:
        pass

    return {
        "success": True,
        "message": f"Product '{new_prod.name}' registered successfully!",
        "product_id": new_prod.id,
        "product": {
            "id": new_prod.id,
            "name": new_prod.name,
            "barcode": new_prod.barcode,
            "brand": new_prod.brand,
            "category": new_prod.category,
            "price": new_prod.price,
            "mrp": new_prod.mrp,
            "unit": new_prod.unit,
            "image_url": new_prod.image_url or "",
            "is_available": new_prod.is_available,
            "total_quantity": initial_qty
        }
    }

@router.put("/product/{product_id}")
def update_product(
    product_id: int,
    payload: ProductUpdateRequest,
    shop_id: int = Query(..., description="Shop ID"),
    db: Session = Depends(get_db)
):
    """Edits all product details (name, price, MRP, unit, category, brand, description, image, is_available)."""
    product = db.query(Product).filter(
        Product.id == product_id,
        Product.shop_id == shop_id
    ).first()

    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")

    if payload.name is not None:
        product.name = payload.name.strip()
    if payload.barcode is not None:
        product.barcode = payload.barcode.strip()
    if payload.price is not None:
        product.price = float(payload.price)
    if payload.mrp is not None:
        product.mrp = float(payload.mrp)
    if payload.unit is not None:
        product.unit = payload.unit.strip()
    if payload.category is not None:
        product.category = payload.category.strip()
    if payload.brand is not None:
        product.brand = payload.brand.strip()
    if payload.description is not None:
        product.description = payload.description.strip()
    if payload.image_url is not None:
        product.image_url = payload.image_url.strip()
    if payload.is_available is not None:
        product.is_available = payload.is_available
    if payload.low_stock_threshold is not None:
        product.low_stock_threshold = payload.low_stock_threshold

    db.commit()
    db.refresh(product)

    return {
        "success": True,
        "message": f"Product '{product.name}' updated successfully.",
        "product": {
            "id": product.id,
            "name": product.name,
            "brand": product.brand,
            "category": product.category,
            "price": product.price,
            "mrp": product.mrp,
            "unit": product.unit,
            "image_url": product.image_url or "",
            "is_available": product.is_available
        }
    }

@router.delete("/product/{product_id}")
def delete_product(
    product_id: int,
    shop_id: int = Query(..., description="Shop ID"),
    db: Session = Depends(get_db)
):
    """Deletes a product and its associated batches."""
    product = db.query(Product).filter(
        Product.id == product_id,
        Product.shop_id == shop_id
    ).first()

    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")

    prod_name = product.name
    # Delete batches
    db.query(Batch).filter(Batch.product_id == product.id).delete()
    db.delete(product)
    db.commit()

    return {
        "success": True,
        "message": f"Product '{prod_name}' has been deleted successfully."
    }

@router.put("/product/{product_id}/stock")
def update_product_stock(
    product_id: int,
    payload: ProductStockUpdateRequest,
    shop_id: int = Query(..., description="Shop ID"),
    db: Session = Depends(get_db)
):
    """Quick update product stock quantity."""
    product = db.query(Product).filter(
        Product.id == product_id,
        Product.shop_id == shop_id
    ).first()

    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")

    target_qty = max(0, payload.quantity)
    batch = db.query(Batch).filter(
        Batch.product_id == product.id,
        Batch.shop_id == shop_id
    ).order_by(Batch.expiry_date.desc()).first()

    if batch:
        batch.quantity = target_qty
        if payload.expiry_date:
            batch.expiry_date = payload.expiry_date.strip()
    else:
        new_batch = Batch(
            product_id=product.id,
            shop_id=shop_id,
            batch_number=f"B-{datetime.utcnow().strftime('%y%m%d%H%M')}",
            quantity=target_qty,
            expiry_date=payload.expiry_date or "2027-12-31"
        )
        db.add(new_batch)

    # If stock is positive, mark product available
    if target_qty > 0:
        product.is_available = True

    db.commit()

    return {
        "success": True,
        "message": f"Stock for '{product.name}' updated to {target_qty} units.",
        "product_id": product.id,
        "stock": target_qty
    }

@router.put("/product/{product_id}/toggle-availability")
def toggle_product_availability(
    product_id: int,
    shop_id: int = Query(..., description="Shop ID"),
    db: Session = Depends(get_db)
):
    """Toggle in-stock / out-of-stock availability."""
    product = db.query(Product).filter(
        Product.id == product_id,
        Product.shop_id == shop_id
    ).first()

    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")

    product.is_available = not (product.is_available if product.is_available is not None else True)
    db.commit()

    status_str = "In Stock" if product.is_available else "Out of Stock"
    return {
        "success": True,
        "message": f"Product '{product.name}' is now {status_str}.",
        "is_available": product.is_available
    }

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
    product.is_available = True
    db.commit()

    try:
        trigger_notify_back_for_product(db, product.name, shop.name)
    except Exception:
        pass

    return {
        "success": True,
        "message": f"Batch of {payload.quantity} units added for '{product.name}' (Expires: {payload.expiry_date})",
        "batch_id": new_batch.id,
        "product_name": product.name
    }
