from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Shop, DeliveryCluster, DeliveryPerson
from backend.haversine import get_shop_delivery_details, recompute_delivery_clusters

router = APIRouter(prefix="/delivery", tags=["Shared Delivery Service"])

@router.get("/cluster-info")
def get_cluster_info(
    shop_id: int = Query(..., description="Shop ID"),
    db: Session = Depends(get_db)
):
    """
    Shopkeeper Dashboard - Shared Delivery Service:
    Returns:
    - The cluster's shops
    - The delivery person's name and total monthly salary
    - The number of shops sharing
    - THIS shop's split share (salary divided equally among shops in the cluster)
    """
    details = get_shop_delivery_details(db, shop_id)
    if not details:
        raise HTTPException(status_code=404, detail="Shop not found.")

    return {
        "success": True,
        "delivery_details": details
    }

@router.post("/recompute-clusters")
def trigger_recompute_clusters(db: Session = Depends(get_db)):
    """
    Recalculates delivery clusters across all shops using 1 km Haversine radius.
    Called automatically on shop registration, or manually if needed.
    """
    recompute_delivery_clusters(db)
    clusters = db.query(DeliveryCluster).all()
    results = []

    for c in clusters:
        rider = c.delivery_persons[0] if c.delivery_persons else None
        shops_in_c = c.shops
        n_shops = len(shops_in_c)
        salary = rider.monthly_salary if rider else 12000.0
        share_per_shop = round(salary / max(n_shops, 1), 2)

        results.append({
            "cluster_id": c.id,
            "cluster_name": c.name,
            "shops_count": n_shops,
            "monthly_salary": salary,
            "cost_per_shop": share_per_shop,
            "rider_name": rider.name if rider else "Not Assigned",
            "rider_phone": rider.phone if rider else "N/A",
            "shops": [{"id": s.id, "name": s.name, "phone": s.phone} for s in shops_in_c]
        })

    return {
        "success": True,
        "message": "Clusters successfully recalculated based on 1 km radius.",
        "clusters": results
    }
