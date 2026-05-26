import hashlib
from rapidfuzz import fuzz
import os

THRESHOLD = float(os.getenv("PEK_SIMILARITY_THRESHOLD", "0.92")) * 100

def compute_pek(p: dict) -> str:
    """
    Deterministic equivalence key:
    brand + strain + size + category + thc-bucket
    Title variations collapse to the same PEK.
    """
    parts = [
        p.get("norm_brand", ""),
        p.get("norm_strain", ""),
        p.get("norm_size", ""),
        p.get("norm_category", ""),
        f"{round(float(p['norm_thc']))//5*5}" if p.get("norm_thc") else "",
    ]
    key = "|".join(parts).strip("|")
    return hashlib.sha1(key.encode()).hexdigest()

def dedupe_by_pek(products):
    """Merge products with identical PEK or fuzzy-matching titles within same brand+size."""
    buckets = {}
    for p in products:
        k = p["pek_hash"]
        if k in buckets:
            # keep cheaper price, merge prices array
            buckets[k].setdefault("variants", []).append(p)
        else:
            buckets[k] = p

    # second pass: fuzzy titles in same brand+size that didn't share PEK
    out = list(buckets.values())
    merged = []
    while out:
        a = out.pop()
        merges = []
        for b in out[:]:
            if a["norm_brand"] == b["norm_brand"] and a["norm_size"] == b["norm_size"]:
                if fuzz.token_set_ratio(a["norm_title"], b["norm_title"]) >= THRESHOLD:
                    merges.append(b); out.remove(b)
        if merges:
            a.setdefault("variants", []).extend(merges)
        merged.append(a)
    return merged
