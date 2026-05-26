import re
from unidecode import unidecode
from .tokens import STRAIN_ALIASES, UNIT_RE, STOPWORDS

def _clean(s: str) -> str:
    s = unidecode(s or "").lower()
    s = re.sub(r"[^a-z0-9 .%]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def normalize_product(p: dict) -> dict:
    title = _clean(p.get("title", ""))
    brand = _clean(p.get("brand", ""))
    strain = STRAIN_ALIASES.get(_clean(p.get("strain", "")), _clean(p.get("strain", "")))
    size_match = UNIT_RE.search(title + " " + str(p.get("size", "")))
    size = size_match.group(0) if size_match else ""
    category = _clean(p.get("category", ""))
    thc = p.get("thc_pct") or p.get("thc")
    return {
        **p,
        "norm_title": " ".join(t for t in title.split() if t not in STOPWORDS),
        "norm_brand": brand,
        "norm_strain": strain,
        "norm_size": size.replace(" ", ""),
        "norm_category": category,
        "norm_thc": thc,
    }
