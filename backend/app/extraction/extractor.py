"""
Declaration Extraction Engine — Extracts statutory declarations from raw OCR regions.

Converts OCR text detections and spatial coordinates into structured DeclarationField
objects (specifically MRP and NET_QUANTITY for Version 1) for downstream processing
by the Legal Metrology Rules Engine.

This module is strictly an extraction layer and does not evaluate legal compliance.
"""

from __future__ import annotations

import re
from typing import Any, Optional

try:
    from app.extraction.schemas import (
        BBox,
        DeclarationExtractionResult,
        DeclarationField,
    )
except ImportError:
    from .schemas import (
        BBox,
        DeclarationExtractionResult,
        DeclarationField,
    )


# ---------------------------------------------------------------------------
# Structured Quantity representation
# ---------------------------------------------------------------------------

class QuantityValue(dict):
    """
    Structured representation of a physical quantity with magnitude and unit.

    Subclasses dict so it serializes naturally as {"value": ..., "unit": ...}
    in Pydantic and JSON outputs, while providing property access (.value, .unit),
    clean string rendering ("100 g"), and equality support against both dicts
    and formatted strings.
    """

    def __init__(self, value: float | int, unit: str):
        super().__init__(value=value, unit=unit)

    @property
    def value(self) -> float | int:
        return self["value"]

    @property
    def unit(self) -> str:
        return self["unit"]

    def __str__(self) -> str:
        return f"{self['value']} {self['unit']}"

    def __repr__(self) -> str:
        return f"QuantityValue(value={self['value']}, unit='{self['unit']}')"

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, str):
            return str(self) == other or str(self) == other.strip()
        return super().__eq__(other)


# ---------------------------------------------------------------------------
# Statutory unit normalisation
# ---------------------------------------------------------------------------

_UNIT_NORMALIZATION: dict[str, str] = {
    "g": "g",
    "gm": "g",
    "gms": "g",
    "gram": "g",
    "grams": "g",
    "kg": "kg",
    "kgs": "kg",
    "kilogram": "kg",
    "kilograms": "kg",
    "mg": "mg",
    "mgs": "mg",
    "milligram": "mg",
    "milligrams": "mg",
    "ml": "ml",
    "mls": "ml",
    "millilitre": "ml",
    "millilitres": "ml",
    "milliliter": "ml",
    "milliliters": "ml",
    "l": "l",
    "ltr": "l",
    "ltrs": "l",
    "litre": "l",
    "litres": "l",
    "liter": "l",
    "liters": "l",
}

_QTY_UNITS_PATTERN = (
    r"(?:gms?|grams?|kgs?|kilograms?|mgs?|milligrams?|mls?|"
    r"millilit(?:re|er)s?|ltrs?|lit(?:re|er)s?|g|l)"
)


# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# Explicit MRP label indicators (word-boundary constrained)
_MRP_LABEL_RE = re.compile(
    r"(?i)\b(?:m\.?\s*r\.?\s*p\b\.?|maximum\s+retail\s+price\b|max\.?\s*retail\s*price\b)"
)

# Combined MRP label + price in a single region
_MRP_SAME_BOX_RE = re.compile(
    r"(?i)(?:m\.?\s*r\.?\s*p\b\.?|maximum\s+retail\s+price\b|max\.?\s*retail\s*price\b)"
    r"[\s:.\-]*"
    r"(?:(?:rs\.?|inr|\u20b9)[\s:.\-]*)?"
    r"(\d+(?:\.\d{1,2})?)"
    r"(?:\s*/-|\b)"
)

# Standalone price candidate (in a nearby separate region)
_STANDALONE_PRICE_RE = re.compile(
    r"(?i)(?:(?:rs\.?|inr|\u20b9)[\s:.\-]*)?(\d+(?:\.\d{1,2})?)(?:\s*/-)?(?:\b|$)"
)

# Net Quantity label indicators
_NET_QTY_LABEL_RE = re.compile(
    r"(?i)\b(?:net\s*(?:wt|weight|qty|quantity|volume|vol|vt))\b"
)

