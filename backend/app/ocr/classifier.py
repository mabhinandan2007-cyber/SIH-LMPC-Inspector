import re

def classify_fields(extracted_regions):
    classified_fields = []
    
    mrp_keyword_pattern = re.compile(r'(m\.?r\.?p\.?|rs\.?|,1|price)', re.IGNORECASE)
    netqty_keyword_pattern = re.compile(r'(net\s*wt|net\s*qty|net\s*volume|net\s*weight|volume|quantity)', re.IGNORECASE)
    
    for region in extracted_regions:
        text = region["text"]
        
        if mrp_keyword_pattern.search(text):
            # Duplicate the region if it matches both? Or just add it.
            # Easiest is to copy it
            mrp_reg = region.copy()
            mrp_reg["field_type"] = "mrp"
            classified_fields.append(mrp_reg)
            
        if netqty_keyword_pattern.search(text):
            nq_reg = region.copy()
            nq_reg["field_type"] = "net_quantity"
            classified_fields.append(nq_reg)
            
    return classified_fields
