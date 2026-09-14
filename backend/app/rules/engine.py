import re
from app.ocr.pipeline import verify_price_with_doctr

def evaluate_field_rule(
    field_type,
    rule_clause,
    fields,
    raw_regions,
    image_path,
    value_pattern,
    secondary_pattern,
    value_extraction_fn,
    min_keyword_confidence=0.3,
    min_value_confidence=0.7,
    require_dual_engine=True
):
    if not fields:
        return {
            "status": "uncertain",
            "rule_clause": rule_clause,
            "detail": f"No {field_type} keywords found on the label. Manual review required."
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
                reg_y1 = region["bbox"][0][1]
                reg_y2 = region["bbox"][2][1]
                reg_cy = (reg_y1 + reg_y2) / 2
                
                if abs(field_cy - reg_cy) <= line_height * 1.0:
                    same_line_regions.append(region)
                    
        same_line_regions.sort(key=lambda r: r["bbox"][0][0])
        
        has_confident_number = False
        has_secondary = False if secondary_pattern else True
        combined_text = []
        
        for reg in same_line_regions:
            text = reg["text"]
            text_lower = text.lower()
            conf = reg.get("confidence", 1.0)
            combined_text.append(text)
            
            if value_pattern.search(text_lower):
                if require_dual_engine and image_path:
                    doctr_text, _ = verify_price_with_doctr(image_path, reg["bbox"])
                    if doctr_text is None:
                        verification_failed_reason = f"docTR failed to extract text from {field_type} region."
                    else:
                        easy_val = value_extraction_fn(text)
                        doctr_val = value_extraction_fn(doctr_text)
                        
                        if easy_val == doctr_val and easy_val is not None:
                            # Dual-engine agreement overrides individual confidence scores!
                            has_confident_number = True
                            verification_failed_reason = None
                        else:
                            verification_failed_reason = f"OCR engine mismatch on {field_type}. EasyOCR: '{easy_val}', docTR: '{doctr_val}' (from raw: '{text}' / '{doctr_text}')"
                else:
                    easy_val = value_extraction_fn(text)
                    if easy_val is not None:
                        if conf >= min_value_confidence:
                            has_confident_number = True
                        else:
                            verification_failed_reason = f"Numeric confidence {conf} below strict threshold {min_value_confidence}"
                
            if secondary_pattern and secondary_pattern.search(text_lower) and conf >= 0.2:
                has_secondary = True
                
        if has_confident_number and has_secondary:
            best_candidate = {
                "text": " ".join(combined_text)
            }
            break
            
    if best_candidate:
        return {
            "status": "present",
            "rule_clause": rule_clause,
            "detail": f"Valid {field_type} declaration found: '{best_candidate['text']}'"
        }
    
    if verification_failed_reason:
        detail = f"Manual review required: {verification_failed_reason}"
    else:
        detail = f"No valid {field_type} declaration detected - needs manual confirmation."
        
    return {
        "status": "uncertain",
        "rule_clause": rule_clause,
        "detail": detail
    }

def evaluate_mrp_rule(mrp_fields, raw_regions, image_path=None):
    def extract_mrp(s):
        match = re.search(r'(?:\d+\.\d+|\d+|\.\d+)', s)
        return match.group(0) if match else None
        
    return evaluate_field_rule(
        field_type="mrp",
        rule_clause="Rule 6(1)(e)",
        fields=mrp_fields,
        raw_regions=raw_regions,
        image_path=image_path,
        value_pattern=re.compile(r'\d+', re.IGNORECASE),
        secondary_pattern=re.compile(r'(tax|incl)', re.IGNORECASE),
        value_extraction_fn=extract_mrp,
        require_dual_engine=True
    )

def evaluate_net_quantity_rule(netqty_fields, raw_regions, image_path=None):
    def extract_netqty(s):
        # Ignore anything after 'x', '*', 'units', or 'unit'
        s = re.split(r'(?i)(?:x|\*|units?)', s)[0]
        # Look for number followed by optional space and unit
        match = re.search(r'(?i)(\d+(?:\.\d+)?)\s*(g|kg|ml|l|mg|gms|grams|litres?|liters?)\b', s)
        if match:
            # Normalize to avoid mismatch like '450 g' vs '450g'
            return match.group(1) + match.group(2).lower()
        return None
        
    return evaluate_field_rule(
        field_type="net_quantity",
        rule_clause="Rule 6(1)(c)",
        fields=netqty_fields,
        raw_regions=raw_regions,
        image_path=image_path,
        value_pattern=re.compile(r'(?i)\d+(?:\.\d+)?\s*(g|kg|ml|l|mg|gms|grams|litres?|liters?)\b', re.IGNORECASE),
        secondary_pattern=None,
        value_extraction_fn=extract_netqty,
        require_dual_engine=True
    )

def run_rule_engine(classified_fields, raw_regions, image_path=None):
    results = []
    
    mrp_fields = [f for f in classified_fields if f["field_type"] == "mrp"]
    mrp_result = evaluate_mrp_rule(mrp_fields, raw_regions, image_path)
    mrp_result["field_type"] = "mrp"
    results.append(mrp_result)
    
    netqty_fields = [f for f in classified_fields if f["field_type"] == "net_quantity"]
    netqty_result = evaluate_net_quantity_rule(netqty_fields, raw_regions, image_path)
    netqty_result["field_type"] = "net_quantity"
    results.append(netqty_result)
    
    return results