# Combined Net Quantity label + quantity + unit in a single region
_NET_QTY_SAME_BOX_RE = re.compile(
    r"(?i)\b(?:net\s*(?:wt|weight|qty|quantity|volume|vol|vt))"
    r"[\s:.\-]*"
    rf"(\d+(?:\.\d+)?)\s*({_QTY_UNITS_PATTERN})\b"
)

# Standalone quantity candidate (number + recognised physical unit)
_STANDALONE_QTY_RE = re.compile(
    rf"(?i)\b(\d+(?:\.\d+)?)\s*({_QTY_UNITS_PATTERN})\b"
)

# Blacklist / negative filters
_DATE_RE = re.compile(r"\b\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}\b")
_DATE_UNIT_RE = re.compile(
    r"(?i)\b\d+\s*(?:days?|months?|years?|weeks?|hours?|mins?)\b"
)


# ---------------------------------------------------------------------------
# Spatial Geometry & Association
# ---------------------------------------------------------------------------

def _bbox_geometry(bbox: Optional[list[list[int]]]) -> Optional[dict[str, float]]:
    """Extract bounding box extent and center coordinates."""
    if not bbox or len(bbox) < 4:
        return None
    try:
        xs = [pt[0] for pt in bbox]
        ys = [pt[1] for pt in bbox]
        x_min, x_max = min(xs), max(xs)
        y_min, y_max = min(ys), max(ys)
        return {
            "x_min": float(x_min),
            "x_max": float(x_max),
            "y_min": float(y_min),
            "y_max": float(y_max),
            "cx": (x_min + x_max) / 2.0,
            "cy": (y_min + y_max) / 2.0,
            "w": float(max(1, x_max - x_min)),
            "h": float(max(1, y_max - y_min)),
        }
    except Exception:
        return None


def _calculate_spatial_score(
    label_reg: dict,
    label_idx: int,
    cand_reg: dict,
    cand_idx: int,
) -> float:
    """
    Score the spatial proximity and alignment between a label region and a candidate value region.

    Prefers:
    1. Horizontal alignment on the same line to the right of the label.
    2. Vertical alignment directly below the label.
    3. General 2D proximity.
    4. Reading-order sequence index as a fallback when bounding boxes are unavailable.
    """
    l_geo = _bbox_geometry(label_reg.get("bbox"))
    c_geo = _bbox_geometry(cand_reg.get("bbox"))

    if l_geo and c_geo:
        dy = c_geo["cy"] - l_geo["cy"]
        dx = c_geo["cx"] - l_geo["cx"]
        h = l_geo["h"]
        w = l_geo["w"]

        # Horizontal layout: same line (vertical delta <= 1.5 * height), value to right of label
        if abs(dy) <= h * 1.5:
            if c_geo["x_min"] >= l_geo["x_min"] - w * 0.1:
                gap_x = max(0.0, c_geo["x_min"] - l_geo["x_max"])
                if gap_x <= max(h * 15.0, w * 5.0):
                    return 1000.0 - gap_x * 0.5 - abs(dy) * 2.0

        # Vertical layout: value directly below label
        gap_y = c_geo["y_min"] - l_geo["y_max"]
        if -h * 0.2 <= gap_y <= h * 6.0:
            if abs(dx) <= max(w, c_geo["w"]) * 2.0:
                return 800.0 - max(0.0, gap_y) - abs(dx) * 0.5

        # Proximity fallback
        dist = (dx**2 + dy**2) ** 0.5
        if dist <= h * 15.0:
            return 500.0 - dist * 0.5

        return -9999.0
    else:
        # Fallback to reading-order sequence index distance
        idx_diff = cand_idx - label_idx
        if 1 <= idx_diff <= 3:
            return 600.0 - idx_diff * 50.0
        elif -2 <= idx_diff < 0:
            return 200.0 - abs(idx_diff) * 50.0
        return -9999.0


# ---------------------------------------------------------------------------
# Field Extractors
# ---------------------------------------------------------------------------

