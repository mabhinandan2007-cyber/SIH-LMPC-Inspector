import easyocr
reader = easyocr.Reader(['en'])
res = reader.readtext(r"C:\Users\ASUS\.gemini\antigravity\brain\041690f4-598a-4f7d-8586-b15e6a0249e6\chips_packet_mrp_1789241855335.jpg")
print([r[1] for r in res])
