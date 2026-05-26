How it works
The scraper reverse-engineers the Carrot dispensary CMS API (api.nevada.getcarrot.io/api/v1) used by all 5 storefronts:
1. Auto-detects CARROT_SPACE_ID and CARROT_API_URL from each store's HTML at runtime (using curl_cffi with Chrome TLS fingerprinting to bypass Cloudflare/rate-limits)
2. Hits 3 endpoints per dispensary: /store/locations → /store/category → /store/category/slug/{slug}/product
3. Sends required headers: Carrot-Space-Id, Carrot-Anonymous-Id (UUID4), Origin, Referer
4. Outputs one JSON file per category under output/<dispensary_name>/
Per-product fields captured


Field
	Description
	product_id, name, brand, sku, slug
	Identity
	category, subcategory, strain, strain_type
	Classification
	quantity_in_stock
	Live inventory count from POS
	pos_price, pricing_options
	Pricing with size tiers
	lab_results
	THC/CBD/CBG/etc. as {pct, mg}
	image_urls
	Full CDN URLs
	description, tags, unit_weight
	Details
	Dependency: pip install curl_cffi


"""
Carrot Dispensary Scraper
=========================
Scrapes full product inventory from Carrot-powered cannabis dispensary storefronts.
Exports one JSON file per product category, per dispensary.


Requires:
    pip install curl_cffi


Usage:
    python carrot_scraper.py


Output:
    ./output/<dispensary_name>/<category_slug>.json
    ./output/<dispensary_name>/_manifest.json   (per-dispensary summary)
    ./output/_summary.json                       (overall run summary)
"""


import json
import re
import time
import uuid
import logging
from pathlib import Path


from curl_cffi import requests as cffi_requests


# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ── Dispensary definitions ────────────────────────────────────────────────────
# space_id / api_url are auto-detected from the store page at runtime.
# You can hard-code them here to skip detection (faster, avoids rate-limits).
DISPENSARIES = [
    {
        "name": "greensidecannabis",
        "display_name": "Greenside Cannabis",
        "store_url": "https://greensidecannabis.com/store/",
        "space_id": "371",                                       # known
        "api_url": "https://api.nevada.getcarrot.io/api/v1",    # known
    },
    {
        "name": "premierearth",
        "display_name": "Premier Earth",
        "store_url": "https://premierearth.com/store/",
        "space_id": None,   # auto-detected
        "api_url": None,
    },
    {
        "name": "tcvbuff",
        "display_name": "TCV Buff",
        "store_url": "https://tcvbuff.com/store/",
        "space_id": None,
        "api_url": None,
    },
    {
        "name": "thejointcannabisdispensary",
        "display_name": "The Joint Cannabis Dispensary",
        "store_url": "https://thejointcannabisdispensary.com/store/",
        "space_id": None,
        "api_url": None,
    },
    {
        "name": "yeticanna",
        "display_name": "Yeti Canna",
        "store_url": "https://yeticanna.com/store/",
        "space_id": None,
        "api_url": None,
    },
]


OUTPUT_DIR = Path("output")
DEFAULT_API_URL = "https://api.nevada.getcarrot.io/api/v1"
REQUEST_DELAY = 0.4   # seconds between API calls


# ── HTTP helpers ──────────────────────────────────────────────────────────────


def make_session(site_url: str, space_id: str) -> cffi_requests.Session:
    """
    Return a curl_cffi Session with Chrome TLS fingerprinting and the
    required Carrot request headers.
    """
    session = cffi_requests.Session(impersonate="chrome120")
    session.headers.update({
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Origin": site_url.rstrip("/"),
        "Referer": site_url,
        "Carrot-Space-Id": str(space_id),
        "Carrot-Anonymous-Id": str(uuid.uuid4()),
    })
    return session




def api_get(session: cffi_requests.Session, url: str,
            params: dict = None, retries: int = 3) -> dict | list | None:
    """GET with retry; returns parsed JSON or None."""
    for attempt in range(1, retries + 1):
        try:
            resp = session.get(url, params=params, timeout=30)
            if resp.status_code == 200:
                return resp.json()
            log.warning("HTTP %s on %s (attempt %d)", resp.status_code, url, attempt)
        except Exception as exc:
            log.warning("Request error %s (attempt %d): %s", url, attempt, exc)
        time.sleep(2 ** attempt)
    return None




