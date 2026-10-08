import json
import logging
from typing import List, Dict, Any, Optional
import httpx
from backend.config import (
    AZURE_OPENAI_ENDPOINT,
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_DEPLOYMENT_NAME,
    AZURE_OPENAI_API_VERSION,
)

logger = logging.getLogger("AgoraZure.AI")

def is_azure_configured() -> bool:
    """Check if Azure OpenAI credentials are set."""
    return bool(AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY and AZURE_OPENAI_DEPLOYMENT_NAME)

async def call_azure_openai_chat(messages: List[Dict[str, str]], temperature: float = 0.3) -> Optional[str]:
    """Call Azure OpenAI Chat Completions REST API directly."""
    if not is_azure_configured():
        return None

    url = (
        f"{AZURE_OPENAI_ENDPOINT.rstrip('/')}/openai/deployments/"
        f"{AZURE_OPENAI_DEPLOYMENT_NAME}/chat/completions"
        f"?api-version={AZURE_OPENAI_API_VERSION}"
    )
    headers = {
        "api-key": AZURE_OPENAI_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "messages": messages,
        "temperature": temperature,
        "max_tokens": 800,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                return data["choices"][0]["message"]["content"].strip()
            else:
                logger.warning(f"Azure OpenAI call returned status {resp.status_code}: {resp.text}")
                return None
    except Exception as e:
        logger.warning(f"Azure OpenAI call failed: {e}. Falling back to rule-based engine.")
        return None

# =========================================================================
# 1. DEMAND INSIGHTS (Stocking Advice from Missed Searches)
# =========================================================================

async def generate_demand_insights(missed_searches_summary: List[Dict[str, Any]], shop_name: str) -> List[Dict[str, Any]]:
    """
    Generates commercial stocking advice for the shopkeeper based on missed searches.
    Falls back to a structured rule-based response if Azure OpenAI is unavailable.
    """
    if not missed_searches_summary:
        return [
            {
                "term": "N/A",
                "count": 0,
                "urgency": "Low",
                "advice": "No missed searches recorded yet. Keep your catalog updated to capture real-time shopper intent."
            }
        ]

    # Try Azure OpenAI first
    if is_azure_configured():
        prompt = (
            f"You are AgoraZure's Smart Commerce retail analytics AI assistant for shop '{shop_name}'.\n"
            f"Here are recent customer searches that found 0 stock or were unstocked:\n"
            f"{json.dumps(missed_searches_summary, indent=2)}\n\n"
            f"Generate concise, high-impact stocking advice for each product. "
            f"Return a strict JSON array of objects with keys:\n"
            f"- 'term': the search query\n"
            f"- 'count': number of searches\n"
            f"- 'urgency': 'High', 'Medium', or 'Low'\n"
            f"- 'advice': e.g. '12 shoppers searched for X this week - consider stocking it to capture ~₹1,500 unmet demand.'\n"
            f"Respond with JSON ONLY without markdown fences."
        )

        messages = [
            {"role": "system", "content": "You are a retail commerce inventory advisor. Return valid JSON only."},
            {"role": "user", "content": prompt}
        ]
        response_text = await call_azure_openai_chat(messages)
        if response_text:
            try:
                # Clean any markdown block formatting
                clean_json = response_text.replace("```json", "").replace("```", "").strip()
                parsed = json.loads(clean_json)
                if isinstance(parsed, list):
                    return parsed
            except Exception as e:
                logger.warning(f"Failed to parse Azure OpenAI JSON response: {e}")

    # Rule-based fallback
    insights = []
    for item in missed_searches_summary:
        term = item.get("term", "Product")
        count = item.get("count", 1)
        
        if count >= 8:
            urgency = "High"
            est_demand = count * 150
            advice = f"🔥 {count} shoppers searched for '{term}' this week! High unmet demand — stocking 10-15 units could yield ~₹{est_demand} in quick sales."
        elif count >= 3:
            urgency = "Medium"
            est_demand = count * 90
            advice = f"⚡ {count} shoppers looked for '{term}'. Emerging demand detected — consider stocking a trial batch to capture ~₹{est_demand}."
        else:
            urgency = "Low"
            advice = f"📌 {count} customer searched for '{term}'. Monitor next 7 days or test a small stock."

        insights.append({
            "term": term,
            "count": count,
            "urgency": urgency,
            "advice": advice
        })

    return insights

# =========================================================================
# 2. SMART SUBSTITUTES (Alternatives when item is Out of Stock)
# =========================================================================

async def suggest_substitutes(
    out_of_stock_item: str,
    available_catalog: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    When a product is out of stock, suggests available alternatives from nearby shops.
    Uses Azure OpenAI if configured, otherwise uses intelligent rule-based ranking.
    """
    if not available_catalog:
        return []

    if is_azure_configured():
        prompt = (
            f"A customer is searching for '{out_of_stock_item}', which is currently out of stock.\n"
            f"Here is the list of available products in nearby shops:\n"
            f"{json.dumps(available_catalog[:15], indent=2)}\n\n"
            f"Pick the top 1-3 best substitutes that a shopper would realistically accept (same category, use-case, or similar brand).\n"
            f"Return a strict JSON array of objects with keys:\n"
            f"- 'product_id': id of the product\n"
            f"- 'product_name': name of substitute\n"
            f"- 'shop_name': shop name\n"
            f"- 'price': price in INR\n"
            f"- 'distance_km': distance in km\n"
            f"- 'reason': Why this is a great substitute (e.g. 'Similar premium whole milk available only 0.4 km away at Green Grocers')\n"
            f"Respond with JSON ONLY without code fences."
        )

        messages = [
            {"role": "system", "content": "You are an AI grocery and retail assistant that suggests high-relevance product substitutes. Return JSON only."},
            {"role": "user", "content": prompt}
        ]
        response_text = await call_azure_openai_chat(messages)
        if response_text:
            try:
                clean_json = response_text.replace("```json", "").replace("```", "").strip()
                parsed = json.loads(clean_json)
                if isinstance(parsed, list) and len(parsed) > 0:
                    return parsed
            except Exception as e:
                logger.warning(f"Failed to parse Azure substitutes JSON: {e}")

    # Rule-based fallback: match keyword overlap and category
    substitutes = []
    item_tokens = set(out_of_stock_item.lower().split())

    scored_items = []
    for item in available_catalog:
        name_lower = item.get("name", "").lower()
        cat_lower = item.get("category", "").lower()
        score = 0

        # Check word overlaps
        for tok in item_tokens:
            if tok in name_lower:
                score += 3
            if tok in cat_lower:
                score += 2

        # Check if in same category
        if any(tok in cat_lower for tok in item_tokens):
            score += 2

        if score > 0 or len(scored_items) < 3:
            scored_items.append((score, item))

    # Sort descending by score
    scored_items.sort(key=lambda x: x[0], reverse=True)

    for score, item in scored_items[:3]:
        substitutes.append({
            "product_id": item.get("id"),
            "product_name": item.get("name"),
            "shop_name": item.get("shop_name", "Nearby Partner"),
            "price": item.get("price"),
            "distance_km": item.get("distance_km", 0.5),
            "reason": f"Popular in {item.get('category', 'same category')} — in stock at {item.get('shop_name', 'nearby shop')} ({item.get('distance_km', 0.5)} km away)."
        })

    return substitutes
