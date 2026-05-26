from .sources import dutchie, leafly, weedmaps, iheartjane
from .pek.filter import compute_pek, dedupe_by_pek
from .pek.normalize import normalize_product
from .db.supabase_client import upsert_products

SOURCE_MAP = {
    "dutchie": dutchie.scrape,
    "leafly": leafly.scrape,
    "weedmaps": weedmaps.scrape,
    "iheartjane": iheartjane.scrape,
}

def detect_source(url: str) -> str:
    for k in SOURCE_MAP:
        if k in url:
            return k
    raise ValueError(f"Unknown menu source for {url}")

async def scrape_only(menu_url: str, source: str = "auto"):
    src = detect_source(menu_url) if source == "auto" else source
    products = await SOURCE_MAP[src](menu_url)
    return {"source": src, "count": len(products), "products": products}

def normalize_only(products):
    normalized = [normalize_product(p) for p in products]
    for p in normalized:
        p["pek_hash"] = compute_pek(p)
    deduped = dedupe_by_pek(normalized)
    return {"normalized": deduped, "raw_count": len(products), "deduped_count": len(deduped)}

async def run_full_pipeline(menu_url, dispensary_id, source="auto"):
    raw = await scrape_only(menu_url, source)
    norm = normalize_only(raw["products"])
    for p in norm["normalized"]:
        p["dispensary_id"] = dispensary_id
        p["source"] = raw["source"]
    result = upsert_products(norm["normalized"])
    return {"scraped": raw["count"], "upserted": result["upserted"], "deduped": norm["deduped_count"]}
