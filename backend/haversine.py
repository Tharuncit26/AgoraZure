import math
from typing import List, Tuple
from sqlalchemy.orm import Session
from backend.models import Shop, DeliveryCluster, DeliveryPerson

EARTH_RADIUS_KM = 6371.0

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance between two points on Earth in kilometers
    using the Haversine formula.
    """
    if lat1 == lat2 and lon1 == lon2:
        return 0.0

    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(EARTH_RADIUS_KM * c, 3)

def recompute_delivery_clusters(db: Session):
    """
    Groups all registered shops into 1 km radius delivery clusters.
    Assigns or updates a shared DeliveryPerson per cluster, and recalculates
    each shop's share of the monthly salary.
    """
    shops = db.query(Shop).all()
    if not shops:
        return

    # Reset existing cluster assignments temporarily to re-cluster cleanly
    visited = set()
    clusters = []  # List of lists of Shop objects

    for shop in shops:
        if shop.id in visited:
            continue
        
        # New cluster starting with this shop
        current_cluster = [shop]
        visited.add(shop.id)

        # Find all other unvisited shops within 1 km of ANY shop in this cluster (connected component)
        queue = [shop]
        while queue:
            curr = queue.pop(0)
            for other in shops:
                if other.id not in visited:
                    dist = haversine_distance(curr.latitude, curr.longitude, other.latitude, other.longitude)
                    if dist <= 1.0:  # 1 km radius
                        visited.add(other.id)
                        current_cluster.append(other)
                        queue.append(other)

        clusters.append(current_cluster)

    # Now update database clusters
    # Existing clusters
    existing_clusters = db.query(DeliveryCluster).all()
    cluster_idx = 0

    for cluster_shops in clusters:
        cluster_idx += 1
        cluster_name = f"Cluster {cluster_idx} ({len(cluster_shops)} Shops)"
        
        # Find or create DeliveryCluster
        if cluster_idx <= len(existing_clusters):
            db_cluster = existing_clusters[cluster_idx - 1]
            db_cluster.name = cluster_name
        else:
            db_cluster = DeliveryCluster(name=cluster_name)
            db.add(db_cluster)
            db.flush()

        # Assign all shops in this group to db_cluster
        for s in cluster_shops:
            s.cluster_id = db_cluster.id

        # Ensure a delivery person exists for this cluster
        dp = db.query(DeliveryPerson).filter(DeliveryPerson.cluster_id == db_cluster.id).first()
        if not dp:
            dp = DeliveryPerson(
                cluster_id=db_cluster.id,
                name=f"Rider {cluster_idx} (Shared)",
                phone=f"987654321{cluster_idx % 10}",
                monthly_salary=12000.0,
                status="active"
            )
            db.add(dp)

    # Any extra clusters that have no shops now can have shops unassigned
    db.commit()

def get_shop_delivery_details(db: Session, shop_id: int):
    """
    Returns the cluster details for a given shop:
    - cluster shops
    - delivery person name and total monthly salary
    - number of shops sharing
    - this shop's split share
    """
    shop = db.query(Shop).filter(Shop.id == shop_id).first()
    if not shop:
        return None

    if not shop.cluster_id:
        return {
            "has_cluster": False,
            "message": "Shop does not belong to any delivery cluster yet."
        }

    cluster = db.query(DeliveryCluster).filter(DeliveryCluster.id == shop.cluster_id).first()
    if not cluster:
        return {
            "has_cluster": False,
            "message": "No active cluster found."
        }

    cluster_shops = db.query(Shop).filter(Shop.cluster_id == cluster.id).all()
    delivery_person = db.query(DeliveryPerson).filter(DeliveryPerson.cluster_id == cluster.id).first()

    total_shops = len(cluster_shops)
    monthly_salary = delivery_person.monthly_salary if delivery_person else 12000.0
    shop_share = round(monthly_salary / max(total_shops, 1), 2)

    return {
        "has_cluster": True,
        "cluster_id": cluster.id,
        "cluster_name": cluster.name,
        "delivery_person_name": delivery_person.name if delivery_person else "Assigned Rider",
        "delivery_person_phone": delivery_person.phone if delivery_person else "N/A",
        "total_monthly_salary": monthly_salary,
        "total_shops_sharing": total_shops,
        "this_shop_share": shop_share,
        "shops": [
            {
                "id": s.id,
                "name": s.name,
                "owner_name": s.owner_name,
                "phone": s.phone,
                "address": s.address,
                "is_current_shop": (s.id == shop.id)
            }
            for s in cluster_shops
        ]
    }
