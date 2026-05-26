How It Works


The Jane platform uses iHeartJane's Algolia search index (menu-products-production) hosted at search.iheartjane.com. The scraper Fetches live Algolia credentials (App ID + API key) directly from each dispensary's HTML — no hardcoding required for future credential rotations
Queries the Algolia index filtered by store_id, handling pagination automatically (up to 1000 results/page)
Uses curl_cffi with Chrome TLS impersonation to bypass Cloudflare/CDN protections
Exports clean JSON organized by category with full product details
Each product record includes:
Name, brand, category/subcategory, description, strain, store notes
Prices (regular, discounted, special) per weight (gram, 1/8oz, 1/4oz, etc.)
THC%, THCA%, CBD%, TAC% potency
Effects, flavors, terpenes, feelings, activities
Dosage, quantity, net weight, max cart quantity
Pickup/delivery availability, aggregate rating, review count
Photos (small/medium/large/original URLs)
POS product lookup IDs, lab results






#!/usr/bin/env python3
"""
Jane Platform Cannabis Dispensary Inventory Scraper
Supports: Buffalo Dreams (shopbuffalodreams.com) and Stoned House NY (stonedhouseny.com)


Uses the iHeartJane (Jane platform) Algolia search API to fetch full product inventory.
curl_cffi is used for HTTP requests to bypass CDN/anti-bot protections.
"""


import json
import re
import sys
import argparse
from datetime import datetime
from pathlib import Path


try:
    from curl_cffi import requests as cffi_requests
    USE_CURL_CFFI = True
except ImportError:
    import requests as cffi_requests
    USE_CURL_CFFI = False
    print("[WARNING] curl_cffi not installed. Falling back to requests. Install with: pip install curl_cffi")




# ─── Configuration ────────────────────────────────────────────────────────────


DISPENSARIES = {
    "buffalo_dreams": {
        "name": "Buffalo Dreams",
        "store_id": 5876,
        "store_url": "https://shopbuffalodreams.com/shop/",
        "jane_store_url": "https://www.iheartjane.com/stores/5876/buffalo-dreams/menu",
    },
    "stoned_house_ny": {
        "name": "Stoned House NY",
        "store_id": 6928,
        "store_url": "https://stonedhouseny.com/order-online/menu/",
        "jane_store_url": "https://www.iheartjane.com/stores/6928",
    },
}


ALGOLIA_INDEX = "menu-products-production"
ALGOLIA_SEARCH_URL = "https://search.iheartjane.com/1/indexes/{index}/query"
ALGOLIA_AGENT = "Algolia for JavaScript (4.26.0); Browser"


JANE_SITE_URL = "https://www.iheartjane.com/"
HITS_PER_PAGE = 1000  # Max allowed by Algolia




# ─── Helper: Resolve Algolia credentials from Jane page ───────────────────────


def get_algolia_credentials(store_url: str) -> dict:
    """
    Fetch the dispensary's website and extract live Algolia App ID + API key.
    Falls back to hardcoded credentials if extraction fails.
    """
    fallback = {
        "app_id": "VFM4X0N23A",
        "api_key": "edc5435c65d771cecbd98bbd488aa8d3",
    }
    try:
        print(f"  Fetching Algolia credentials from {store_url} ...")
        if USE_CURL_CFFI:
            resp = cffi_requests.get(store_url, impersonate="chrome", timeout=15)
        else:
            resp = cffi_requests.get(store_url, timeout=15)
        
        html = resp.text
        
        # Extract App ID from settings JSON block
        app_id_match = re.search(r'algoliaAppId["\s:]+["\']([A-Z0-9]{8,})["\']', html)
        # Extract API key from secrets JSON block
        api_key_match = re.search(r'algoliaApiKey["\s:]+["\']([a-f0-9]{30,})["\']', html)
        
        if app_id_match and api_key_match:
            creds = {"app_id": app_id_match.group(1), "api_key": api_key_match.group(1)}
            print(f"  ✓ Credentials extracted: App ID={creds['app_id']}")
            return creds
        else:
            print(f"  ⚠ Could not extract credentials from page, using fallback.")
            return fallback
    except Exception as e:
        print(f"  ⚠ Error fetching credentials: {e}. Using fallback.")
        return fallback




# ─── Core: Fetch products from Algolia ────────────────────────────────────────