def _extract_mrp(raw_regions: list[dict]) -> Optional[DeclarationField]:
    """
    Extract Maximum Retail Price (MRP) from OCR regions.

    Supports same-box extraction and spatial association across separate label/value boxes.
    Requires explicit MRP context (e.g. MRP, M.R.P., Maximum Retail Price) to avoid false
    positives from currency symbols or non-price numeric figures.
    """
    candidates: list[dict[str, Any]] = []

    for idx, reg in enumerate(raw_regions):
        text = str(reg.get("text", "") or "").strip()
        conf = max(0.0, min(1.0, float(reg.get("confidence", 1.0))))
        source = reg.get("source") or reg.get("engine")
        bbox = reg.get("bbox")

        # 1. Check same-box match (label + price in the same region)
        if _MRP_LABEL_RE.search(text):
            same_box_match = _MRP_SAME_BOX_RE.search(text)
            if same_box_match and not _DATE_RE.search(text):
                val = float(same_box_match.group(1))
                score = 2000.0 + conf * 100.0
                candidates.append({
                    "score": score,
                    "field": "MRP",
                    "value": val,
                    "raw_text": text,
                    "confidence": conf,
                    "bbox": bbox,
                    "source": source,
                    "extraction_method": "pattern_match",
                })
                continue

            # 2. Separate regions: label in this box, search nearby regions for price value
            best_cand_reg = None
            best_score = 0.0
            best_val = None

            for c_idx, c_reg in enumerate(raw_regions):
                if c_idx == idx:
                    continue
                c_text = str(c_reg.get("text", "") or "").strip()
                if _DATE_RE.search(c_text) or _DATE_UNIT_RE.search(c_text):
                    continue
                if _STANDALONE_QTY_RE.search(c_text):
                    continue

                m = _STANDALONE_PRICE_RE.search(c_text)
                if not m or not m.group(1):
                    continue

                sp_score = _calculate_spatial_score(reg, idx, c_reg, c_idx)
                c_conf = max(0.0, min(1.0, float(c_reg.get("confidence", 1.0))))
                total_sp_score = sp_score + c_conf * 50.0

                if total_sp_score > best_score:
                    best_score = total_sp_score
                    best_cand_reg = c_reg
                    best_val = float(m.group(1))

            if best_cand_reg is not None and best_val is not None:
                c_conf = max(0.0, min(1.0, float(best_cand_reg.get("confidence", 1.0))))
                # Deterministic confidence combination: weakest link represents combined reliability
                comb_conf = round(min(conf, c_conf), 4)
                c_bbox = best_cand_reg.get("bbox")
                c_source = (
                    best_cand_reg.get("source")
                    or best_cand_reg.get("engine")
                    or source
                )
                combined_raw = f"{text} {str(best_cand_reg.get('text', '') or '').strip()}".strip()
                candidates.append({
                    "score": best_score,
                    "field": "MRP",
                    "value": best_val,
                    "raw_text": combined_raw,
                    "confidence": comb_conf,
                    "bbox": c_bbox,
                    "source": c_source,
                    "extraction_method": "spatial_association",
                })

    if not candidates:
        return None

    best = max(candidates, key=lambda c: c["score"])
    return DeclarationField(
        field=best["field"],
        value=best["value"],
        raw_text=best["raw_text"],
        confidence=best["confidence"],
        bbox=best["bbox"],
        source=best["source"],
        extraction_method=best["extraction_method"],
    )


