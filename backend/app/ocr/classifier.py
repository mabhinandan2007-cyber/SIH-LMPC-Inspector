"""
OCR Field Classifier — maps raw OCR text regions to statutory field types.

Uses deterministic regex patterns with word-boundary constraints to
classify detected text as MRP, Net Quantity, or other declaration fields.
Applies confidence modifiers to distinguish explicit labels from weaker
currency-only indicators.
"""

import re
from typing import Any

# ---------------------------------------------------------------------------
# Pre-compiled regex patterns
# ---------------------------------------------------------------------------

# MRP — explicit labels get a confidence boost; standalone currency symbols
# act as a weaker fallback to avoid false positives (e.g. "cadersis" → "rs").
_MRP_LABEL_RE = re.compile(
    r"\b(?:m\.?r\.?p\b\.?|maximum\s+retail\s+price\b|price\b)",
    re.IGNORECASE,
)
_MRP_CURRENCY_RE = re.compile(
    r"\b(?:rs\b\.?|inr\b)",
    re.IGNORECASE,
)

# Net Quantity — includes common OCR mis-readings like "Net Vt" for "Net Wt".
_NETQTY_RE = re.compile(
    r"\b(?:net\s*wt|net\s*qty|net\s*volume|net\s*weight|volume|quantity|net\s*vt)\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def classify_fields(extracted_regions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Iterate over raw OCR regions and tag each one with a ``field_type``
    if it matches a known statutory keyword pattern.

    A single region may produce multiple classified entries (e.g. a box
    containing both "MRP" and "Net Wt" text — rare but possible).

    Args:
        extracted_regions: List of region dicts from ``run_ocr_pipeline``,
            each containing at minimum ``text``, ``bbox``, ``confidence``,
            and ``engine``.

    Returns:
        A list of classified field dicts.  Each entry is a shallow copy
        of the source region with an added ``field_type`` key and,
        for MRP fields, a ``reason`` key.
    """
    classified: list[dict[str, Any]] = []

    for region in extracted_regions:
        text = region["text"]

        # ----- MRP classification -----
        is_mrp = False
        mrp_conf_modifier = 1.0

        if _MRP_LABEL_RE.search(text):
            is_mrp = True
            mrp_conf_modifier = 1.2  # boost explicit labels
        elif _MRP_CURRENCY_RE.search(text):
            is_mrp = True
            mrp_conf_modifier = 0.8  # demote standalone currency hints

        if is_mrp:
            mrp_entry = region.copy()
            mrp_entry["field_type"] = "mrp"
            mrp_entry["confidence"] = min(1.0, mrp_entry.get("confidence", 1.0) * mrp_conf_modifier)
            mrp_entry["reason"] = (
                "explicit-mrp-label" if mrp_conf_modifier >= 1.0 else "currency-pattern-only"
            )
            classified.append(mrp_entry)

        # ----- Net Quantity classification -----
        if _NETQTY_RE.search(text):
            nq_entry = region.copy()
            nq_entry["field_type"] = "net_quantity"
            classified.append(nq_entry)

    return classified
