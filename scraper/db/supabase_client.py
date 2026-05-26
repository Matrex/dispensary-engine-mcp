import os
from supabase import create_client

_sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])

def upsert_products(products):
    if not products:
        return {"upserted": 0}
    payload = [{
        "pek_hash": p["pek_hash"],
        "dispensary_id": p["dispensary_id"],
        "source": p["source"],
        "title": p.get("title"),
        "brand": p.get("norm_brand"),
        "strain": p.get("norm_strain"),
        "category": p.get("norm_category"),
        "size": p.get("norm_size"),
        "thc_pct": p.get("norm_thc"),
        "price": p.get("price"),
        "url": p.get("url"),
        "raw": p,
    } for p in products]
    res = _sb.table("menu_products").upsert(
        payload, on_conflict="dispensary_id,pek_hash"
    ).execute()
    return {"upserted": len(res.data or [])}
