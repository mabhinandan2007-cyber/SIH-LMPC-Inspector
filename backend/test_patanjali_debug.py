import json
import re
from app.ocr.pipeline import verify_price_with_doctr

field = {
    "bbox": [[254, 210], [455, 210], [455, 238], [254, 238]],
    "text": "& MRP E; USP (nch; ol all kaxes)",
    "confidence": 0.127,
    "engine": "easyocr",
    "field_type": "mrp",
    "reason": "explicit-mrp-label"
}

fx, fy = (field["bbox"][0][0] + field["bbox"][2][0]) / 2, (field["bbox"][0][1] + field["bbox"][2][1]) / 2
f_height = max(1, field["bbox"][2][1] - field["bbox"][0][1])

print("Height:", f_height)
doctr_text, doctr_bboxes = verify_price_with_doctr(r"..\storage\7621f60c-b4ad-4e56-a45b-c0a14cdc0afd.jpeg", field["bbox"])
print("docTR BBoxes:")
for dbbox in doctr_bboxes:
    rx, ry = (dbbox["bbox"][0][0] + dbbox["bbox"][2][0]) / 2, (dbbox["bbox"][0][1] + dbbox["bbox"][2][1]) / 2
    dx = rx - fx
    dy = ry - fy
    print(dbbox["text"], "dx:", dx, "dy:", dy)
