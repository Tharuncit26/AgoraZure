import io
import base64
import json
from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
import qrcode

from backend.database import get_db
from backend.models import Product, Batch, Bill, BillItem, Shop
from backend.schemas import BillCreateRequest, BillScanBarcodeRequest

router = APIRouter(prefix="/billing", tags=["Billing & Point of Sale"])

# -------------------------------------------------------------------------
# Barcode Lookup for Scanner (Keyboard Input)
# -------------------------------------------------------------------------

@router.post("/scan")
def scan_item(
    payload: BillScanBarcodeRequest,
    shop_id: int = Query(..., description="Shop ID"),
    db: Session = Depends(get_db)
):
    """
    Called when a barcode scanner (keyboard input + Enter) inputs a barcode.
    Returns product info and current available stock across batches.
    """
    barcode_clean = payload.barcode.strip()
    product = db.query(Product).filter(
        Product.shop_id == shop_id,
        Product.barcode == barcode_clean
    ).first()

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item with barcode '{barcode_clean}' not found in your catalog."
        )

    batches = db.query(Batch).filter(
        Batch.product_id == product.id,
        Batch.quantity > 0
    ).order_by(Batch.expiry_date.asc()).all()

    total_stock = sum(b.quantity for b in batches)

    return {
        "success": True,
        "product": {
            "id": product.id,
            "name": product.name,
            "barcode": product.barcode,
            "price": product.price,
            "category": product.category,
            "available_stock": total_stock,
            "session_tab": payload.session_tab
        }
    }

# -------------------------------------------------------------------------
# UPI QR Generation (Prototype Payment)
# -------------------------------------------------------------------------

