from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
)
from sqlalchemy.orm import relationship
from backend.database import Base

class DeliveryCluster(Base):
    __tablename__ = "delivery_clusters"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    shops = relationship("Shop", back_populates="cluster")
    delivery_persons = relationship("DeliveryPerson", back_populates="cluster")


class DeliveryPerson(Base):
    __tablename__ = "delivery_persons"

    id = Column(Integer, primary_key=True, index=True)
    cluster_id = Column(Integer, ForeignKey("delivery_clusters.id"), nullable=False)
    name = Column(String(100), nullable=False)
    phone = Column(String(20), nullable=False)
    monthly_salary = Column(Float, default=12000.0)
    status = Column(String(50), default="active")
    created_at = Column(DateTime, default=datetime.utcnow)

    cluster = relationship("DeliveryCluster", back_populates="delivery_persons")


class Shop(Base):
    __tablename__ = "shops"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    owner_name = Column(String(100), nullable=False)
    phone = Column(String(20), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    address = Column(String(255), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    cluster_id = Column(Integer, ForeignKey("delivery_clusters.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    cluster = relationship("DeliveryCluster", back_populates="shops")
    shopkeepers = relationship("Shopkeeper", back_populates="shop")
    products = relationship("Product", back_populates="shop")
    batches = relationship("Batch", back_populates="shop")
    bills = relationship("Bill", back_populates="shop")
    orders = relationship("Order", back_populates="shop")
    offers = relationship("Offer", back_populates="shop")
    loyalty_points = relationship("LoyaltyPoint", back_populates="shop")


class Shopkeeper(Base):
    __tablename__ = "shopkeepers"

    id = Column(Integer, primary_key=True, index=True)
    shop_id = Column(Integer, ForeignKey("shops.id"), nullable=False)
    name = Column(String(100), nullable=False)
    phone = Column(String(20), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    shop = relationship("Shop", back_populates="shopkeepers")


class Shopper(Base):
    __tablename__ = "shoppers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    phone = Column(String(20), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    address = Column(String(255), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    orders = relationship("Order", back_populates="shopper")
    notifications = relationship("Notification", back_populates="shopper")
    loyalty_points = relationship("LoyaltyPoint", back_populates="shopper")


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    shop_id = Column(Integer, ForeignKey("shops.id"), nullable=False)
    name = Column(String(150), nullable=False, index=True)
    barcode = Column(String(100), nullable=False, index=True)
    price = Column(Float, nullable=False)
    category = Column(String(100), default="General")
    low_stock_threshold = Column(Integer, default=5)
    created_at = Column(DateTime, default=datetime.utcnow)

    shop = relationship("Shop", back_populates="products")
    batches = relationship("Batch", back_populates="product", cascade="all, delete-orphan")
    offers = relationship("Offer", back_populates="product")


class Batch(Base):
    __tablename__ = "batches"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    shop_id = Column(Integer, ForeignKey("shops.id"), nullable=False)
    batch_number = Column(String(50), nullable=False)
    quantity = Column(Integer, nullable=False, default=0)
    expiry_date = Column(String(20), nullable=False)  # Format: YYYY-MM-DD for FEFO ordering
    created_at = Column(DateTime, default=datetime.utcnow)

    product = relationship("Product", back_populates="batches")
    shop = relationship("Shop", back_populates="batches")


class Bill(Base):
    __tablename__ = "bills"

    id = Column(Integer, primary_key=True, index=True)
    shop_id = Column(Integer, ForeignKey("shops.id"), nullable=False)
    bill_number = Column(String(50), unique=True, index=True, nullable=False)
    session_tab = Column(String(20), default="tab_1")  # tab_1 or tab_2
    total_amount = Column(Float, nullable=False, default=0.0)
    payment_method = Column(String(20), default="cash")  # cash or upi
    payment_status = Column(String(20), default="completed")  # completed or pending
    created_at = Column(DateTime, default=datetime.utcnow)

    shop = relationship("Shop", back_populates="bills")
    items = relationship("BillItem", back_populates="bill", cascade="all, delete-orphan")


class BillItem(Base):
    __tablename__ = "bill_items"

    id = Column(Integer, primary_key=True, index=True)
    bill_id = Column(Integer, ForeignKey("bills.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Float, nullable=False)
    batch_deductions_json = Column(Text, default="[]")  # e.g. [{"batch_id": 1, "batch_number": "B1", "qty": 2}]

    bill = relationship("Bill", back_populates="items")
    product = relationship("Product")


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    shopper_id = Column(Integer, ForeignKey("shoppers.id"), nullable=False)
    shop_id = Column(Integer, ForeignKey("shops.id"), nullable=False)
    order_number = Column(String(50), unique=True, index=True, nullable=False)
    order_type = Column(String(30), default="buy_from_home")  # prebook or buy_from_home
    collect_option = Column(String(30), default="pickup")     # pickup or home_delivery
    status = Column(String(30), default="pending")            # pending, accepted, ready, picked_up, out_for_delivery, completed
    total_amount = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    shopper = relationship("Shopper", back_populates="orders")
    shop = relationship("Shop", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Float, nullable=False)

    order = relationship("Order", back_populates="items")
    product = relationship("Product")


class MissedSearch(Base):
    __tablename__ = "missed_searches"

    id = Column(Integer, primary_key=True, index=True)
    shopper_id = Column(Integer, ForeignKey("shoppers.id"), nullable=True)
    query_text = Column(String(200), nullable=False, index=True)
    searched_at = Column(DateTime, default=datetime.utcnow)
    resolved = Column(Boolean, default=False)


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    shopper_id = Column(Integer, ForeignKey("shoppers.id"), nullable=False)
    title = Column(String(150), nullable=False)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    shopper = relationship("Shopper", back_populates="notifications")


class LoyaltyPoint(Base):
    __tablename__ = "loyalty_points"

    id = Column(Integer, primary_key=True, index=True)
    shopper_id = Column(Integer, ForeignKey("shoppers.id"), nullable=False)
    shop_id = Column(Integer, ForeignKey("shops.id"), nullable=False)
    points = Column(Integer, nullable=False)
    transaction_type = Column(String(20), default="earned")  # earned or redeemed
    description = Column(String(255), default="Purchase reward")
    created_at = Column(DateTime, default=datetime.utcnow)

    shopper = relationship("Shopper", back_populates="loyalty_points")
    shop = relationship("Shop", back_populates="loyalty_points")


class Offer(Base):
    __tablename__ = "offers"

    id = Column(Integer, primary_key=True, index=True)
    shop_id = Column(Integer, ForeignKey("shops.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    title = Column(String(150), nullable=False)
    discount_percent = Column(Float, default=10.0)
    valid_from = Column(String(20), nullable=False)
    valid_to = Column(String(20), nullable=False)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    shop = relationship("Shop", back_populates="offers")
    product = relationship("Product", back_populates="offers")
