import os
import hashlib
from datetime import datetime, timedelta
from backend.database import SessionLocal, engine, Base
from backend.models import (
    Shop, Shopkeeper, Shopper, Product, Batch, Order, OrderItem,
    Bill, BillItem, MissedSearch, Notification, LoyaltyPoint, Offer
)
from backend.haversine import recompute_delivery_clusters

def hash_pwd(pwd: str) -> str:
    return hashlib.sha256(pwd.strip().encode("utf-8")).hexdigest()

def populate_data(db):
    today = datetime.utcnow().date()

    print("Seeding Shops and Shopkeepers...")
    # 4 Shops: 3 in Indiranagar within 1km cluster, 1 far away in Whitefield
    shops_data = [
        {
            "name": "Gupta Supermart",
            "owner": "Rajesh Gupta",
            "phone": "9810011111",
            "pwd": "password123",
            "address": "42, 100 Feet Road, Indiranagar, Bengaluru",
            "lat": 12.9716,
            "lon": 77.6412
        },
        {
            "name": "Fresh Daily Grocery",
            "owner": "Sunita Verma",
            "phone": "9810022222",
            "pwd": "password123",
            "address": "18, 12th Main Road, Indiranagar, Bengaluru",
            "lat": 12.9735,
            "lon": 77.6435
        },
        {
            "name": "Metro Provision Store",
            "owner": "Anil Kumar",
            "phone": "9810033333",
            "pwd": "password123",
            "address": "77, CMH Road, Indiranagar, Bengaluru",
            "lat": 12.9782,
            "lon": 77.6420
        },
        {
            "name": "Green Field Organics",
            "owner": "Venkatesh Rao",
            "phone": "9810044444",
            "pwd": "password123",
            "address": "105, ITPL Main Road, Whitefield, Bengaluru",
            "lat": 12.9698,
            "lon": 77.7499  # ~11.8 km far away
        }
    ]

    shops = []
    for s_info in shops_data:
        shop = Shop(
            name=s_info["name"],
            owner_name=s_info["owner"],
            phone=s_info["phone"],
            password_hash=hash_pwd(s_info["pwd"]),
            address=s_info["address"],
            latitude=s_info["lat"],
            longitude=s_info["lon"]
        )
        db.add(shop)
        db.flush()

        shopkeeper = Shopkeeper(
            shop_id=shop.id,
            name=s_info["owner"],
            phone=s_info["phone"],
            password_hash=hash_pwd(s_info["pwd"])
        )
        db.add(shopkeeper)
        shops.append(shop)

    print("Seeding Shoppers...")
    shoppers_data = [
        {
            "name": "Aarav Sharma",
            "phone": "9876500001",
            "pwd": "password123",
            "address": "Flat 302, Palm Heights, Indiranagar",
            "lat": 12.9720,
            "lon": 77.6418
        },
        {
            "name": "Priya Patel",
            "phone": "9876500002",
            "pwd": "password123",
            "address": "14, 5th Cross, Defense Colony, Indiranagar",
            "lat": 12.9740,
            "lon": 77.6440
        },
        {
            "name": "Rohan Verma",
            "phone": "9876500003",
            "pwd": "password123",
            "address": "B-12, Prestige Palms, Whitefield",
            "lat": 12.9690,
            "lon": 77.7485
        }
    ]

    shoppers = []
    for sh_info in shoppers_data:
        shopper = Shopper(
            name=sh_info["name"],
            phone=sh_info["phone"],
            password_hash=hash_pwd(sh_info["pwd"]),
            address=sh_info["address"],
            latitude=sh_info["lat"],
            longitude=sh_info["lon"]
        )
        db.add(shopper)
        shoppers.append(shopper)

    db.commit()

    print("Computing 1 km Delivery Clusters...")
    recompute_delivery_clusters(db)

    print("Seeding 22 Products with Barcodes & Multi-Batch Inventory (FEFO & Use Soon)...")
    products_master = [
        {"name": "Amul Taaza Homogenised Toned Milk (500ml)", "barcode": "890103000001", "price": 28.0, "cat": "Dairy & Breakfast", "threshold": 10},
        {"name": "Nandini Pasteurised Toned Milk (500ml)", "barcode": "890103000002", "price": 24.0, "cat": "Dairy & Breakfast", "threshold": 10},
        {"name": "Modern 100% Whole Wheat Bread (400g)", "barcode": "890103000003", "price": 45.0, "cat": "Bakery", "threshold": 6},
        {"name": "Britannia Brown Bread (400g)", "barcode": "890103000004", "price": 50.0, "cat": "Bakery", "threshold": 6},
        {"name": "Aashirvaad Shudh Chakki Atta (5kg)", "barcode": "890103000005", "price": 260.0, "cat": "Staples & Grains", "threshold": 4},
        {"name": "Fortune Sunlite Sunflower Oil (1L)", "barcode": "890103000006", "price": 145.0, "cat": "Cooking Oils", "threshold": 5},
        {"name": "Tata Salt Vacuum Evaporated (1kg)", "barcode": "890103000007", "price": 28.0, "cat": "Staples & Grains", "threshold": 12},
        {"name": "Maggi 2-Minute Masala Instant Noodles (70g)", "barcode": "890103000008", "price": 14.0, "cat": "Snacks & Instant Food", "threshold": 15},
        {"name": "Parle-G Original Gluco Biscuits (250g)", "barcode": "890103000009", "price": 25.0, "cat": "Snacks & Biscuits", "threshold": 10},
        {"name": "Tata Tea Gold (500g)", "barcode": "890103000010", "price": 310.0, "cat": "Beverages", "threshold": 5},
        {"name": "Nescafe Classic Instant Coffee Jar (50g)", "barcode": "890103000011", "price": 195.0, "cat": "Beverages", "threshold": 4},
        {"name": "Epigamia Greek Yogurt Strawberry (90g)", "barcode": "890103000012", "price": 60.0, "cat": "Dairy & Breakfast", "threshold": 8},
        {"name": "Amul Butter Pasteurised (100g)", "barcode": "890103000013", "price": 58.0, "cat": "Dairy & Breakfast", "threshold": 8},
        {"name": "Lay's India's Magic Masala Chips (50g)", "barcode": "890103000014", "price": 20.0, "cat": "Snacks & Instant Food", "threshold": 15},
        {"name": "Dettol Original Liquid Handwash Pump (200ml)", "barcode": "890103000015", "price": 99.0, "cat": "Personal Care", "threshold": 5},
        {"name": "Colgate Total Clean Mint Toothpaste (120g)", "barcode": "890103000016", "price": 125.0, "cat": "Personal Care", "threshold": 6},
        {"name": "Surf Excel Easy Wash Detergent Powder (1kg)", "barcode": "890103000017", "price": 140.0, "cat": "Household & Cleaning", "threshold": 5},
        {"name": "Vim Lemon Dishwash Gel Bottle (250ml)", "barcode": "890103000018", "price": 60.0, "cat": "Household & Cleaning", "threshold": 7},
        {"name": "Farm Fresh White Eggs (Pack of 6)", "barcode": "890103000019", "price": 48.0, "cat": "Eggs & Meat", "threshold": 8},
        {"name": "Kellogg's Real Almond Honey Corn Flakes (300g)", "barcode": "890103000020", "price": 185.0, "cat": "Breakfast Cereals", "threshold": 4},
        {"name": "Raw Pressery Cold Pressed Orange Juice (250ml)", "barcode": "890103000021", "price": 85.0, "cat": "Beverages", "threshold": 6},
        {"name": "Saffola Gold Pro Healthy Oil (1L)", "barcode": "890103000022", "price": 175.0, "cat": "Cooking Oils", "threshold": 5}
    ]

    # Assign products across shops with realistic batch variations
    all_created_products = []

    for shop in shops:
        # Shop 1 & 2 have most items, Shop 3 has smaller selection, Shop 4 has organic staples
        for i, item in enumerate(products_master):
            # Skip some items for Shop 3 and Shop 4 to create real unmet demand opportunities!
            if shop.id == 3 and i % 3 == 0:
                continue
            if shop.id == 4 and i % 2 == 1:
                continue

            prod = Product(
                shop_id=shop.id,
                name=item["name"],
                barcode=item["barcode"],
                price=item["price"],
                category=item["cat"],
                low_stock_threshold=item["threshold"]
            )
            db.add(prod)
            db.flush()
            all_created_products.append(prod)

            # Batches:
            # Batch 1: Near expiry (in 4 to 12 days) for "Use Soon" Deals and Expiry alerts!
            near_exp = (today + timedelta(days=(4 + (i % 8)))).strftime("%Y-%m-%d")
            b1 = Batch(
                product_id=prod.id,
                shop_id=shop.id,
                batch_number=f"BATCH-{prod.id}-01",
                quantity=4 + (i % 6),
                expiry_date=near_exp
            )
            db.add(b1)

            # Batch 2: Fresh stock (in 180 to 365 days)
            fresh_exp = (today + timedelta(days=200 + (i * 10))).strftime("%Y-%m-%d")
            b2 = Batch(
                product_id=prod.id,
                shop_id=shop.id,
                batch_number=f"BATCH-{prod.id}-02",
                quantity=15 + (i % 12),
                expiry_date=fresh_exp
            )
            db.add(b2)

    db.commit()

    print("Seeding Missed Searches for Unmet-Demand Loop & AI Insights...")
    missed_queries = [
        ("Oat Milk 1L", 14),
        ("Gluten Free Sourdough Bread", 9),
        ("Organic Tofu 200g", 8),
        ("Greek Feta Cheese", 6),
        ("Cold Brew Coffee Can", 5),
        ("Chia Seeds 250g", 4),
        ("Avocado Hass", 7),
        ("Matcha Green Tea Powder", 3)
    ]

    for query, count in missed_queries:
        for k in range(count):
            shopper_ref = shoppers[k % len(shoppers)]
            ms = MissedSearch(
                shopper_id=shopper_ref.id,
                query_text=query,
                searched_at=datetime.utcnow() - timedelta(hours=k * 3),
                resolved=False
            )
            db.add(ms)

    print("Seeding Sample Orders & Digital Receipts...")
    # Pre-seed sample orders for Gupta Supermart
    shop1 = shops[0]
    shopper1 = shoppers[0]
    p1 = all_created_products[0]
    p2 = all_created_products[2]

    order1 = Order(
        shopper_id=shopper1.id,
        shop_id=shop1.id,
        order_number="ORD-20261008-001",
        order_type="buy_from_home",
        collect_option="home_delivery",
        status="ready",
        total_amount=round(p1.price * 2 + p2.price * 1, 2)
    )
    db.add(order1)
    db.flush()

    db.add(OrderItem(order_id=order1.id, product_id=p1.id, quantity=2, unit_price=p1.price))
    db.add(OrderItem(order_id=order1.id, product_id=p2.id, quantity=1, unit_price=p2.price))

    # Pre-seed a completed order with loyalty points
    order2 = Order(
        shopper_id=shopper1.id,
        shop_id=shop1.id,
        order_number="ORD-20261007-009",
        order_type="prebook",
        collect_option="pickup",
        status="completed",
        total_amount=350.0,
        created_at=datetime.utcnow() - timedelta(days=1)
    )
    db.add(order2)
    db.flush()

    db.add(LoyaltyPoint(
        shopper_id=shopper1.id,
        shop_id=shop1.id,
        points=7,
        transaction_type="earned",
        description="Reward for Order #ORD-20261007-009"
    ))

    print("Seeding Seasonal Offers...")
    db.add(Offer(
        shop_id=shop1.id,
        product_id=p1.id,
        title="Morning Breakfast Booster - 15% OFF",
        discount_percent=15.0,
        valid_from=today.strftime("%Y-%m-%d"),
        valid_to=(today + timedelta(days=30)).strftime("%Y-%m-%d"),
        active=True
    ))

    db.add(Offer(
        shop_id=shop1.id,
        product_id=None,
        title="Festive Weekend Clearance - 10% Storewide",
        discount_percent=10.0,
        valid_from=today.strftime("%Y-%m-%d"),
        valid_to=(today + timedelta(days=15)).strftime("%Y-%m-%d"),
        active=True
    ))

    db.commit()
    print("Seed data successfully populated!")

def seed_database():
    print("Clearing and creating database schema...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        populate_data(db)
    finally:
        db.close()

def seed_if_empty():
    db = SessionLocal()
    try:
        if db.query(Shop).count() == 0:
            print("Database is empty. Populating seed data...")
            populate_data(db)
    except Exception as e:
        print(f"Error checking or seeding database: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