@router.get("/upi-qr")
def generate_upi_qr(
    amount: float = Query(..., gt=0, description="Bill total in INR"),
    shop_id: int = Query(..., description="Shop ID"),
    db: Session = Depends(get_db)
):
    """
    Generates a UPI QR code image (Base64 data URI) for the bill amount.
    Prototype QR code compatible with UPI apps (GPay, PhonePe, Paytm).
    """
    shop = db.query(Shop).filter(Shop.id == shop_id).first()
    shop_name = shop.name if shop else "AgoraZure Store"
    upi_id = f"{shop.phone if shop else 'merchant'}@upi"

    upi_uri = f"upi://pay?pa={upi_id}&pn={shop_name.replace(' ', '%20')}&am={amount:.2f}&cu=INR&tn=AgoraZure%20Bill"

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=4,
    )
    qr.add_data(upi_uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1e293b", back_color="#ffffff")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64_qr = base64.b64encode(buf.getvalue()).decode("utf-8")

    return {
        "success": True,
        "upi_uri": upi_uri,
        "qr_base64": f"data:image/png;base64,{b64_qr}",
        "amount": amount,
        "merchant": shop_name,
        "upi_id": upi_id
    }

# -------------------------------------------------------------------------
# Confirm Bill & FEFO Automatic Stock Deduction
# -------------------------------------------------------------------------

@router.post("/confirm")
def confirm_bill(
    payload: BillCreateRequest,
    shop_id: int = Query(..., description="Shop ID"),
    db: Session = Depends(get_db)
):
    """
    Finalizes the bill (Cash or confirmed UPI payment):
    1. Reduces stock AUTOMATICALLY using FEFO (First-Expired, First-Out: oldest batch sold first).
    2. Records bill & bill items with batch audit deductions.
    3. Generates a Digital Receipt.
    """
    shop = db.query(Shop).filter(Shop.id == shop_id).first()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found.")

    if not payload.items:
        raise HTTPException(status_code=400, detail="Cannot create an empty bill.")

    total_amount = 0.0
    bill_number = f"BILL-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

    new_bill = Bill(
        shop_id=shop_id,
        bill_number=bill_number,
        session_tab=payload.session_tab,
        total_amount=0.0,
        payment_method=payload.payment_method,
        payment_status="completed"
    )
    db.add(new_bill)
    db.flush()

    receipt_items = []

    for item_data in payload.items:
        product = db.query(Product).filter(
            Product.id == item_data.product_id,
            Product.shop_id == shop_id
        ).first()

        if not product:
            raise HTTPException(
                status_code=404,
                detail=f"Product ID {item_data.product_id} not found."
            )

        needed_qty = item_data.quantity
        if needed_qty <= 0:
            continue

        # Fetch batches ordered by expiry_date ASC (FEFO: Nearest Expiry Sold First)
        batches = db.query(Batch).filter(
            Batch.product_id == product.id,
            Batch.quantity > 0
        ).order_by(Batch.expiry_date.asc()).all()

        available_stock = sum(b.quantity for b in batches)
        if available_stock < needed_qty:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient stock for '{product.name}'. Requested: {needed_qty}, Available: {available_stock}"
            )

        # Deduct across batches using FEFO
        remaining_to_deduct = needed_qty
        batch_deductions = []

        for b in batches:
            if remaining_to_deduct == 0:
                break
            deduct = min(b.quantity, remaining_to_deduct)
            b.quantity -= deduct
            remaining_to_deduct -= deduct
            batch_deductions.append({
                "batch_id": b.id,
                "batch_number": b.batch_number,
                "expiry_date": b.expiry_date,
                "quantity_deducted": deduct
            })

        line_subtotal = round(product.price * needed_qty, 2)
        total_amount += line_subtotal

        bill_item = BillItem(
            bill_id=new_bill.id,
            product_id=product.id,
            quantity=needed_qty,
            unit_price=product.price,
            batch_deductions_json=json.dumps(batch_deductions)
        )
        db.add(bill_item)

        receipt_items.append({
            "product_name": product.name,
            "barcode": product.barcode,
            "quantity": needed_qty,
            "unit_price": product.price,
            "subtotal": line_subtotal,
            "batches_used": [f"{bd['batch_number']} (Exp: {bd['expiry_date']})" for bd in batch_deductions]
        })

    new_bill.total_amount = round(total_amount, 2)
    db.commit()
    db.refresh(new_bill)

    # Return digital receipt
    digital_receipt = {
        "bill_id": new_bill.id,
        "bill_number": new_bill.bill_number,
        "session_tab": new_bill.session_tab,
        "timestamp": new_bill.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        "shop": {
            "name": shop.name,
            "phone": shop.phone,
            "address": shop.address,
            "owner": shop.owner_name
        },
        "items": receipt_items,
        "total_amount": new_bill.total_amount,
        "payment_method": new_bill.payment_method.upper(),
        "payment_status": "PAID"
    }

    return {
        "success": True,
        "message": "Bill confirmed! Stock reduced automatically using FEFO.",
        "receipt": digital_receipt
    }

# -------------------------------------------------------------------------
# Retrieve Receipts
# -------------------------------------------------------------------------

@router.get("/receipt/{bill_number}")
def get_receipt(bill_number: str, db: Session = Depends(get_db)):
    """Fetch digital receipt by bill number."""
    bill = db.query(Bill).filter(Bill.bill_number == bill_number.strip()).first()
    if not bill:
        raise HTTPException(status_code=404, detail="Receipt not found.")

    shop = db.query(Shop).filter(Shop.id == bill.shop_id).first()

    items = []
    for bi in bill.items:
        items.append({
            "product_name": bi.product.name,
            "barcode": bi.product.barcode,
            "quantity": bi.quantity,
            "unit_price": bi.unit_price,
            "subtotal": round(bi.quantity * bi.unit_price, 2),
            "batches_deducted": json.loads(bi.batch_deductions_json or "[]")
        })

    return {
        "success": True,
        "receipt": {
            "bill_id": bill.id,
            "bill_number": bill.bill_number,
            "session_tab": bill.session_tab,
            "timestamp": bill.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "shop": {
                "name": shop.name if shop else "Shop",
                "phone": shop.phone if shop else "",
                "address": shop.address if shop else "",
                "owner": shop.owner_name if shop else ""
            },
            "items": items,
            "total_amount": bill.total_amount,
            "payment_method": bill.payment_method.upper(),
            "payment_status": bill.payment_status.upper()
        }
    }
