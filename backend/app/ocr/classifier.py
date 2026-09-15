"""
OCR Field Classifier — maps raw OCR text regions to statutory field types.

Uses robust fuzzy-matching and contextual evidence to normalize OCR variations
and classify them into canonical declaration fields, while strictly guarding
against false positives (like random substrings matching 'rs' or 'mrp').
"""

import re
from typing import Any, Optional
from rapidfuzz import fuzz

# Canonical aliases dictionary
# Extensible configuration of fields and their common representations
FIELD_ALIASES = {
    "mrp": ["mrp", "m.r.p", "maximum retail price"],
    "net_quantity": ["net quantity", "net qty", "net wt", "net weight", "net vt"],
    "volume": ["volume", "vol"],
    "manufacturer": ["manufacturer", "mfg by", "manufactured by"],
    "packer": ["packer", "pkd by", "packed by"],
    "importer": ["importer", "imported by"],
    "pack_date": ["packed date", "pkd date", "pack date"],
    "mfg_date": ["mfg date", "manufacturing date", "pkd"],
    "best_before": ["best before", "use by", "expiry"],
    "consumer_care": ["consumer care", "customer care"]
}

# Currency indicators for context checking (used to boost weak MRP matches)
_CURRENCY_RE = re.compile(r"\b(?:rs\.?|inr|₹)\b", re.IGNORECASE)
_DIGIT_RE = re.compile(r"\d")


def _clean_text(text: str) -> str:
    """Normalize text by keeping only alphanumerics and spaces, converting to lowercase."""
    return re.sub(r"[^a-z0-9\s]", "", text.lower()).strip()


def _get_ngrams(text: str, max_n: int = 4) -> list[str]:
    """Generate up to max_n word n-grams from cleaned text to allow partial matching."""
    words = text.split()
    ngrams = []
    for n in range(1, min(max_n, len(words)) + 1):
        for i in range(len(words) - n + 1):
            ngrams.append(" ".join(words[i:i + n]))
    return ngrams


def fuzzy_match_fields(text: str) -> list[dict[str, Any]]:
    """
    Evaluates OCR text against canonical aliases using N-gram fuzzy matching.
    
    Returns a list of dicts for each field matched:
    {
        "field": str,
        "matched_text": str,
        "canonical_text": str,
        "similarity": float,
        "confidence_modifier": float,
        "reason": str
    }
    """
    has_currency = bool(_CURRENCY_RE.search(text))
    has_digit = bool(_DIGIT_RE.search(text))
    
    ct = _clean_text(text)
    if not ct:
        # If no clean text (e.g. only punctuation), we still might have currency
        if has_currency:
            return [{
                "field": "mrp",
                "matched_text": text,
                "canonical_text": "currency",
                "similarity": 100.0,
                "confidence_modifier": 0.8,
                "reason": "currency-pattern-only"
            }]
        return []
        
    ngrams = _get_ngrams(ct, max_n=4)
    matches = []
    
    for field, aliases in FIELD_ALIASES.items():
        best_sim = 0.0
        best_ng = ""
        best_canonical = ""
        
        for ng in ngrams:
            for alias in aliases:
                score = fuzz.ratio(alias, ng)
                if score > best_sim:
                    best_sim = score
                    best_ng = ng
                    best_canonical = alias
                    
        # Apply field-specific thresholds and context checks
        if field == "mrp":
            # MRP is a short word; high similarity required unless there is context
            if best_sim >= 90.0:
                matches.append({
                    "field": "mrp",
                    "matched_text": best_ng,
                    "canonical_text": best_canonical,
                    "similarity": round(best_sim, 2),
                    "confidence_modifier": 1.2,
                    "reason": "explicit-mrp-label"
                })
            elif best_sim >= 66.0 and len(best_canonical) <= 5:
                # Catch MRY, MAP, HRP etc. ONLY if currency or digits are present
                if has_currency or has_digit:
                    matches.append({
                        "field": "mrp",
                        "matched_text": best_ng,
                        "canonical_text": best_canonical,
                        "similarity": round(best_sim, 2),
                        "confidence_modifier": 1.0,
                        "reason": "fuzzy-mrp+context"
                    })
            
            # Standalone currency as fallback (Step 3 protection)
            if has_currency:
                matches.append({
                    "field": "mrp",
                    "matched_text": text,
                    "canonical_text": "currency",
                    "similarity": 100.0,
                    "confidence_modifier": 0.8,
                    "reason": "currency-pattern-only"
                })
                
        else:
            # General fields require at least 75% similarity
            if best_sim >= 75.0:
                matches.append({
                    "field": field,
                    "matched_text": best_ng,
                    "canonical_text": best_canonical,
                    "similarity": round(best_sim, 2),
                    "confidence_modifier": 1.0,
                    "reason": f"fuzzy-{field}"
                })
                
    # Deduplicate: pick the strongest match per field
    final_matches = []
    for field in FIELD_ALIASES.keys():
        field_matches = [m for m in matches if m["field"] == field]
        if field_matches:
            best = max(field_matches, key=lambda x: (x["confidence_modifier"], x["similarity"]))
            final_matches.append(best)
            
    return final_matches


def classify_fields(extracted_regions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Iterate over raw OCR regions and tag each one with a ``field_type``
    if it matches a known canonical alias using fuzzy logic.

    A single region may produce multiple classified entries.

    Args:
        extracted_regions: List of region dicts from ``run_ocr_pipeline``.

    Returns:
        A list of classified field dicts. Each entry is a shallow copy
        of the source region with added classification metadata.
    """
    classified: list[dict[str, Any]] = []

    for region in extracted_regions:
        text = region["text"]
        fuzzy_results = fuzzy_match_fields(text)
        
        for result in fuzzy_results:
            entry = region.copy()
            entry["field_type"] = result["field"]
            entry["confidence"] = min(1.0, entry.get("confidence", 1.0) * result["confidence_modifier"])
            entry["reason"] = result["reason"]
            
            # Attach fuzzy matching metadata for tracing
            entry["fuzzy_metadata"] = {
                "matched_text": result["matched_text"],
                "canonical_text": result["canonical_text"],
                "similarity": result["similarity"]
            }
            classified.append(entry)

    return classified
