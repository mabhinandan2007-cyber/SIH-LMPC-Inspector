from app.rules.engine import evaluate_net_quantity_rule

fields = [{"text": "Net Weight", "confidence": 0.9, "bbox": [[10, 10], [50, 10], [50, 20], [10, 20]], "field_type": "net_quantity"}]
regions = [
    {"text": "Net Weight", "confidence": 0.9, "bbox": [[10, 10], [50, 10], [50, 20], [10, 20]]},
    {"text": "450 g (5 Units x 90 g)", "confidence": 0.95, "bbox": [[55, 10], [150, 10], [150, 20], [55, 20]]}
]

# We pass require_dual_engine=False for this mocked test since we don't have an image path to crop from
result = evaluate_net_quantity_rule(fields, regions, image_path=None)
print(result)
