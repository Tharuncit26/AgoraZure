from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field

# =========================================================================
# AUTH SCHEMAS
# =========================================================================

class ShopRegisterRequest(BaseModel):
    shop_name: str
    owner_name: str
    phone: str
    password: str
    address: str
    latitude: float
    longitude: float

class LoginRequest(BaseModel):
    phone: str
    password: str

class ShopperRegisterRequest(BaseModel):
    name: str
    phone: str
    password: str
    address: str
    latitude: float = 12.9716
    longitude: float = 77.5946

# =========================================================================
# STOCK & BATCH SCHEMAS
# =========================================================================

class ProductCreateRequest(BaseModel):
    name: str
    barcode: str
    price: float
    category: Optional[str] = "General"
    low_stock_threshold: Optional[int] = 5
    initial_quantity: Optional[int] = 0
    expiry_date: Optional[str] = "2026-12-31"  # Hand entered expiry date

class ProductUpdateRequest(BaseModel):
    name: Optional[str] = None
    price: Optional[float] = None
    category: Optional[str] = None
    low_stock_threshold: Optional[int] = None

class BatchCreateRequest(BaseModel):
    barcode: str
    quantity: int
    expiry_date: str  # Format: YYYY-MM-DD
    batch_number: Optional[str] = None

class ShrinkageCheckRequest(BaseModel):
    product_id: int
    counted_quantity: int

# =========================================================================
# BILLING SCHEMAS (SCAN & BILL)
# =========================================================================

class BillItemPayload(BaseModel):
    product_id: int
    quantity: int

class BillCreateRequest(BaseModel):
    session_tab: str = "tab_1"  # Support two open bills: tab_1 or tab_2
    payment_method: str = "cash"  # cash or upi
    items: List[BillItemPayload]

class BillScanBarcodeRequest(BaseModel):
    barcode: str
    session_tab: str = "tab_1"

# =========================================================================
# ORDERS SCHEMAS
# =========================================================================

class OrderItemPayload(BaseModel):
    product_id: int
    quantity: int

class OrderCreateRequest(BaseModel):
    shop_id: int
    order_type: str = "buy_from_home"  # prebook or buy_from_home
    collect_option: str = "pickup"      # pickup or home_delivery
    items: List[OrderItemPayload]

class OrderStatusUpdateRequest(BaseModel):
    status: str  # accepted, ready, picked_up, out_for_delivery, completed

# =========================================================================
# OFFERS SCHEMAS
# =========================================================================

class OfferCreateRequest(BaseModel):
    product_id: Optional[int] = None
    title: str
    discount_percent: float
    valid_from: str
    valid_to: str

# =========================================================================
# MISSED SEARCH SCHEMAS
# =========================================================================

class MissedSearchLogRequest(BaseModel):
    query_text: str
