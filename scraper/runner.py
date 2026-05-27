from .sources import aiq, blaze, carrot, dutchie, goodlife, jane, kushmart, proteus420, weedmaps
from .pek.filter import compute_pek, dedupe_by_pek
from .pek.normalize import normalize_product
from .db.supabase_client import upsert_products

SOURCE_MAP = {
    "aiq":        aiq.scrape,
    "blaze":      blaze.scrape,
    "carrot":     carrot.scrape,
    "dutchie":    dutchie.scrape,
    "goodlife":   goodlife.scrape,
    "jane":       jane.scrape,
    "kushmart":   kushmart.scrape,
    "proteus420": proteus420.scrape,
    "weedmaps":   weedmaps.scrape,
}

URL_HINTS = {
    "aiq":        ["aiqsolutions", "aiq."],
    "blaze":      ["blaze"],
    "carrot":     ["carrotsoftware", "carrot."],
    "dutchie":    ["dutchie"],
    "goodlife":   ["goodlife"],
    "jane":       ["iheartjane", "jane."],
    "kushmart":   ["kushmart"],
    "proteus420": ["proteus420", "proteus"],
    "weedmaps":   ["weedmaps"],
}

def detect_source(url: str) -> str:
    url_lower = url.lower()
    for src, hints in URL_HINTS.items():
        if any(h in url_lower for h in hints):
            return src
    raise ValueError(f"Unknown menu source for URL: {url}")

async def scrape_only(menu_url: str, source: str = "auto"):
    src = detect_source(menu_url) if source == "auto" else source
    if src not in SOURCE_MAP:
        raise ValueError(f"Unsupported source: {src}. Valid: {list(SOURCE_MAP)}")
    products = await SOURCE_MAP[src](menu_url)
    return {"source": src, "count": len(products), "products": products}

def normalize_only(products: list) -> dict:
    normalized = [normalize_product(p) for p in products]
    for p in normalized:
        p["pek_hash"] = compute_pek(p)
    deduped = dedupe_by_pek(normalized)
    return {"normalized": deduped, "raw_count": len(products), "deduped_count": len(deduped)}

async def run_full_pipeline(menu_url: str, dispensary_id: str, source: str = "auto") -> dict:
    raw = await scrape_only(menu_url, source)
    norm = normalize_only(raw["products"])
    for p in norm["normalized"]:
        p["dispensary_id"] = dispensary_id
        p["source"] = raw["source"]
    result = upsert_products(norm["normalized"])
    return {
        "scraped": raw["count"],
        "upserted": result["upserted"],
        "deduped": norm["deduped_count"],
        "source": raw["source"],
    }
