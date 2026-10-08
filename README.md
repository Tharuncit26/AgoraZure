# 🛒 AgoraZure — Smart Commerce Platform
**Zéphyr 2026 AI Hackathon — Problem Statement PS-2: Smart Commerce**

AgoraZure connects local neighborhood shops and shoppers through one unified, shared hyperlocal commerce system.

---

## 🌟 Key Architecture & Differentiators

```
  ┌─────────────────────────────────────────────────────────────┐
  │                        AgoraZure                            │
  ├──────────────────────────────┬──────────────────────────────┤
  │      Shopper Website         │     Shopkeeper Website       │
  │  • Search Live Stock Nearby  │  • Scan & Bill POS (FEFO)    │
  │  • Pre-book & Buy from Home  │  • Dual-Bill Sessions (A & B)│
  │  • 1 km Shared Delivery/Pickup│  • UPI QR & Digital Receipt  │
  │  • "Use Soon" Deals (30% off)│  • Low Stock / Shrinkage / Exp│
  │  • Smart Substitutes (AI)    │  • Shared Delivery Dashboard │
  │  • Unmet-Demand Notify-Back  │  • Azure AI Demand Insights  │
  └──────────────┬───────────────┴──────────────┬───────────────┘
                 │                              │
                 ▼                              ▼
      ┌─────────────────────────────────────────────────────┐
      │           FastAPI Unified Backend Engine            │
      ├─────────────────────────────────────────────────────┤
      │  • Haversine 1 km Clustering & Salary Splitting     │
      │  • FEFO (First-Expired First-Out) Inventory Engine  │
      │  • Azure OpenAI + Intelligent Rule-Based Fallback   │
      │  • SQLite DB Layer (SQLAlchemy ORM, Postgres-ready) │
      └─────────────────────────────────────────────────────┘
```

1. **Unmet-Demand Loop (Core Differentiator)**:
   - When a shopper searches for an unstocked product, it is logged in `missed_searches`.
   - **(a) Stocking Advice**: Azure OpenAI analyzes missed searches and recommends high-ROI stocking decisions to the shopkeeper.
   - **(b) Notify-Back**: The moment any nearby shopkeeper adds that product or new batch, the waiting shopper instantly receives an in-app notification!

2. **Shared Delivery Service (1 km Radius Cluster)**:
   - Uses the **Haversine formula** to measure distances between shops from their latitude and longitude.
   - Shops within 1 km form a delivery cluster sharing **ONE delivery rider** (instead of each shop hiring their own).
   - Monthly rider salary (e.g. ₹12,000) is **split equally** among cluster shops (e.g. ₹12,000 / 3 = ₹4,000 per shop). Automatically recalculates as shops join or leave.
   - Home delivery is offered to shoppers **only** if the shop belongs to an active delivery cluster; otherwise, only store pickup is available.

3. **FEFO Inventory & "Use Soon" Deals**:
   - Stock is tracked in **batches** with hand-entered expiry dates.
   - At checkout, the oldest batch (nearest expiry) is automatically deducted first (**First-Expired, First-Out**).
   - Batches expiring within 14 days are showcased to shoppers as **"Use Soon" Deals** at a 30% discount to eliminate food waste.

4. **Barcode POS (Keyboard Input)**:
   - Compatible with any standard USB or Bluetooth scanner (acts as keyboard input + Enter). No camera or special hardware required.
   - Supports **two concurrent billing tabs** (Bill Tab 1 & Bill Tab 2) to serve two customers simultaneously without mixing items up.
   - Dynamic **UPI QR Code** generation for bill amounts with instant digital receipts.

---

## 🛠️ Tech Stack

- **Backend**: Python 3.11+ with **FastAPI**
- **Database**: **SQLite** via **SQLAlchemy ORM** (structured for seamless migration to PostgreSQL)
- **Frontend**: Plain **HTML5, CSS3, JavaScript** (no heavy frameworks like React/Vue/Angular), **Mobile-First Responsive Design**
- **AI**: **Azure OpenAI** (for smart substitutes & demand insights) with automatic rule-based fallback if credentials are not provided
- **Scanner**: Standard keyboard input emulation (types barcode and triggers Enter)
- **Payments**: Prototype **UPI QR** code generator (`upi://pay`) with merchant confirmation

---

## 🚀 Quick Setup & Run Instructions

### 1. Prerequisites
Ensure Python 3.10 or higher is installed.

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Environment Setup (.env)
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
*(Optional)* Add your Azure OpenAI credentials in `.env`. If left empty, AgoraZure will automatically use its built-in rule-based AI engine:
```env
DATABASE_URL=sqlite:///./agorazure.db
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your_key_here
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o-mini
AZURE_OPENAI_API_VERSION=2024-02-15-preview
```

### 4. Seed Database with Realistic Data
Populates 4 shops (3 in Indiranagar within 1 km, 1 in Whitefield far away), 22 products with barcodes, multi-batch FEFO inventory, near-expiry batches, missed searches, and sample shoppers:
```bash
python seed.py
```

