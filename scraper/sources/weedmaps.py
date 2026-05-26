#How it works:


#Hits the Weedmaps internal API directly: https://api-g.weedmaps.com/discovery/v1/listings/dispensaries/ether/menu_items
#Paginates at 100 items/page — fetches all 7 pages automatically
#Uses curl_cffi with Chrome124 TLS fingerprinting to bypass CDN/Cloudflare blocks (falls back to requests if not installed)
#Usage:


#pip install curl_cffi
#python ether_buffalo_scraper.py                          # → ether_buffalo_inventory.json
#python ether_buffalo_scraper.py --output my_file.json   # custom output
#python ether_buffalo_scraper.py --page-size 50          # adjust page size
#Inventory Summary (as of 2026-04-27)
#Total products: 693
#Top categories: Concentrate (262), Edible (132), Indica (85), Hybrid (63), Preroll (60), Drink (40)
#Top brands: STIIIZY, ayrloom, Jaunty, Florist Farms, EUREKA, Dime Industries, WYLD…
#Per-product fields captured:
#id, name, slug, catalog_slug, category, subcategory, parent_category, genetics, brand_name, brand_slug, product_name_canonical, license_type, is_online_orderable, is_badged, is_endorsed, rating, reviews_count, price, prices (unit/label/price/on_sale), current_deal_title, deal_ids, strains, effects, flavors, avatar_url, created_at, updated_at, test_result_created_at, test_result_expired, external_ids, menu_id, position


!/usr/bin/env python3
"""
Ether Buffalo Dispensary — Weedmaps Menu Scraper
Source : https://etherbuffalo.wm.store/discover
API    : https://api-g.weedmaps.com/discovery/v1/listings/dispensaries/ether/menu_items


Requirements:
    pip install curl_cffi  (Chrome TLS fingerprinting — bypasses Cloudflare/CDN blocks)
    pip install requests   (fallback if curl_cffi is not available)


Usage:
    python ether_buffalo_scraper.py
    python ether_buffalo_scraper.py --output my_inventory.json
    python ether_buffalo_scraper.py --page-size 50
"""


import json
import argparse
import sys
from datetime import datetime, timezone


DISPENSARY_SLUG = "ether"
BASE_API = f"https://api-g.weedmaps.com/discovery/v1/listings/dispensaries/{DISPENSARY_SLUG}/menu_items"
DEFAULT_OUTPUT = "ether_buffalo_inventory.json"
DEFAULT_PAGE_SIZE = 100


HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://etherbuffalo.wm.store",
    "Referer": "https://etherbuffalo.wm.store/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
}




def get_session():
    """Return a requests-compatible session with Chrome TLS fingerprinting if available."""
    try:
        from curl_cffi import requests as cffi_requests
        session = cffi_requests.Session(impersonate="chrome124")
        print("[INFO] Using curl_cffi with Chrome TLS fingerprinting.")
        return session
    except ImportError:
        import requests
        session = requests.Session()
        session.headers.update(HEADERS)
        print("[WARN] curl_cffi not installed — using standard requests. "
              "Install with: pip install curl_cffi")
        return session




def fetch_page(session, page: int, page_size: int) -> dict:
    url = (
        f"{BASE_API}"
        f"?include[]=facets.categories"
        f"&page={page}"
        f"&page_size={page_size}"
    )
    response = session.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return response.json()




def extract_prices(prices_dict) -> list:
    result = []
    if not isinstance(prices_dict, dict):
        return result
    for unit_key, unit_data in prices_dict.items():
        if unit_key == "grams_per_eighth":
            continue
        if isinstance(unit_data, dict):
            result.append({
                "unit": unit_key,
                "label": unit_data.get("label"),
                "price": unit_data.get("price"),
                "original_price": unit_data.get("original_price"),
                "on_sale": unit_data.get("on_sale"),
                "units": unit_data.get("units"),
                "quantity": unit_data.get("quantity"),
            })
    return result




