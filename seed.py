import os
import hashlib
from datetime import datetime, timedelta
from backend.database import SessionLocal, engine, Base, ensure_schema_migrations
from backend.models import (
    Shop, Shopkeeper, Shopper, Product, Batch, Order, OrderItem,
    Bill, BillItem, MissedSearch, Notification, LoyaltyPoint, Offer
)
from backend.haversine import recompute_delivery_clusters

def hash_pwd(pwd: str) -> str:
    salt = "zephyr_2026_smart_commerce_salt"
    return hashlib.sha256(f"{salt}_{pwd.strip()}".encode("utf-8")).hexdigest()

def seed_database(force: bool = False):
    if force:
        print("Force reseed: dropping and recreating tables...")
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
    else:
        Base.metadata.create_all(bind=engine)
        try:
            ensure_schema_migrations(engine)
        except Exception:
            pass

    db = SessionLocal()

    try:
        existing_products = db.query(Product).count()
        if existing_products > 0 and not force:
            print(f"Database already populated ({existing_products} products found). Skipping seed.")
            return

        today = datetime.utcnow().date()

        print("Seeding Shops and Shopkeepers...")
        shops_data = [
            {
                "name": "Gupta Supermart",
                "owner": "Rajesh Gupta",
                "phone": "9810011111",
                "email": "gupta@supermart.in",
                "pwd": "password123",
                "address": "42, 100 Feet Road, Indiranagar, Bengaluru",
                "category": "Grocery & Supermarket",
                "hours": "7:00 AM - 10:30 PM",
                "lat": 12.9716,
                "lon": 77.6412
            },
            {
                "name": "Fresh Daily Grocery",
                "owner": "Sunita Verma",
                "phone": "9810022222",
                "email": "fresh@dailygrocery.in",
                "pwd": "password123",
                "address": "18, 12th Main Road, Indiranagar, Bengaluru",
                "category": "Fruits & Vegetables",
                "hours": "6:30 AM - 9:30 PM",
                "lat": 12.9735,
                "lon": 77.6435
            },
            {
                "name": "Metro Provision Store",
                "owner": "Anil Kumar",
                "phone": "9810033333",
                "email": "anil@metroprovisions.in",
                "pwd": "password123",
                "address": "77, CMH Road, Indiranagar, Bengaluru",
                "category": "General Store",
                "hours": "7:30 AM - 10:00 PM",
                "lat": 12.9782,
                "lon": 77.6420
            },
            {
                "name": "Green Field Organics",
                "owner": "Venkatesh Rao",
                "phone": "9810044444",
                "email": "greenfield@organics.in",
                "pwd": "password123",
                "address": "105, ITPL Main Road, Whitefield, Bengaluru",
                "category": "Organic & Wellness",
                "hours": "8:00 AM - 9:00 PM",
                "lat": 12.9698,
                "lon": 77.7499
            }
        ]

        shops = []
        for s_info in shops_data:
            shop = Shop(
                name=s_info["name"],
                owner_name=s_info["owner"],
                phone=s_info["phone"],
                email=s_info["email"],
                password_hash=hash_pwd(s_info["pwd"]),
                address=s_info["address"],
                category=s_info["category"],
                opening_hours=s_info["hours"],
                is_open=True,
                latitude=s_info["lat"],
                longitude=s_info["lon"]
            )
            db.add(shop)
            db.flush()

            shopkeeper = Shopkeeper(
                shop_id=shop.id,
                name=s_info["owner"],
                phone=s_info["phone"],
                email=s_info["email"],
                password_hash=hash_pwd(s_info["pwd"])
            )
            db.add(shopkeeper)
            shops.append(shop)

        print("Seeding Shoppers...")
        shoppers_data = [
            {
                "name": "Aarav Sharma",
                "phone": "9876500001",
                "email": "aarav.sharma@gmail.com",
                "pwd": "password123",
                "address": "Flat 302, Palm Heights, Indiranagar, Bengaluru",
                "lat": 12.9720,
                "lon": 77.6418
            },
            {
                "name": "Priya Patel",
                "phone": "9876500002",
                "email": "priya.patel@gmail.com",
                "pwd": "password123",
                "address": "14, 5th Cross, Defense Colony, Indiranagar, Bengaluru",
                "lat": 12.9740,
                "lon": 77.6440
            },
            {
                "name": "Rohan Verma",
                "phone": "9876500003",
                "email": "rohan.v@gmail.com",
                "pwd": "password123",
                "address": "B-12, Prestige Palms, Whitefield, Bengaluru",
                "lat": 12.9690,
                "lon": 77.7485
            }
        ]

        shoppers = []
        for sh_info in shoppers_data:
            shopper = Shopper(
                name=sh_info["name"],
                phone=sh_info["phone"],
                email=sh_info["email"],
                password_hash=hash_pwd(sh_info["pwd"]),
                address=sh_info["address"],
                latitude=sh_info["lat"],
                longitude=sh_info["lon"]
            )
            db.add(shopper)
            shoppers.append(shopper)

        db.commit()

        print("Computing 1 km Delivery Clusters...")
        try:
            recompute_delivery_clusters(db)
        except Exception:
            pass

        print("Seeding Realistic Product Catalog across Categories...")
        # Comprehensive realistic grocery products catalog with curated images and realistic MRPs
        catalog = [
            # Dairy & Breakfast
            {
                "name": "Amul Taaza Homogenised Toned Milk",
                "barcode": "890103000001",
                "brand": "Amul",
                "category": "Dairy & Breakfast",
                "price": 28.0,
                "mrp": 30.0,
                "unit": "500 ml",
                "desc": "Fresh homogenised toned milk packet, pasteurised and rich in calcium.",
                "image": "https://images.unsplash.com/photo-1550583724-b2692b85b150?w=400&auto=format&fit=crop&q=80"
            },
            {
                "name": "Nandini Pasteurised Toned Milk",
                "barcode": "890103000002",
                "brand": "Nandini",
                "category": "Dairy & Breakfast",
                "price": 24.0,
                "mrp": 26.0,
                "unit": "500 ml",
                "desc": "Wholesome pure cow milk from Karnataka Milk Federation.",
                "image": "https://images.unsplash.com/photo-1563636619-e9143da7973b?w=400&auto=format&fit=crop&q=80"
            },
            {
                "name": "Amul Butter Pasteurised",
                "barcode": "890103000003",
                "brand": "Amul",
                "category": "Dairy & Breakfast",
                "price": 58.0,
                "mrp": 60.0,
                "unit": "100 g",
                "desc": "Utterly butterly delicious salted cream butter.",
                "image": "https://images.unsplash.com/photo-1589985270826-4b7bb135bc9d?w=400&auto=format&fit=crop&q=80"
            },
            {
                "name": "Milky Mist Fresh Paneer",
                "barcode": "890103000004",
                "brand": "Milky Mist",
                "category": "Dairy & Breakfast",
                "price": 95.0,
                "mrp": 105.0,
                "unit": "200 g",
                "desc": "Soft, creamy fresh cottage cheese block, ideal for curry and grilling.",
                "image": "https://images.unsplash.com/photo-1631452180519-c014fe946bc7?w=400&auto=format&fit=crop&q=80"
            },

            # Bakery
            {
                "name": "Modern 100% Whole Wheat Bread",
                "barcode": "890103000005",
                "brand": "Modern",
                "category": "Bakery",
                "price": 45.0,
                "mrp": 50.0,
                "unit": "400 g",
                "desc": "High fibre wholesome brown loaf prepared from 100% atta wheat flour.",
                "image": "https://images.unsplash.com/photo-1509440159596-0249088772ff?w=400&auto=format&fit=crop&q=80"
            },
            {
                "name": "Britannia Brown Bread",
                "barcode": "890103000006",
                "brand": "Britannia",
                "category": "Bakery",
                "price": 50.0,
                "mrp": 55.0,
                "unit": "400 g",
                "desc": "Soft brown bread enriched with essential vitamins and whole grains.",
                "image": "https://images.unsplash.com/photo-1549931319-a545dcf3bc73?w=400&auto=format&fit=crop&q=80"
            },

            # Eggs & Meat
            {
                "name": "Farm Fresh White Eggs",
                "barcode": "890103000007",
                "brand": "Farm Fresh",
                "category": "Eggs & Meat",
                "price": 48.0,
                "mrp": 55.0,
                "unit": "Pack of 6",
                "desc": "Graded, farm-fresh protein rich table eggs with natural goodness.",
                "image": "https://images.unsplash.com/photo-1516448620398-c5f44bf9f441?w=400&auto=format&fit=crop&q=80"
            },
            {
                "name": "Country Brown Eggs Tray",
                "barcode": "890103000008",
                "brand": "Organic Valley",
                "category": "Eggs & Meat",
                "price": 110.0,
                "mrp": 125.0,
                "unit": "Pack of 12",
                "desc": "Cage-free, organic brown hen eggs rich in Omega-3.",
                "image": "https://images.unsplash.com/photo-1582722872445-44dc5f7e3c8f?w=400&auto=format&fit=crop&q=80"
            },

            # Staples & Grains
            {
                "name": "Aashirvaad Shudh Chakki Atta",
                "barcode": "890103000009",
                "brand": "Aashirvaad",
                "category": "Staples & Grains",
                "price": 260.0,
                "mrp": 290.0,
                "unit": "5 kg",
                "desc": "100% whole wheat grains ground in stone chakki for soft rotis.",
                "image": "https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&auto=format&fit=crop&q=80"
            },
            {
                "name": "India Gate Basmati Rice Feast",
                "barcode": "890103000010",
                "brand": "India Gate",
                "category": "Staples & Grains",
                "price": 140.0,
                "mrp": 165.0,
                "unit": "1 kg",
                "desc": "Long grain aromatic aged basmati rice for biryanis and pulao.",
                "image": "https://images.unsplash.com/photo-1586201375761-83865001e31c?w=400&auto=format&fit=crop&q=80"
            },
            {
                "name": "Tata Salt Vacuum Evaporated",
                "barcode": "890103000011",
                "brand": "Tata",
                "category": "Staples & Grains",
                "price": 28.0,
                "mrp": 30.0,
                "unit": "1 kg",
                "desc": "Iodised vacuum-evaporated table salt, purity guaranteed by Tata.",
                "image": "https://images.unsplash.com/photo-1626082927389-6cd097cdc6ec?w=400&auto=format&fit=crop&q=80"
            },
            {
                "name": "Fortune Sunlite Sunflower Oil",
                "barcode": "890103000012",
                "brand": "Fortune",
                "category": "Cooking Oils",
                "price": 145.0,
                "mrp": 165.0,
                "unit": "1 L",
                "desc": "Refined sunflower cooking oil enriched with Vitamins A, D, and E.",
                "image": "https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&auto=format&fit=crop&q=80"
            },

            # Fruits & Fresh Vegetables
            {
                "name": "Fresh Hybrid Tomatoes",
                "barcode": "890103000013",
                "brand": "Farm Fresh",
                "category": "Fruits & Vegetables",
                "price": 35.0,
                "mrp": 45.0,
                "unit": "1 kg",
                "desc": "Crisp red ripe kitchen tomatoes sourced directly from local mandis.",
                "image": "https://images.unsplash.com/photo-1592924357228-91a4daadcfea?w=400&auto=format&fit=crop&q=80"
            },
            {
                "name": "Fresh Nashik Red Onions",
                "barcode": "890103000014",
                "brand": "Farm Fresh",
                "category": "Fruits & Vegetables",
                "price": 42.0,
                "mrp": 50.0,
                "unit": "1 kg",
                "desc": "Pungent, dry, medium-sized cooking onions for everyday curries.",
                "image": "https://images.unsplash.com/photo-1618512496248-a07fe83aa8cb?w=400&auto=format&fit=crop&q=80"
            },
            {
                "name": "Fresh Baby Potatoes",
                "barcode": "890103000015",
                "brand": "Farm Fresh",
                "category": "Fruits & Vegetables",
                "price": 38.0,
                "mrp": 45.0,
                "unit": "1 kg",
                "desc": "Clean, unwashed firm potatoes perfect for roasting, dum aloo, and fries.",
                "image": "https://images.unsplash.com/photo-1518977676601-b53f82aba655?w=400&auto=format&fit=crop&q=80"
            },
            {
                "name": "Robusta Ripe Bananas",
                "barcode": "890103000016",
                "brand": "Daily Fresh",
                "category": "Fruits & Vegetables",
                "price": 45.0,
                "mrp": 55.0,
                "unit": "1 kg (approx 6-8 pcs)",
                "desc": "Naturally sweet golden ripe bananas packed with natural potassium.",
                "image": "https://images.unsplash.com/photo-1571771894821-ce9b6c11b08e?w=400&auto=format&fit=crop&q=80"
            },

            # Snacks & Instant Food
            {
                "name": "Maggi 2-Minute Masala Instant Noodles",
                "barcode": "890103000017",
                "brand": "Nestle",
                "category": "Snacks & Instant Food",
                "price": 14.0,
                "mrp": 15.0,
                "unit": "70 g",
                "desc": "India's favorite instant noodle with iconic blend of authentic spices.",
                "image": "https://images.unsplash.com/photo-1612927601601-6638404737ce?w=400&auto=format&fit=crop&q=80"
            },
            {
                "name": "Lay's India's Magic Masala Potato Chips",
                "barcode": "890103000018",
                "brand": "Lay's",
                "category": "Snacks & Instant Food",
                "price": 20.0,
                "mrp": 20.0,
                "unit": "50 g",
                "desc": "Thin crispy ridged potato chips seasoned with aromatic Indian spices.",
                "image": "https://images.unsplash.com/photo-1566478989037-eec170784d0b?w=400&auto=format&fit=crop&q=80"
            },
            {
                "name": "Parle-G Original Gluco Biscuits",
                "barcode": "890103000019",
                "brand": "Parle",
                "category": "Snacks & Biscuits",
                "price": 25.0,
                "mrp": 25.0,
                "unit": "250 g",
                "desc": "Classic crisp glucose biscuits, the best companion for evening chai.",
                "image": "https://images.unsplash.com/photo-1558961363-fa8fdf82db35?w=400&auto=format&fit=crop&q=80"
            },

            # Beverages
            {
                "name": "Tata Tea Gold Leaf Tea",
                "barcode": "890103000020",
                "brand": "Tata",
                "category": "Beverages",
                "price": 310.0,
                "mrp": 340.0,
                "unit": "500 g",
                "desc": "Exquisite blend of valley grown Assam CTC tea and long aromatic leaves.",
                "image": "https://images.unsplash.com/photo-1544787219-7f47ccb76574?w=400&auto=format&fit=crop&q=80"
            },
            {
                "name": "Nescafe Classic Instant Coffee Jar",
                "barcode": "890103000021",
                "brand": "Nescafe",
                "category": "Beverages",
                "price": 195.0,
                "mrp": 215.0,
                "unit": "50 g",
                "desc": "100% pure soluble coffee granules delivering rich aroma and taste.",
                "image": "https://images.unsplash.com/photo-1559056199-641a0ac8b55e?w=400&auto=format&fit=crop&q=80"
            }
        ]

        # Seed products into shops with multi-batch inventory
        all_created_products = []
        for shop in shops:
            for i, item in enumerate(catalog):
                prod = Product(
                    shop_id=shop.id,
                    name=item["name"],
                    barcode=f"{item['barcode'][:-1]}{shop.id}",
                    brand=item["brand"],
                    category=item["category"],
                    description=item["desc"],
                    price=item["price"],
                    mrp=item["mrp"],
                    unit=item["unit"],
                    image_url=item["image"],
                    is_available=True,
                    low_stock_threshold=5
                )
                db.add(prod)
                db.flush()
                all_created_products.append(prod)

                # Batch 1: Near expiry for Use-Soon deals
                near_exp = (today + timedelta(days=6 + (i % 6))).strftime("%Y-%m-%d")
                b1 = Batch(
                    product_id=prod.id,
                    shop_id=shop.id,
                    batch_number=f"B-{prod.id}-01",
                    quantity=8 + (i % 5),
                    expiry_date=near_exp
                )
                db.add(b1)

                # Batch 2: Fresh stock
                fresh_exp = (today + timedelta(days=180 + (i * 10))).strftime("%Y-%m-%d")
                b2 = Batch(
                    product_id=prod.id,
                    shop_id=shop.id,
                    batch_number=f"B-{prod.id}-02",
                    quantity=20 + (i % 10),
                    expiry_date=fresh_exp
                )
                db.add(b2)

        print("Seeding Seasonal Offers...")
        # Store offers for Shop 1 (Gupta Supermart) and Shop 2 (Fresh Daily)
        today_str = today.strftime("%Y-%m-%d")
        next_month_str = (today + timedelta(days=30)).strftime("%Y-%m-%d")

        # Offer 1: 15% off milk & dairy
        off1 = Offer(
            shop_id=shops[0].id,
            product_id=all_created_products[0].id, # Amul Milk
            title="Morning Dairy Rush: 15% OFF",
            discount_percent=15.0,
            valid_from=today_str,
            valid_to=next_month_str,
            banner_text="Fresh Milk & Dairy Special: 15% OFF on morning essentials!",
            active=True
        )
        db.add(off1)

        # Offer 2: 10% off Atta & staples
        off2 = Offer(
            shop_id=shops[0].id,
            product_id=all_created_products[8].id, # Aashirvaad Atta
            title="Staples Saver: 10% OFF Atta",
            discount_percent=10.0,
            valid_from=today_str,
            valid_to=next_month_str,
            banner_text="Flat 10% discount on Aashirvaad Chakki Atta 5kg!",
            active=True
        )
        db.add(off2)

        # Offer 3: 20% off Fruits at Fresh Daily
        off3 = Offer(
            shop_id=shops[1].id,
            product_id=None, # Store-wide
            title="Weekend Veggie & Fruit Carnival: 20% OFF",
            discount_percent=20.0,
            valid_from=today_str,
            valid_to=next_month_str,
            banner_text="Flat 20% OFF across farm fresh fruits and vegetables!",
            active=True
        )
        db.add(off3)

        print("Seeding Initial Order...")
        shop1 = shops[0]
        shopper1 = shoppers[0]
        p1 = all_created_products[0]
        p2 = all_created_products[4]

        order1 = Order(
            shopper_id=shopper1.id,
            shop_id=shop1.id,
            order_number="AZ-20261009-1001",
            order_type="buy_from_home",
            collect_option="home_delivery",
            delivery_address=shopper1.address,
            payment_method="UPI / Online",
            payment_status="completed",
            status="accepted",
            subtotal=round(p1.price * 2 + p2.price * 1, 2),
            delivery_fee=25.0,
            tax_amount=round((p1.price * 2 + p2.price * 1) * 0.05, 2),
            discount_amount=round(p1.price * 2 * 0.15, 2),
            total_amount=round((p1.price * 2 + p2.price * 1) * 1.05 + 25.0 - (p1.price * 2 * 0.15), 2)
        )
        db.add(order1)
        db.flush()

        db.add(OrderItem(order_id=order1.id, product_id=p1.id, quantity=2, unit_price=round(p1.price * 0.85, 2)))
        db.add(OrderItem(order_id=order1.id, product_id=p2.id, quantity=1, unit_price=p2.price))

        db.commit()
        print("Database successfully seeded with realistic real-world data!")

    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}")
        raise e
    finally:
        db.close()

def seed_if_empty():
    seed_database(force=False)

if __name__ == "__main__":
    import sys
    force_flag = "--force" in sys.argv
    seed_database(force=force_flag)
