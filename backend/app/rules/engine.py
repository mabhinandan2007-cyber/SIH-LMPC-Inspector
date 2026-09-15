"""
LMPC Rule Engine — evaluates classified OCR fields against the Legal
Metrology (Packaged Commodities) Rules, 2011.

Each ``evaluate_*_rule`` function implements a *spatial candidate scoring*
algorithm that:

1. Searches a neighbourhood around the detected keyword label.
2. Collects candidate numeric values from both EasyOCR and docTR.
3. Builds a **bad-numbers blacklist** of dates, phone numbers, batch codes,
   and unit prices extracted from the full-page OCR text.
4. Scores every candidate on spatial proximity, textual features (decimal
   points, currency symbols, unit suffixes), and blacklist membership.
5. Returns the highest-scoring candidate with its bounding boxes preserved.

Public API
----------
* ``run_rule_engine(classified_fields, raw_regions, image_path)``
  — orchestrates all field-specific evaluators and returns a list of
    verdict dicts ready for database storage and frontend display.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from app.ocr.pipeline import verify_price_with_doctr

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------
BBox = list[list[int]]
Verdict = dict[str, Any]


# ═══════════════════════════════════════════════════════════════════════════
# Shared helpers
# ═══════════════════════════════════════════════════════════════════════════

def _bbox_center(bbox: BBox) -> tuple[float, float]:
    """Return the (cx, cy) centre point of a four-corner bounding box."""
    return (bbox[0][0] + bbox[2][0]) / 2, (bbox[0][1] + bbox[2][1]) / 2


def _bbox_height(bbox: BBox) -> int:
    """Return the pixel height of a bounding box (min 1 to avoid division by zero)."""
    return max(1, bbox[2][1] - bbox[0][1])


def _extract_date_numbers(text: str) -> set[str]:
    """
    Find date-like patterns (e.g. ``24.08.2026``, ``12/2024``) and return
    a set of the individual numeric components so they can be blacklisted
    as non-value candidates.
    """
    bad: set[str] = set()
    for m in re.finditer(r"\b\d{2}[/.-]\d{2}[/.-]\d{2,4}\b|\b\d{2}[/.-]\d{4}\b", text):
        for num in re.findall(r"\d+", m.group(0)):
            bad.add(num)
    return bad


def _extract_phone_numbers(text: str) -> set[str]:
    """Return a set of 8–14 digit strings that look like phone / barcode numbers."""
    return {m.group(0) for m in re.finditer(r"\b\d{8,14}\b", text)}


def _extract_unit_prices(text: str) -> set[str]:
    """
    Find unit-price patterns like ``0.83/ml`` and return the numeric
    part for blacklisting.
    """
    bad: set[str] = set()
    for m in re.finditer(
        r"\b(\d+(?:[.\-]\d+)?)\s*(?:/|per\s*)"
        r"(g|kg|ml|l|mg|gms|grams|litres?|liters?|m)\b",
        text.lower(),
    ):
        bad.add(m.group(1).replace("-", "."))
    return bad


def _spatial_score(dx: float, dy: float, f_height: int) -> float:
    """
    Compute a proximity bonus that decays linearly with distance.
    Closer candidates score higher (max 100, min 0).
    """
    dist = (dx ** 2 + dy ** 2) ** 0.5
    return max(0.0, 100.0 - (dist / f_height) * 10.0)


# ═══════════════════════════════════════════════════════════════════════════
# Legacy generic evaluator (kept for potential future use)
# ═══════════════════════════════════════════════════════════════════════════

def evaluate_field_rule(
    field_type: str,
    rule_clause: str,
    fields: list[dict],
    raw_regions: list[dict],
    image_path: Optional[str],
    value_pattern: re.Pattern,
    secondary_pattern: Optional[re.Pattern],
    value_extraction_fn,
    min_keyword_confidence: float = 0.3,
    min_value_confidence: float = 0.7,
    require_dual_engine: bool = True,
) -> Verdict:
    """
    Generic field evaluator that uses rigid same-line matching.

    .. deprecated::
        Superseded by ``evaluate_mrp_rule`` and ``evaluate_net_quantity_rule``
        which use robust spatial candidate scoring.  Retained here for
        backward compatibility with any future field types that have not
        yet been upgraded.
    """
    if not fields:
        return {
            "status": "uncertain",
            "rule_clause": rule_clause,
            "detail": f"No {field_type} keywords found on the label. Manual review required.",
        }

    best_candidate = None
    verification_failed_reason = None

    for field in fields:
        if field.get("confidence", 1.0) < min_keyword_confidence:
            continue

        field_y1 = field["bbox"][0][1]
        field_y2 = field["bbox"][2][1]
        field_cy = (field_y1 + field_y2) / 2
        line_height = field_y2 - field_y1

        same_line_regions = []
        for region in raw_regions:
            if "bbox" in region:
                reg_cy = (region["bbox"][0][1] + region["bbox"][2][1]) / 2
                if abs(field_cy - reg_cy) <= line_height * 1.0:
                    same_line_regions.append(region)

        same_line_regions.sort(key=lambda r: r["bbox"][0][0])

        has_confident_number = False
        has_secondary = secondary_pattern is None
        combined_text: list[str] = []

        for reg in same_line_regions:
            text = reg["text"]
            conf = reg.get("confidence", 1.0)
            combined_text.append(text)

            if value_pattern.search(text.lower()):
                if require_dual_engine and image_path:
                    doctr_text, _ = verify_price_with_doctr(image_path, reg["bbox"])
                    if doctr_text is None:
                        verification_failed_reason = (
                            f"docTR failed to extract text from {field_type} region."
                        )
                    else:
                        easy_val = value_extraction_fn(text)
                        doctr_val = value_extraction_fn(doctr_text)
                        if easy_val == doctr_val and easy_val is not None:
                            has_confident_number = True
                            verification_failed_reason = None
                        else:
                            verification_failed_reason = (
                                f"OCR engine mismatch on {field_type}. "
                                f"EasyOCR: '{easy_val}', docTR: '{doctr_val}' "
                                f"(from raw: '{text}' / '{doctr_text}')"
                            )
                else:
                    easy_val = value_extraction_fn(text)
                    if easy_val is not None:
                        if conf >= min_value_confidence:
                            has_confident_number = True
                        else:
                            verification_failed_reason = (
                                f"Numeric confidence {conf} below threshold {min_value_confidence}"
                            )

            if secondary_pattern and secondary_pattern.search(text.lower()) and conf >= 0.2:
                has_secondary = True

        if has_confident_number and has_secondary:
            best_candidate = {"text": " ".join(combined_text)}
            break

    if best_candidate:
        return {
            "status": "present",
            "rule_clause": rule_clause,
            "detail": f"Valid {field_type} declaration found: '{best_candidate['text']}'",
        }

    detail = (
        f"Manual review required: {verification_failed_reason}"
        if verification_failed_reason
        else f"No valid {field_type} declaration detected - needs manual confirmation."
    )
    return {"status": "uncertain", "rule_clause": rule_clause, "detail": detail}


# ═══════════════════════════════════════════════════════════════════════════
# MRP Rule — Rule 6(1)(e)
# ═══════════════════════════════════════════════════════════════════════════

def evaluate_mrp_rule(
    mrp_fields: list[dict],
    raw_regions: list[dict],
    image_path: Optional[str] = None,
) -> Verdict:
    """
    Evaluate the Maximum Retail Price declaration using spatial candidate
    scoring across both EasyOCR and docTR results.

    The algorithm:

    1. For each detected MRP keyword, defines a rectangular search
       neighbourhood scaled by the keyword's bounding-box height.
    2. Builds a **bad-numbers** blacklist from date, phone, and
       unit-price patterns found in the full OCR text.
    3. Scores each numeric candidate on: decimal precision (+50),
       currency marker (+50), ``/-`` suffix (+30), blacklist membership
       (−1000), and proximity to the keyword.
    4. Selects the highest-scoring candidate and returns both label
       and value bounding boxes.
    """
    if not mrp_fields:
        return {
            "status": "uncertain",
            "rule_clause": "Rule 6(1)(e)",
            "detail": "No mrp keywords found on the label. Manual review required.",
        }

    best_overall_score: float = -9999
    best_overall_candidate: Optional[dict] = None

    for field in mrp_fields:
        if field.get("confidence", 1.0) < 0.1:
            continue

        fx, fy = _bbox_center(field["bbox"])
        f_height = _bbox_height(field["bbox"])

        # Search neighbourhood (in multiples of line height)
        max_dy_down = f_height * 6.0
        max_dy_up = f_height * 2.0
        max_dx = f_height * 10.0

        # ── Build bad-numbers blacklist ──────────────────────────────
        bad_numbers: set[str] = set()

        doctr_bboxes: list[dict] = []
        if image_path:
            doctr_text, doctr_bboxes = verify_price_with_doctr(image_path, field["bbox"])
            if doctr_text:
                bad_numbers |= _extract_date_numbers(doctr_text)
                bad_numbers |= _extract_unit_prices(doctr_text)
                bad_numbers |= _extract_phone_numbers(doctr_text)

        full_easyocr_text = " ".join(r["text"] for r in raw_regions)
        bad_numbers |= _extract_date_numbers(full_easyocr_text)
        bad_numbers |= _extract_unit_prices(full_easyocr_text)
        bad_numbers |= _extract_phone_numbers(full_easyocr_text)

        # ── Candidate scoring function ──────────────────────────────
        def score_mrp_candidate(text: str) -> tuple[float, Optional[str]]:
            matches = list(re.finditer(
                r"(?:rs\.?\s*|inr\s*|₹\s*)?(\d+[.\-]\d+|\d+)(?:/-)?",
                text.lower(),
            ))
            if not matches:
                return -9999, None

            best_val_score = -9999.0
            best_val: Optional[str] = None

            for m in matches:
                val_str = m.group(1).replace("-", ".")
                val_score = 0.0

                if val_str in bad_numbers:
                    val_score -= 1000
                if "." in val_str:
                    val_score += 50
                if any(tok in m.group(0) for tok in ("rs", "₹", "inr")):
                    val_score += 50
                if "/-" in m.group(0):
                    val_score += 30
                if "." not in val_str and len(val_str) > 4:
                    val_score -= 50

                if val_score > best_val_score:
                    best_val_score = val_score
                    best_val = val_str

            return best_val_score, best_val

        # ── Collect candidates from three sources ───────────────────
        candidates: list[dict] = []

        # Source 1: the label box itself
        text_score, val = score_mrp_candidate(field["text"])
        if val:
            candidates.append({
                "source": "easyocr_label_box",
                "text": field["text"],
                "value": val,
                "bbox": field["bbox"],
                "score": text_score + 100,
                "confidence": field.get("confidence", 1.0),
            })

        # Source 2: nearby EasyOCR regions
        for reg in raw_regions:
            if "bbox" not in reg or reg is field:
                continue
            rx, ry = _bbox_center(reg["bbox"])
            dx, dy = rx - fx, ry - fy
            if -max_dy_up <= dy <= max_dy_down and -max_dx <= dx <= max_dx:
                text_score, val = score_mrp_candidate(reg["text"])
                if val:
                    candidates.append({
                        "source": "easyocr_nearby",
                        "text": reg["text"],
                        "value": val,
                        "bbox": reg["bbox"],
                        "score": text_score + _spatial_score(dx, dy, f_height),
                        "confidence": reg.get("confidence", 1.0),
                    })

        # Source 3: nearby docTR word boxes
        if doctr_bboxes and isinstance(doctr_bboxes, list):
            for dbbox in doctr_bboxes:
                rx, ry = _bbox_center(dbbox["bbox"])
                dx, dy = rx - fx, ry - fy
                if -max_dy_up * 1.5 <= dy <= max_dy_down * 1.5 and -max_dx * 1.5 <= dx <= max_dx * 1.5:
                    text_score, val = score_mrp_candidate(dbbox["text"])
                    if val:
                        candidates.append({
                            "source": "doctr_nearby",
                            "text": dbbox["text"],
                            "value": val,
                            "bbox": dbbox["bbox"],
                            "score": text_score + _spatial_score(dx, dy, f_height) + 20,
                            "confidence": dbbox.get("confidence", 1.0),
                        })

        # ── Pick the winner ─────────────────────────────────────────
        for cand in candidates:
            if cand["score"] > best_overall_score:
                best_overall_score = cand["score"]
                best_overall_candidate = cand
                best_overall_candidate["label_bbox"] = field["bbox"]
                best_overall_candidate["reason"] = field.get("reason", "explicit-mrp-label")

    if best_overall_candidate and best_overall_score > -500:
        return {
            "status": "present",
            "rule_clause": "Rule 6(1)(e)",
            "detail": f"Valid mrp declaration found: '{best_overall_candidate['value']}'",
            "field": "MRP",
            "value": float(best_overall_candidate["value"]),
            "raw_text": best_overall_candidate["text"],
            "label_bbox": best_overall_candidate["label_bbox"],
            "value_bbox": best_overall_candidate["bbox"],
            "confidence": best_overall_candidate["confidence"],
            "selection_reason": best_overall_candidate["reason"],
        }

    return {
        "status": "uncertain",
        "rule_clause": "Rule 6(1)(e)",
        "detail": "No valid mrp declaration detected - needs manual confirmation.",
    }


# ═══════════════════════════════════════════════════════════════════════════
# Net Quantity Rule — Rule 6(1)(c)
# ═══════════════════════════════════════════════════════════════════════════

# Canonical unit normalisation map
_UNIT_ALIASES: dict[str, str] = {
    "gm": "g", "gms": "g", "grams": "g",
    "litres": "l", "liters": "l", "litre": "l", "liter": "l",
}


def _evaluate_physical_quantity_rule(
    fields: list[dict],
    raw_regions: list[dict],
    field_id: str,
    semantic_field: str,
    rule_clause: str,
    unit_regex: str,
    unit_aliases: dict[str, str],
    image_path: Optional[str] = None,
) -> Verdict:
    """
    Shared helper to evaluate physical quantities (Net Quantity, Volume)
    using unit-aware spatial candidate scoring.
    """
    if not fields:
        return {
            "status": "uncertain",
            "rule_clause": rule_clause,
            "detail": "No {field_id} keywords found on the label. Manual review required.",
        }

    best_overall_score: float = -9999
    best_overall_candidate: Optional[dict] = None

    for field in fields:
        if field.get("confidence", 1.0) < 0.1:
            continue

        fx, fy = _bbox_center(field["bbox"])
        f_height = _bbox_height(field["bbox"])

        max_dy_down = f_height * 6.0
        max_dy_up = f_height * 2.0
        max_dx = f_height * 10.0

        # ── Build bad-numbers blacklist ──────────────────────────────
        bad_numbers: set[str] = set()

        doctr_bboxes: list[dict] = []
        if image_path:
            doctr_text, doctr_bboxes = verify_price_with_doctr(image_path, field["bbox"])
            if doctr_text:
                bad_numbers |= _extract_date_numbers(doctr_text)
                bad_numbers |= _extract_phone_numbers(doctr_text)
                bad_numbers |= _extract_unit_prices(doctr_text)
                # Blacklist numbers preceded by MRP/currency indicators
                for m in re.finditer(
                    r"\b(?:mrp|rs\.?|inr|₹)\s*[:\-]?\s*(\d+[.\-]\d+|\d+)(?:/-)?",
                    doctr_text.lower(),
                ):
                    bad_numbers.add(m.group(1).replace("-", "."))

        full_easyocr_text = " ".join(r["text"] for r in raw_regions)
        bad_numbers |= _extract_date_numbers(full_easyocr_text)
        bad_numbers |= _extract_phone_numbers(full_easyocr_text)
        bad_numbers |= _extract_unit_prices(full_easyocr_text)
        for m in re.finditer(
            r"\b(?:mrp|rs\.?|inr|₹)\s*[:\-]?\s*(\d+[.\-]\d+|\d+)(?:/-)?",
            full_easyocr_text.lower(),
        ):
            bad_numbers.add(m.group(1).replace("-", "."))

        # ── Unit-aware candidate scoring ────────────────────────────
        def score_qty_candidate(
            text: str,
        ) -> tuple[float, Optional[str], Optional[str], Optional[str]]:
            """
            Return ``(score, value_str, normalised_unit, raw_match)``
            or ``(-9999, None, None, None)`` if no unit-bearing number
            is found.
            """
            matches = list(re.finditer(unit_regex, text.lower()))
            if not matches:
                return -9999, None, None, None

            best_val_score = -9999.0
            best_val: Optional[str] = None
            best_unit: Optional[str] = None
            best_raw: Optional[str] = None

            for m in matches:
                val_str = m.group(1).replace("-", ".")
                unit_str = m.group(2).lower()
                norm_unit = unit_aliases.get(unit_str, unit_str)

                val_score = 100.0  # base score for having a valid unit
                if val_str in bad_numbers:
                    val_score -= 1000

                if val_score > best_val_score:
                    best_val_score = val_score
                    best_val = val_str
                    best_unit = norm_unit
                    best_raw = m.group(0)

            return best_val_score, best_val, best_unit, best_raw

        # ── Collect candidates ──────────────────────────────────────
        candidates: list[dict] = []

        # Source 1: the label box itself (e.g. "Net Wt: 100 gms")
        text_score, val, unit, raw = score_qty_candidate(field["text"])
        if val:
            candidates.append({
                "source": "easyocr_label_box",
                "text": field["text"], "value": val, "unit": unit,
                "raw_text": raw, "bbox": field["bbox"],
                "score": text_score + 100,
                "confidence": field.get("confidence", 1.0),
            })

        # Source 2: nearby EasyOCR regions
        for reg in raw_regions:
            if "bbox" not in reg or reg is field:
                continue
            rx, ry = _bbox_center(reg["bbox"])
            dx, dy = rx - fx, ry - fy
            if -max_dy_up <= dy <= max_dy_down and -max_dx <= dx <= max_dx:
                text_score, val, unit, raw = score_qty_candidate(reg["text"])
                if val:
                    candidates.append({
                        "source": "easyocr_nearby",
                        "text": reg["text"], "value": val, "unit": unit,
                        "raw_text": raw, "bbox": reg["bbox"],
                        "score": text_score + _spatial_score(dx, dy, f_height),
                        "confidence": reg.get("confidence", 1.0),
                    })

        # Source 3: nearby docTR lines (word boxes clustered into lines)
        if doctr_bboxes and isinstance(doctr_bboxes, list):
            doctr_bboxes.sort(key=lambda b: (b["bbox"][0][1], b["bbox"][0][0]))
            doctr_lines: list[list[dict]] = []
            current_line: list[dict] = []
            current_y: Optional[float] = None

            for b in doctr_bboxes:
                cy = (b["bbox"][0][1] + b["bbox"][2][1]) / 2
                if current_y is None or abs(cy - current_y) < f_height * 0.5:
                    current_line.append(b)
                    n = len(current_line)
                    current_y = cy if current_y is None else (current_y * n + cy) / (n + 1)
                else:
                    doctr_lines.append(current_line)
                    current_line = [b]
                    current_y = cy
            if current_line:
                doctr_lines.append(current_line)

            for line in doctr_lines:
                text = " ".join(b["text"] for b in line)
                x_min = min(b["bbox"][0][0] for b in line)
                y_min = min(b["bbox"][0][1] for b in line)
                x_max = max(b["bbox"][2][0] for b in line)
                y_max = max(b["bbox"][2][1] for b in line)
                line_bbox: BBox = [[x_min, y_min], [x_max, y_min], [x_max, y_max], [x_min, y_max]]

                lx, ly = (x_min + x_max) / 2, (y_min + y_max) / 2
                dx, dy = lx - fx, ly - fy

                if -max_dy_up * 1.5 <= dy <= max_dy_down * 1.5 and -max_dx * 1.5 <= dx <= max_dx * 1.5:
                    text_score, val, unit, raw = score_qty_candidate(text)
                    if val:
                        candidates.append({
                            "source": "doctr_nearby_line",
                            "text": text, "value": val, "unit": unit,
                            "raw_text": raw, "bbox": line_bbox,
                            "score": text_score + _spatial_score(dx, dy, f_height) + 20,
                            "confidence": min(b.get("confidence", 1.0) for b in line),
                        })

        # ── Pick the winner ─────────────────────────────────────────
        for cand in candidates:
            if cand["score"] > best_overall_score:
                best_overall_score = cand["score"]
                best_overall_candidate = cand
                best_overall_candidate["label_bbox"] = field["bbox"]

    if best_overall_candidate and best_overall_score > -500:
        return {
            "status": "present",
            "rule_clause": rule_clause,
            "detail": f"Valid {field_id} declaration found: '{best_overall_candidate['raw_text']}'",
            "field": semantic_field,
            "value": float(best_overall_candidate["value"]),
            "unit": best_overall_candidate["unit"],
            "normalized_value": float(best_overall_candidate["value"]),
            "normalized_unit": best_overall_candidate["unit"],
            "raw_text": best_overall_candidate["raw_text"],
            "label_bbox": best_overall_candidate["label_bbox"],
            "value_bbox": best_overall_candidate["bbox"],
            "confidence": best_overall_candidate["confidence"],
        }

    return {
        "status": "uncertain",
        "rule_clause": rule_clause,
        "detail": f"No valid {field_id} declaration detected - needs manual confirmation.",
    }


# ═══════════════════════════════════════════════════════════════════════════


def evaluate_net_quantity_rule(
    netqty_fields: list[dict],
    raw_regions: list[dict],
    image_path: Optional[str] = None,
) -> Verdict:
    """Evaluate the Net Quantity declaration."""
    unit_regex = r"(?i)\b(\d+(?:[.\-]\d+)?)\s*(g|gm|gms|grams|kg|mg|ml|l|litres?|liters?)\b"
    return _evaluate_physical_quantity_rule(
        fields=netqty_fields,
        raw_regions=raw_regions,
        field_id="net_quantity",
        semantic_field="NET_QUANTITY",
        rule_clause="Rule 6(1)(c)",
        unit_regex=unit_regex,
        unit_aliases=_UNIT_ALIASES,
        image_path=image_path
    )

def evaluate_volume_rule(
    volume_fields: list[dict],
    raw_regions: list[dict],
    image_path: Optional[str] = None,
) -> Verdict:
    """Evaluate the Volume declaration."""
    unit_regex = r"(?i)\b(\d+(?:[.\-]\d+)?)\s*(ml|mi|l|litres?|liters?)\b"
    return _evaluate_physical_quantity_rule(
        fields=volume_fields,
        raw_regions=raw_regions,
        field_id="volume",
        semantic_field="VOLUME",
        rule_clause="Rule 6(1)(c)",
        unit_regex=unit_regex,
        unit_aliases={"litres": "l", "liters": "l", "litre": "l", "liter": "l", "mi": "ml"},
        image_path=image_path
    )


# Orchestrator
# ═══════════════════════════════════════════════════════════════════════════

def run_rule_engine(
    classified_fields: list[dict],
    raw_regions: list[dict],
    image_path: Optional[str] = None,
) -> list[Verdict]:
    """
    Run all field-specific rule evaluators and return a list of verdict
    dicts suitable for database persistence.

    Each verdict contains at minimum ``status``, ``rule_clause``,
    ``detail``, and ``field_type``.
    """
    results: list[Verdict] = []

    mrp_fields = [f for f in classified_fields if f["field_type"] == "mrp"]
    mrp_result = evaluate_mrp_rule(mrp_fields, raw_regions, image_path)
    mrp_result["field_type"] = "mrp"
    results.append(mrp_result)

    netqty_fields = [f for f in classified_fields if f["field_type"] == "net_quantity"]
    netqty_result = evaluate_net_quantity_rule(netqty_fields, raw_regions, image_path)
    netqty_result["field_type"] = "net_quantity"
    results.append(netqty_result)

    volume_fields = [f for f in classified_fields if f["field_type"] == "volume"]
    volume_result = evaluate_volume_rule(volume_fields, raw_regions, image_path)
    volume_result["field_type"] = "volume"
    results.append(volume_result)

    return results