def extract_product(item: dict) -> dict:
    brand = item.get("brand_endorsement") or {}
    if isinstance(brand, str):
        brand = {}
    category = item.get("category") or {}
    edge_cat = item.get("edge_category") or {}
    ancestors = edge_cat.get("ancestors", []) if isinstance(edge_cat, dict) else []
    genetics = item.get("genetics_tag") or {}
    if isinstance(genetics, str):
        genetics = {}
    avatar = item.get("avatar_image") or {}
    ext_ids = item.get("external_ids") or {}
    tags = item.get("tags") or []


    strains = [t.get("name") for t in tags
               if isinstance(t, dict) and
               (t.get("tag_group") or {}).get("name") == "Strains"]
    effects = [t.get("name") for t in tags
               if isinstance(t, dict) and
               (t.get("tag_group") or {}).get("name") == "Effects"]
    flavors = [t.get("name") for t in tags
               if isinstance(t, dict) and
               (t.get("tag_group") or {}).get("name") == "Flavors"]


    return {
        "id": item.get("id"),
        "name": item.get("name"),
        "slug": item.get("slug"),
        "catalog_slug": item.get("catalog_slug"),
        "category": category.get("name") if isinstance(category, dict) else category,
        "category_id": category.get("id") if isinstance(category, dict) else None,
        "category_slug": category.get("slug") if isinstance(category, dict) else None,
        "subcategory": edge_cat.get("name") if isinstance(edge_cat, dict) else None,
        "subcategory_slug": edge_cat.get("slug") if isinstance(edge_cat, dict) else None,
        "parent_category": ancestors[0].get("name") if ancestors else None,
        "genetics": genetics.get("name") if isinstance(genetics, dict) else genetics,
        "brand_name": brand.get("brand_name"),
        "brand_slug": brand.get("brand_slug"),
        "product_name_canonical": brand.get("product_name"),
        "license_type": item.get("license_type"),
        "is_online_orderable": item.get("is_online_orderable"),
        "is_badged": item.get("is_badged"),
        "is_endorsed": item.get("is_endorsed"),
        "rating": item.get("rating"),
        "reviews_count": item.get("reviews_count"),
        "price": item.get("price"),
        "price_stats": item.get("price_stats"),
        "prices": extract_prices(item.get("prices")),
        "current_deal_title": item.get("current_deal_title"),
        "deal_ids": item.get("deal_ids"),
        "strains": strains,
        "effects": effects,
        "flavors": flavors,
        "avatar_url": avatar.get("original_url") if isinstance(avatar, dict) else None,
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
        "test_result_created_at": item.get("test_result_created_at"),
        "test_result_expired": item.get("test_result_expired"),
        "external_ids": ext_ids if isinstance(ext_ids, dict) else {},
        "menu_id": item.get("menu_id"),
        "position": item.get("position"),
    }




def scrape(page_size: int = DEFAULT_PAGE_SIZE) -> list:
    session = get_session()


    print("[INFO] Fetching page 1 to determine total product count ...")
    first_page = fetch_page(session, 1, page_size)
    total = first_page["meta"]["total_menu_items"]
    pages = (total + page_size - 1) // page_size
    print(f"[INFO] Total products: {total}  |  Pages: {pages}  |  Page size: {page_size}")


    all_items = first_page["data"]["menu_items"]
    print(f"[INFO] Page 1/{pages} — {len(all_items)} items")


    for page_num in range(2, pages + 1):
        page_data = fetch_page(session, page_num, page_size)
        items = page_data["data"]["menu_items"]
        all_items.extend(items)
        print(f"[INFO] Page {page_num}/{pages} — {len(items)} items  (running total: {len(all_items)})")


    products = [extract_product(item) for item in all_items]
    print(f"[INFO] Extracted {len(products)} products.")
    return products




def main():
    parser = argparse.ArgumentParser(description="Ether Buffalo Weedmaps inventory scraper")
    parser.add_argument("--output", default=DEFAULT_OUTPUT,
                        help=f"Output JSON file path (default: {DEFAULT_OUTPUT})")
    parser.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE,
                        help=f"Items per API page (default: {DEFAULT_PAGE_SIZE}, max: 100)")
    args = parser.parse_args()


    products = scrape(page_size=args.page_size)


    output = {
        "meta": {
            "dispensary": "Ether Buffalo",
            "dispensary_slug": DISPENSARY_SLUG,
            "source_url": "https://etherbuffalo.wm.store/discover",
            "api_endpoint": BASE_API,
            "total_products": len(products),
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        },
        "products": products,
    }


    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)


    print(f"[SUCCESS] Saved {len(products)} products → {args.output}")




if __name__ == "__main__":
    main()
