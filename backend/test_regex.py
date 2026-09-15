# -*- coding: utf-8 -*-
import re
texts = ["cadersis", "Rs. 45", "MRP Rs. 45", "Rs.", "45", "Rs 45", "RS: 45", "MRP RS:"]

mrp_currency_pattern_2 = re.compile(r'\b(?:rs\b\.?|inr\b)', re.IGNORECASE)

for t in texts:
    print(f"'{t}':")
    print("  pat2:", bool(mrp_currency_pattern_2.search(t)))