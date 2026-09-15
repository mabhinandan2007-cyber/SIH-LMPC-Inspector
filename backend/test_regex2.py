# -*- coding: utf-8 -*-
import re
texts = ["MRP RS:", "& MRP E;", "M.R.P.", "mrp"]

mrp_label_pattern = re.compile(r'\b(?:m\.?r\.?p\b\.?|maximum\s+retail\s+price\b)', re.IGNORECASE)

for t in texts:
    print(f"'{t}':")
    print("  pat:", bool(mrp_label_pattern.search(t)))