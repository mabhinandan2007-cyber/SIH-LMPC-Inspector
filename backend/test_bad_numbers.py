import re

doctr_text = "E 1 EEE masala,veg - oii,sait RAPP nr RS: 45.00 incl ofall taxes . Net Vt: 100 gms Packed - Date: . 24.08.2026 D BEST BEFORE 45DAY"
doctr_bad_numbers = set()

for m in re.finditer(r'\b\d{2}[/.-]\d{2}[/.-]\d{2,4}\b|\b\d{2}[/.-]\d{4}\b', doctr_text):
    for num in re.findall(r'\d+', m.group(0)): doctr_bad_numbers.add(num)
for m in re.finditer(r'\b(\d+(?:[\.\-]\d+)?)\s*(g|kg|ml|l|mg|gms|grams|litres?|liters?)\b', doctr_text.lower()):
    doctr_bad_numbers.add(m.group(1).replace('-', '.'))
for m in re.finditer(r'\b\d{8,14}\b', doctr_text):
    doctr_bad_numbers.add(m.group(0))

print("Bad numbers:", doctr_bad_numbers)