# ── Config auto-detection ─────────────────────────────────────────────────────


def detect_carrot_config(store_url: str) -> tuple[str | None, str | None]:
    """
    Fetch the dispensary store page with Chrome fingerprinting and extract:
      - Carrot space ID  (CARROT_SPACE_ID  or  carrotSpaceId)
      - Carrot API base URL  (CARROT_API_URL)
    Returns (space_id, api_url).
    """
    try:
        resp = cffi_requests.get(store_url, impersonate="chrome120", timeout=20)
        html = resp.text
    except Exception as exc:
        log.error("Could not fetch store page %s: %s", store_url, exc)
        return None, None


    sid_matches = re.findall(
        r'(?:carrotSpaceId|CARROT_SPACE_ID)\s*[=:]\s*["\']?(\d+)["\']?',
        html
    )
    space_id = sid_matches[0] if sid_matches else None


    api_matches = re.findall(r'CARROT_API_URL\s*=\s*["\']([^"\']+)["\']', html)
    if not api_matches:
        api_matches = re.findall(
            r'https://api\.[a-z0-9-]+\.getcarrot\.io/api/v\d+', html
        )
    api_url = api_matches[0] if api_matches else DEFAULT_API_URL


    return space_id, api_url




# ── Data parsers ──────────────────────────────────────────────────────────────


def parse_lab_results(raw: list) -> dict:
    """Flatten labResults array into {compound: {percentage, mg}} dict."""
    labs: dict[str, dict] = {}
    for entry in raw:
        lab_test = entry.get("labTest", {})
        compound = next(iter(lab_test), None)
        if compound == "Other":
            compound = lab_test["Other"].get("value", "Unknown")
        value = entry.get("value", 0)
        unit_block = entry.get("labResultUnit", {})
        unit = next(iter(unit_block), "Unknown")


        if compound not in labs:
            labs[compound] = {}
        if "Percentage" in unit:
            labs[compound]["percentage"] = value
        elif "Milligrams" in unit:
            labs[compound]["mg"] = value
        else:
            labs[compound][unit] = value
    return labs




def parse_product(entry: dict) -> dict:
    """Convert a raw Carrot API product entry into a clean structured dict."""
    product = entry.get("product", {})
    options = entry.get("cashOptions") or entry.get("creditOptions") or []


    pricing = [
        {
            "display_name": o.get("displayName"),
            "quantity": o.get("qty"),
            "price": o.get("price"),
            "thc_weight": o.get("thcWeight"),
        }
        for o in options
    ]


    image_hashes = product.get("imageHashes", [])
    image_urls = [
        f"https://carrot-static.ams3.digitaloceanspaces.com/{h['imageHash']}"
        for h in image_hashes
        if isinstance(h, dict) and h.get('imageHash')
    ]


    return {
        "product_id":        product.get("productId"),
        "name":              product.get("name"),
        "brand":             product.get("brand"),
        "sku":               product.get("sku"),
        "slug":              product.get("slug"),
        "category":          product.get("masterCategoryName") or product.get("carrotSubcategory"),
        "subcategory":       product.get("subcategoryName") or product.get("carrotSubcategory"),
        "strain":            product.get("strain"),
        "strain_type":       product.get("strainType"),
        "unit_weight":       product.get("unitWeight"),
        "quantity_in_stock": product.get("qty"),
        "pos_price":         product.get("posPrice"),
        "pricing_options":   pricing,
        "location_id":       product.get("locationId"),
        "location_name":     product.get("locationName"),
        "description":       (product.get("description") or "").strip() or None,
        "lab_results":       parse_lab_results(product.get("labResults", [])),
        "image_urls":        image_urls,
        "tags":              product.get("tags", []),
        "sort_order":        product.get("sort"),
        "scraped_at":        time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }




# ── Core scraping logic ───────────────────────────────────────────────────────


