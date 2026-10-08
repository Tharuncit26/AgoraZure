from collections import Counter
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import MissedSearch, Shop, Product, Batch
from backend.ai_service import generate_demand_insights

router = APIRouter(prefix="/insights", tags=["Unmet Demand Insights"])

@router.get("/stocking-advice")
async def get_stocking_advice(
    shop_id: int = Query(..., description="Shop ID"),
    db: Session = Depends(get_db)
):
    """
    Unmet-Demand Loop (Part A):
    Aggregates missed searches (queries with 0 stock / unstocked) and invokes
    Azure OpenAI (with graceful rule-based fallback) to generate actionable
    stocking advice for the shopkeeper.
    """
    shop = db.query(Shop).filter(Shop.id == shop_id).first()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found.")

    # Get all products currently stocked in this shop
    stocked_products = db.query(Product).filter(Product.shop_id == shop_id).all()
    stocked_names = {p.name.lower().strip() for p in stocked_products}

    # Fetch all missed searches
    missed_records = db.query(MissedSearch).all()
    
    # Filter searches that this shop does NOT stock or has 0 stock in
    unmet_queries = []
    for ms in missed_records:
        query_norm = ms.query_text.lower().strip()
        # If this shop doesn't carry it, or carries it with 0 stock
        matching_prod = next((p for p in stocked_products if p.name.lower() in query_norm or query_norm in p.name.lower()), None)
        if not matching_prod:
            unmet_queries.append(ms.query_text.strip().title())
        else:
            # Check stock
            stock = sum(b.quantity for b in matching_prod.batches if b.quantity > 0)
            if stock == 0:
                unmet_queries.append(ms.query_text.strip().title())

    # Count occurrences
    counts = Counter(unmet_queries)
    summary = [
        {"term": term, "count": count}
        for term, count in counts.most_common(10)
    ]

    # Generate insights via Azure OpenAI or fallback
    advice_list = await generate_demand_insights(summary, shop.name)

    return {
        "success": True,
        "shop_id": shop.id,
        "shop_name": shop.name,
        "total_missed_searches": len(missed_records),
        "unmet_demand_items_count": len(summary),
        "summary": summary,
        "stocking_advice": advice_list
    }
