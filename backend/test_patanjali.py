import json
from app.rules.engine import evaluate_mrp_rule

mrp_fields = [{
    "bbox": [[254, 210], [455, 210], [455, 238], [254, 238]],
    "text": "& MRP E; USP (nch; ol all kaxes)",
    "confidence": 0.127,
    "engine": "easyocr",
    "field_type": "mrp",
    "reason": "explicit-mrp-label"
}]

# Simulate run on patanjali
res = evaluate_mrp_rule(mrp_fields, [], r"..\storage\7621f60c-b4ad-4e56-a45b-c0a14cdc0afd.jpeg")
print(json.dumps(res, indent=2))