def fetch_products(store_id: int, credentials: dict) -> list:
    """
    Fetch all products for a given store from Jane's Algolia search index.
    Handles pagination automatically.
    """
    all_hits = []
    page = 0
    total_pages = None


    headers = {
        "X-Algolia-Application-Id": credentials["app_id"],
        "X-Algolia-API-Key": credentials["api_key"],
        "Content-Type": "application/json",
        "Referer": JANE_SITE_URL,
        "Origin": JANE_SITE_URL.rstrip("/"),
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }


    url = (
        ALGOLIA_SEARCH_URL.format(index=ALGOLIA_INDEX)
        + f"?x-algolia-agent={ALGOLIA_AGENT.replace(' ', '%20').replace('(', '%28').replace(')', '%29').replace(';', '%3B')}"
    )


    while True:
        payload = {
            "query": "",
            "filters": f"store_id:{store_id}",
            "hitsPerPage": HITS_PER_PAGE,
            "page": page,
        }


        try:
            if USE_CURL_CFFI:
                resp = cffi_requests.post(
                    url,
                    headers=headers,
                    json=payload,
                    impersonate="chrome",
                    timeout=30,
                )
            else:
                resp = cffi_requests.post(url, headers=headers, json=payload, timeout=30)
            
            resp.raise_for_status()
            data = resp.json()


        except Exception as e:
            print(f"  ✗ Error fetching page {page}: {e}")
            break


        hits = data.get("hits", [])
        all_hits.extend(hits)


        if total_pages is None:
            total_pages = data.get("nbPages", 1)
            total_hits = data.get("nbHits", 0)
            print(f"  Found {total_hits} products across {total_pages} page(s)")


        print(f"  Page {page + 1}/{total_pages}: fetched {len(hits)} products (running total: {len(all_hits)})")


        if page >= total_pages - 1:
            break
        page += 1


    return all_hits




# ─── Extraction: Parse Algolia hit into clean product dict ────────────────────


def extract_product(hit: dict) -> dict:
    """Convert a raw Algolia hit into a clean, structured product record."""
    prices = {}
    for weight in ["gram", "half_gram", "two_gram", "eighth_ounce", "quarter_ounce",
                   "half_ounce", "ounce", "each"]:
        regular = hit.get(f"price_{weight}")
        if regular is not None:
            prices[weight] = {
                "regular": regular,
                "discounted": hit.get(f"discounted_price_{weight}"),
                "special": hit.get(f"special_price_{weight}"),
                "max_cart_quantity": hit.get(f"max_cart_quantity_{weight}"),
            }


    image_urls = hit.get("image_urls") or []
    product_photos = hit.get("product_photos") or []


    # Build photo list with size variants
    photos = []
    for photo in product_photos:
        urls = photo.get("urls", {})
        photos.append({
            "small": urls.get("small"),
            "medium": urls.get("medium"),
            "original": urls.get("original"),
            "extraLarge": urls.get("extraLarge"),
        })
    if not photos and image_urls:
        photos = [{"original": u} for u in image_urls]


    return {
        "id": hit.get("product_id"),
        "objectID": hit.get("objectID"),
        "name": hit.get("name"),
        "brand": hit.get("brand"),
        "category": hit.get("kind"),
        "subcategory": hit.get("kind_subtype") or hit.get("root_subtype"),
        "custom_product_type": hit.get("custom_product_type"),
        "description": hit.get("description"),
        "strain": hit.get("strain"),
        "store_notes": hit.get("store_notes"),
        # Pricing
        "prices": prices,
        "available_weights": hit.get("available_weights", []),
        "bucket_price": hit.get("bucket_price"),
        "sort_price": hit.get("sort_price"),
        "special_title": hit.get("special_title"),
        "special_id": hit.get("special_id"),
        # Potency
        "percent_thc": hit.get("percent_thc"),
        "percent_thca": hit.get("percent_thca"),
        "percent_cbd": hit.get("percent_cbd"),
        "percent_cbda": hit.get("percent_cbda"),
        "percent_tac": hit.get("percent_tac"),
        "inventory_potencies": hit.get("inventory_potencies", []),
        # Characteristics
        "effects": hit.get("effects", []),
        "flavors": hit.get("flavors", []),
        "terpenes": hit.get("terpenes", []),
        "feelings": hit.get("feelings", []),
        "activities": hit.get("activities", []),
        "cannabinoids": hit.get("cannabinoids", []),
        "allergens": hit.get("allergens", []),
        "ingredients": hit.get("ingredients", []),
        # Quantity / weight
        "dosage": hit.get("dosage"),
        "amount": hit.get("amount"),
        "quantity_value": hit.get("quantity_value"),
        "quantity_units": hit.get("quantity_units"),
        "net_weight_grams": hit.get("net_weight_grams"),
        "max_cart_quantity": hit.get("max_cart_quantity"),
        # Availability
        "available_for_delivery": hit.get("available_for_delivery"),
        "available_for_pickup": hit.get("available_for_pickup"),
        "store_types": hit.get("store_types", []),
        # Ratings
        "aggregate_rating": hit.get("aggregate_rating"),
        "review_count": hit.get("review_count"),
        # Media
        "photos": photos,
        # Identifiers
        "url_slug": hit.get("url_slug"),
        "searchable_slug": hit.get("searchable_slug"),
        "store_specific_product": hit.get("store_specific_product"),
        "pos_product_lookup": hit.get("pos_product_lookup"),
        "product_brand_id": hit.get("product_brand_id"),
        # Lab / compliance
        "lab_results": hit.get("lab_results", []),
        "lab_result_urls": hit.get("lab_result_urls", []),
        "business_licenses": hit.get("business_licenses", []),
        # Meta
        "indexed_at": hit.get("indexed_at"),
        "version": hit.get("version"),
    }