def scrape_dispensary(dispensary: dict) -> dict[str, list]:
    """
    Scrape all categories and their products for one dispensary.
    Returns {category_slug: [parsed_product, ...]}
    """
    name      = dispensary["name"]
    store_url = dispensary["store_url"]
    space_id  = dispensary.get("space_id")
    api_url   = dispensary.get("api_url")


    if not space_id or not api_url:
        log.info("[%s] Auto-detecting Carrot config from %s …", name, store_url)
        detected_id, detected_api = detect_carrot_config(store_url)
        space_id = space_id or detected_id
        api_url  = api_url  or detected_api or DEFAULT_API_URL


    if not space_id:
        log.error("[%s] Could not detect space_id — skipping.", name)
        return {}


    log.info("[%s] space_id=%s  api=%s", name, space_id, api_url)


    session = make_session(store_url, space_id)


    # 1. Locations
    loc_data = api_get(session, f"{api_url}/store/locations", {"platform": "web"})
    if not loc_data or not loc_data.get("locations"):
        log.error("[%s] No locations returned — skipping.", name)
        return {}


    location = loc_data["locations"][0]
    loc_id   = location["id"]
    log.info("[%s] Location: %s (id=%s)", name, location["name"], loc_id)
    time.sleep(REQUEST_DELAY)


    # 2. Categories
    categories = api_get(session, f"{api_url}/store/category",
                         {"locId": loc_id, "platform": "web"})
    if not categories:
        log.error("[%s] No categories returned — skipping.", name)
        return {}


    visible = [c for c in categories if c.get("showWeb", True)]
    log.info("[%s] %d categories found.", name, len(visible))
    time.sleep(REQUEST_DELAY)


    results: dict[str, list] = {}


    # 3. Products per category
    for cat in visible:
        slug   = cat["slug"]
        master = cat.get("master", slug)
        log.info("[%s] Fetching category: %s …", name, master)


        raw = api_get(
            session,
            f"{api_url}/store/category/slug/{slug}/product",
            {"locId": loc_id, "platform": "web"},
        )
        time.sleep(REQUEST_DELAY)


        if raw is None:
            log.warning("[%s] No data for '%s'.", name, slug)
            results[slug] = []
        else:
            results[slug] = [parse_product(p) for p in raw]
            log.info("[%s]   → %d products in '%s'.", name, len(results[slug]), master)


    return results




# ── Output helpers ────────────────────────────────────────────────────────────


def save_results(dispensary_name: str, data: dict[str, list]):
    """Write each category as its own JSON file; also write a manifest."""
    out_dir = OUTPUT_DIR / dispensary_name
    out_dir.mkdir(parents=True, exist_ok=True)


    for slug, products in data.items():
        out_file = out_dir / f"{slug}.json"
        with open(out_file, "w", encoding="utf-8") as fh:
            json.dump(products, fh, indent=2, ensure_ascii=False)
        log.info("  Saved %4d products → %s", len(products), out_file)


    manifest = {
        "dispensary":     dispensary_name,
        "scraped_at":     time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "categories":     {s: {"product_count": len(p)} for s, p in data.items()},
        "total_products": sum(len(p) for p in data.values()),
    }
    manifest_file = out_dir / "_manifest.json"
    with open(manifest_file, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
    log.info("  Manifest saved → %s", manifest_file)




# ── Entry point ───────────────────────────────────────────────────────────────


def main():
    log.info("=== Carrot Dispensary Scraper ===")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


    summary = []


    for dispensary in DISPENSARIES:
        log.info("")
        log.info("── Scraping: %s ──", dispensary["display_name"])


        try:
            data = scrape_dispensary(dispensary)
        except Exception as exc:
            log.exception("Unexpected error scraping %s: %s", dispensary["name"], exc)
            data = {}


        if data:
            save_results(dispensary["name"], data)
            summary.append({
                "dispensary":     dispensary["display_name"],
                "name":           dispensary["name"],
                "categories":     len(data),
                "total_products": sum(len(v) for v in data.values()),
                "status":         "ok",
            })
        else:
            summary.append({
                "dispensary":     dispensary["display_name"],
                "name":           dispensary["name"],
                "categories":     0,
                "total_products": 0,
                "status":         "failed",
            })


    log.info("")
    log.info("=== Summary ===")
    for s in summary:
        log.info("%-40s %3d categories  %4d products  [%s]",
                 s["dispensary"], s["categories"], s["total_products"], s["status"])


    with open(OUTPUT_DIR / "_summary.json", "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)
    log.info("Summary saved → %s", OUTPUT_DIR / "_summary.json")




if __name__ == "__main__":
    main()