def _extract_net_quantity(raw_regions: list[dict]) -> Optional[DeclarationField]:
    """
    Extract Net Quantity from OCR regions.

    Supports same-box extraction and spatial association across separate label/value boxes.
    Requires a recognised physical unit (g, kg, ml, l, etc.) and normalises unit variations.
    """
    candidates: list[dict[str, Any]] = []

    for idx, reg in enumerate(raw_regions):
        text = str(reg.get("text", "") or "").strip()
        conf = max(0.0, min(1.0, float(reg.get("confidence", 1.0))))
        source = reg.get("source") or reg.get("engine")
        bbox = reg.get("bbox")

        # 1. Check same-box match
        if _NET_QTY_LABEL_RE.search(text):
            same_box_match = _NET_QTY_SAME_BOX_RE.search(text)
            if same_box_match:
                num_str = same_box_match.group(1)
                unit_str = same_box_match.group(2).lower()
                norm_unit = _UNIT_NORMALIZATION.get(unit_str, unit_str)
                val = float(num_str) if "." in num_str else int(num_str)
                score = 2000.0 + conf * 100.0
                candidates.append({
                    "score": score,
                    "field": "NET_QUANTITY",
                    "value": QuantityValue(val, norm_unit),
                    "raw_text": text,
                    "confidence": conf,
                    "bbox": bbox,
                    "source": source,
                    "extraction_method": "quantity_pattern",
                })
                continue

            # 2. Separate regions: label in this box, search nearby regions for quantity value
            best_cand_reg = None
            best_score = 0.0
            best_val = None
            best_unit = None

            for c_idx, c_reg in enumerate(raw_regions):
                if c_idx == idx:
                    continue
                c_text = str(c_reg.get("text", "") or "").strip()
                if _DATE_RE.search(c_text) or _DATE_UNIT_RE.search(c_text):
                    continue

                m = _STANDALONE_QTY_RE.search(c_text)
                if not m:
                    continue

                sp_score = _calculate_spatial_score(reg, idx, c_reg, c_idx)
                c_conf = max(0.0, min(1.0, float(c_reg.get("confidence", 1.0))))
                total_sp_score = sp_score + c_conf * 50.0

                if total_sp_score > best_score:
                    num_str = m.group(1)
                    unit_str = m.group(2).lower()
                    best_score = total_sp_score
                    best_cand_reg = c_reg
                    best_val = float(num_str) if "." in num_str else int(num_str)
                    best_unit = _UNIT_NORMALIZATION.get(unit_str, unit_str)

            if best_cand_reg is not None and best_val is not None and best_unit is not None:
                c_conf = max(0.0, min(1.0, float(best_cand_reg.get("confidence", 1.0))))
                comb_conf = round(min(conf, c_conf), 4)
                c_bbox = best_cand_reg.get("bbox")
                c_source = (
                    best_cand_reg.get("source")
                    or best_cand_reg.get("engine")
                    or source
                )
                combined_raw = f"{text} {str(best_cand_reg.get('text', '') or '').strip()}".strip()
                candidates.append({
                    "score": best_score,
                    "field": "NET_QUANTITY",
                    "value": QuantityValue(best_val, best_unit),
                    "raw_text": combined_raw,
                    "confidence": comb_conf,
                    "bbox": c_bbox,
                    "source": c_source,
                    "extraction_method": "spatial_association",
                })

    if not candidates:
        return None

    best = max(candidates, key=lambda c: c["score"])
    return DeclarationField(
        field=best["field"],
        value=best["value"],
        raw_text=best["raw_text"],
        confidence=best["confidence"],
        bbox=best["bbox"],
        source=best["source"],
        extraction_method=best["extraction_method"],
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_declarations(
    raw_regions: list[dict],
    image_id: Optional[str] = None,
) -> DeclarationExtractionResult:
    """
    Extract statutory declaration fields from raw OCR regions.

    In Version 1, extracts MRP and NET_QUANTITY using pattern matching and spatial association.

    Args:
        raw_regions: List of OCR region dicts (typically with 'text', 'confidence', 'bbox', 'source').
        image_id: Optional identifier for the image or inspection scan.

    Returns:
        DeclarationExtractionResult containing extracted DeclarationField instances.
    """
    declarations: list[DeclarationField] = []

    mrp_field = _extract_mrp(raw_regions)
    if mrp_field is not None:
        declarations.append(mrp_field)

    net_qty_field = _extract_net_quantity(raw_regions)
    if net_qty_field is not None:
        declarations.append(net_qty_field)

    overall_confidence: Optional[float] = None
    if declarations:
        overall_confidence = round(
            sum(d.confidence for d in declarations) / len(declarations), 4
        )

    return DeclarationExtractionResult(
        declarations=declarations,
        image_id=image_id,
        overall_confidence=overall_confidence,
    )
