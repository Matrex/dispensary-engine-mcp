import re

# ---------------------------------------------------------------------------
# Strain aliases  — canonical name : list of known alternate spellings
# ---------------------------------------------------------------------------
STRAIN_ALIASES: dict[str, str] = {
    "og kush":           "og kush",
    "og":                "og kush",
    "blue dream":        "blue dream",
    "bluedream":         "blue dream",
    "girl scout cookies": "girl scout cookies",
    "gsc":               "girl scout cookies",
    "gorilla glue":      "gorilla glue",
    "gg4":               "gorilla glue",
    "gorilla glue 4":    "gorilla glue",
    "wedding cake":      "wedding cake",
    "pink cookies":      "wedding cake",
    "gelato":            "gelato",
    "gelato 33":         "gelato",
    "sour diesel":       "sour diesel",
    "sour d":            "sour diesel",
    "white widow":       "white widow",
    "jack herer":        "jack herer",
    "pineapple express": "pineapple express",
    "purple haze":       "purple haze",
    "trainwreck":        "trainwreck",
    "ak47":              "ak-47",
    "ak 47":             "ak-47",
    "northern lights":   "northern lights",
    "nl":                "northern lights",
    "zkittlez":          "zkittlez",
    "zkittles":          "zkittlez",
    "skittlez":          "zkittlez",
    "runtz":             "runtz",
    "do si dos":         "do-si-dos",
    "dosidos":           "do-si-dos",
    "modified grapes":   "modified grapes",
    "mac":               "miracle alien cookies",
    "miracle alien cookies": "miracle alien cookies",
}

# ---------------------------------------------------------------------------
# Unit regex — matches weight / volume tokens in product titles
# e.g. "3.5g", "1oz", "500mg", "1g", "2pk", "10ct"
# ---------------------------------------------------------------------------
UNIT_RE = re.compile(
    r"\b(\d+(?:\.\d+)?\s*(?:mg|g|oz|ml|lb|pk|ct|pack|count|piece|pieces|gram|grams|ounce|ounces))\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Stopwords — noise words stripped from norm_title before PEK / fuzzy compare
# ---------------------------------------------------------------------------
STOPWORDS: frozenset[str] = frozenset({
    # articles / conjunctions
    "a", "an", "the", "and", "or", "of", "with", "by", "for", "in", "at", "to",
    # cannabis filler words
    "cannabis", "marijuana", "hemp", "flower", "strain", "product", "item",
    "infused", "premium", "craft", "small", "batch", "reserve", "select",
    "co", "co.", "inc", "llc", "brand", "brands",
    # misc noise
    "new", "sale", "special", "deal", "limited", "edition",
})
