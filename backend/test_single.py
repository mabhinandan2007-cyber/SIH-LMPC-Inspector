import easyocr
reader = easyocr.Reader(['en'])
res = reader.readtext(r"..\storage\dca8d6b4-919d-4978-aa1e-c2bccfcf6905.jpeg")
for r in res:
    print(r[1])
