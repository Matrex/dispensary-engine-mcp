def get_blaze_products(store_id, origin="https://devilslettuce.net"):
    url_base = "https://ecom-api.blaze.me/api/v1/products/"
    headers = {"Accept": "application/vnd.api+json", "Origin": origin, "X-Store": store_id, "X-App-Mode": "default"}
    all_products = []
    offset, limit = 0, 100
    try:
        while True:
            r = cr.get(url_base, params={"limit": limit, "offset": offset, "delivery_type": "pickup"}, headers=headers, impersonate="chrome124")
            if r.status_code != 200: break
            data = r.json()
            items = data.get('data', [])
            if not items: break
            for item in items:
                attr = item.get('attributes', {})
                all_products.append({
                    "id": item.get('id'), "name": attr.get('name'),
                    "brand": attr.get('brand') or attr.get('brand_name') or "Unknown",
                    "category": attr.get('type') or attr.get('category') or "Unknown",
                    "price": (attr.get('unit_price', {}).get('amount', 0) / 100) if isinstance(attr.get('unit_price'), dict) else 0,
                    "raw_data": item
                })
            offset += len(items)
            if offset >= data.get('meta', {}).get('total_count', 0): break
    except Exception as e: print(f"Blaze Error: {e}")
    return all_products
