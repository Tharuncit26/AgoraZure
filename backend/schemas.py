from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field

# =========================================================================
# AUTH & PROFILE SCHEMAS
# =========================================================================

class ShopRegisterRequest(BaseModel):
    shop_name: str
    owner_name: str
    phone: str
    email: Optional[str] = None
    password: str
    address: str
    category: Optional[str] = "Grocery & Supermarket"
    opening_hours: Optional[str] = "7:00 AM - 10:00 PM"
    photo_url: Optional[str] = None
    latitude: float = 12.9716
    longitude: float = 77.5946

class ShopUpdateRequest(BaseModel):
    shop_name: Optional[str] = None
    owner_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    category: Optional[str] = None
    opening_hours: Optional[str] = None
    photo_url: Optional[str] = None
    is_open: Optional[bool] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class ShopToggleOpenRequest(BaseModel):
    is_open: bool

class ShopperRegisterRequest(BaseModel):
    name: str
    phone: str
    email: Optional[str] = None
    password: str
    address: str
    latitude: float = 12.9716
    longitude: float = 77.5946

class ShopperUpdateRequest(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class LoginRequest(BaseModel):
    phone: Optional[str] = None
    email: Optional[str] = None
    password: str

# =========================================================================
# STOCK & PRODUCT SCHEMAS
# =========================================================================

class ProductCreateRequest(BaseModel):
    name: str
    barcode: Optional[str] = None
    price: float
    mrp: Optional[float] = None
    unit: Optional[str] = "1 pc"
    category: Optional[str] = "General"
    brand: Optional[str] = "General"
    description: Optional[str] = None
    image_url: Optional[str] = None
    low_stock_threshold: Optional[int] = 5
    initial_quantity: Optional[int] = 0
    expiry_date: Optional[str] = "2027-12-31"
    is_available: Optional[bool] = True

class ProductUpdateRequest(BaseModel):
    name: Optional[str] = None
    barcode: Optional[str] = None
    price: Optional[float] = None
    mrp: Optional[float] = None
    unit: Optional[str] = None
    category: Optional[str] = None
    brand: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    low_stock_threshold: Optional[int] = None
    is_available: Optional[bool] = None

class ProductStockUpdateRequest(BaseModel):
    quantity: int
    expiry_date: Optional[str] = None

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
    session_tab: str = "tab_1"
    payment_method: str = "cash"
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
    delivery_address: Optional[str] = None
    payment_method: Optional[str] = "Cash on Delivery"
    items: List[OrderItemPayload]

class OrderStatusUpdateRequest(BaseModel):
    status: str  # pending, accepted, preparing, ready, out_for_delivery, delivered, rejected, cancelled
    reject_reason: Optional[str] = None

# =========================================================================
# OFFERS SCHEMAS
# =========================================================================

class OfferCreateRequest(BaseModel):
    product_id: Optional[int] = None
    title: str
    discount_percent: float
    valid_from: str
    valid_to: str
    banner_text: Optional[str] = None

class OfferUpdateRequest(BaseModel):
    product_id: Optional[int] = None
    title: Optional[str] = None
    discount_percent: Optional[float] = None
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None
    banner_text: Optional[str] = None
    active: Optional[bool] = None

# =========================================================================
# MISSED SEARCH SCHEMAS
# =========================================================================

class MissedSearchLogRequest(BaseModel):
    query_text: str