### 5. Start the Server
```bash
uvicorn backend.main:app --reload --port 8000
```
Open your browser to:
- **Landing Hub**: [http://localhost:8000/](http://localhost:8000/)
- **Shopper Website**: [http://localhost:8000/shopper](http://localhost:8000/shopper)
- **Shopkeeper Website**: [http://localhost:8000/shopkeeper](http://localhost:8000/shopkeeper)
- **API Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 🧪 End-to-End Testing & Demo Walkthrough

### 1. Shopkeeper Workflow (`/shopkeeper`)
1. Click **"Login as Gupta Supermart"** (1-click demo button).
2. **Scan & Bill**:
   - Focus the barcode input (pulsing green indicator).
   - Enter barcode `890103000001` (Amul Milk) and press `Enter`.
   - Scan again: quantity increments to 2!
   - Switch to **Bill Tab 2**: notice a separate cart session for Customer B!
   - Switch back to **Bill Tab 1**, click **"Show UPI QR"**: scan the generated QR with any UPI app simulator, then click **"✓ Payment Received"**.
   - Notice the **Digital Receipt** pops up, and stock is reduced via **FEFO**!
3. **Inventory & Goods Arrival**:
   - Go to **"Stock & Batches"** tab.
   - Click **"+ Add Goods (Batch)"**: enter barcode `890103000001`, quantity `20`, expiry `2026-12-31`. Click submit.
4. **Alerts**:
   - Inspect **Low Stock** and **Near Expiry** alerts.
   - Under **Physical Shrinkage Audit**, select a product, enter a counted quantity (e.g. 2 units less than expected), and click **"Verify Match"** to see financial shrinkage flagged.
5. **Demand AI**:
   - Click **"Demand AI"** tab to see stocking advice derived from shopper missed searches (e.g. *Oat Milk*, *Gluten Free Bread*).
6. **Shared Delivery**:
   - Inspect the **Shared Delivery** tab: shows Indiranagar Central Cluster, rider Ramesh Kumar, monthly salary ₹12,000, and this shop's equal share (₹4,000/month).

### 2. Shopper Workflow (`/shopper`)
1. Click **"Login as Aarav Sharma"** (1-click demo button).
2. **Search Live Stock Nearby**:
   - Search for `"Milk"` or `"Bread"`: see nearby shops with live stock counts and distances in km.
   - Add items to cart.
3. **Unmet-Demand Loop & Smart AI Substitutes**:
   - Search for an unstocked item: `"Oat Milk"` or `"Almond Milk"`.
   - Notice the system logs a **Missed Search** and displays **Smart AI Substitutes** from nearby stores!
4. **"Use Soon" Deals**:
   - Check the **"Use Soon" Deals** section displaying near-expiry products with 30% discount tags.
5. **Collect Options & Checkout**:
   - Open cart. Choose **"Buy from Home"** or **"Pre-Book"**.
   - Choose **"Home Delivery (Shared Rider)"** or **"Queue-Free Pickup"**.
   - Click **"Place Order"**: generates a digital pickup slip/receipt and awards **Loyalty Points**!
6. **Notify-Back**:
   - When a shopkeeper adds stock for an item previously searched, the shopper's 🔔 notification bell updates with a live in-app notify-back!

---

## 📁 Repository Structure

```
c:\Users\DELL\ZEPHYR APP\
├── backend/
│   ├── config.py              # Environment and Azure AI configuration
│   ├── database.py            # SQLite engine & session management
│   ├── models.py              # SQLAlchemy database models
│   ├── schemas.py             # Pydantic validation schemas
│   ├── haversine.py           # Haversine 1 km clustering engine
│   ├── ai_service.py          # Azure OpenAI client + rule-based fallback
│   ├── routes/
│   │   ├── auth.py            # Shopkeeper & Shopper authentication
│   │   ├── stock.py           # FEFO stock & batch management
│   │   ├── billing.py         # Barcode POS, UPI QR, receipts
│   │   ├── alerts.py          # Low stock, shrinkage, expiry alerts
│   │   ├── insights.py        # Unmet-demand AI stocking advice
│   │   ├── orders.py          # Online orders & status pipeline
│   │   ├── shopper.py         # Proximity search, substitutes, deals
│   │   ├── delivery.py        # Shared delivery cluster calculations
│   │   └── loyalty_offers.py  # Loyalty points and seasonal offers
│   └── main.py                # FastAPI app initialization
├── frontend/
│   ├── css/style.css          # Mobile-first design system
│   ├── js/
│   │   ├── shopkeeper.js      # Shopkeeper POS & dashboard logic
│   │   └── shopper.js         # Shopper search & checkout logic
│   ├── shopkeeper.html        # Shopkeeper Web App
│   ├── shopper.html           # Shopper Web App
│   └── index.html             # AgoraZure Portal Hub
├── seed.py                    # Complete database seeder
├── requirements.txt           # Python dependencies
├── .env.example               # Environment variables template
├── .env                       # Local runtime config
└── README.md                  # Documentation
```