# ─── Organize products by category ────────────────────────────────────────────


def organize_by_category(raw_hits: list) -> dict:
    """Group and sort extracted products by category."""
    by_category = {}
    for hit in raw_hits:
        product = extract_product(hit)
        category = product["category"] or "unknown"
        by_category.setdefault(category, []).append(product)


    for category in by_category:
        by_category[category].sort(key=lambda p: (p["name"] or "").lower())


    return by_category




# ─── Main scraper ─────────────────────────────────────────────────────────────


def scrape_dispensary(key: str, config: dict, output_dir: Path) -> dict:
    """Scrape a single dispensary and save results to a JSON file."""
    name = config["name"]
    store_id = config["store_id"]


    print(f"\n{'='*60}")
    print(f"  Scraping: {name} (store_id={store_id})")
    print(f"{'='*60}")


    # Step 1: Get live Algolia credentials from the dispensary's website
    credentials = get_algolia_credentials(config["store_url"])


    # Step 2: Fetch all products from Algolia
    raw_hits = fetch_products(store_id, credentials)


    # Step 3: Organize by category
    inventory = organize_by_category(raw_hits)


    # Step 4: Build output structure
    category_summary = {cat: len(products) for cat, products in inventory.items()}
    output = {
        "dispensary": name,
        "store_id": store_id,
        "store_url": config["store_url"],
        "jane_store_url": config["jane_store_url"],
        "total_products": len(raw_hits),
        "categories": category_summary,
        "scraped_at": datetime.utcnow().isoformat() + "Z",
        "inventory": inventory,
    }


    # Step 5: Save to file
    filename = output_dir / f"{key}_inventory.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)


    print(f"  ✓ Saved {len(raw_hits)} products to {filename}")
    print(f"  Category breakdown: {category_summary}")


    return output




def main():
    parser = argparse.ArgumentParser(
        description="Scrape cannabis dispensary inventory from Jane platform stores"
    )
    parser.add_argument(
        "--stores",
        nargs="+",
        choices=list(DISPENSARIES.keys()) + ["all"],
        default=["all"],
        help="Which store(s) to scrape (default: all)",
    )
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Directory to save JSON output files (default: current directory)",
    )
    args = parser.parse_args()


    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)


    stores_to_scrape = (
        list(DISPENSARIES.keys())
        if "all" in args.stores
        else args.stores
    )


    print(f"\nJane Platform Dispensary Inventory Scraper")
    print(f"Using curl_cffi: {USE_CURL_CFFI}")
    print(f"Stores to scrape: {stores_to_scrape}")
    print(f"Output directory: {output_dir.resolve()}")


    results = {}
    for key in stores_to_scrape:
        config = DISPENSARIES[key]
        results[key] = scrape_dispensary(key, config, output_dir)


    print(f"\n{'='*60}")
    print("  SCRAPING COMPLETE")
    print(f"{'='*60}")
    for key, result in results.items():
        print(f"  {result['dispensary']}: {result['total_products']} products")


    print(f"\nOutput files saved to: {output_dir.resolve()}")




if __name__ == "__main__":
    main()
