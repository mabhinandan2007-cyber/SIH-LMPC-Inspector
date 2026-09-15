import re

doctr_text = "50-00, 0.83/ml"
doctr_bad_numbers = set()

for m in re.finditer(r'\b(\d+(?:[\.\-]\d+)?)\s*(?:/|per\s*)?(g|kg|ml|l|mg|gms|grams|litres?|liters?|m)\b', doctr_text.lower()):
    doctr_bad_numbers.add(m.group(1).replace('-', '.'))

print("Bad numbers:", doctr_bad_numbers)
