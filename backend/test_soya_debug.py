import json
import re
from app.ocr.pipeline import verify_price_with_doctr

field = {
    "bbox": [[45, 1000], [269, 1000], [269, 1039], [45, 1039]],
    "text": "Net Wt:",
    "confidence": 0.998
}

raw_regions = [
    {"bbox": [[311, 1001], [550, 1001], [550, 1046], [311, 1046]], "text": "100 gms", "confidence": 0.88},
    {"bbox": [[53, 917], [249, 917], [249, 957], [53, 957]], "text": "MRP RS:", "confidence": 0.77},
    {"bbox": [[287, 915], [453, 915], [453, 957], [287, 957]], "text": "45.00", "confidence": 0.29},
    {"bbox": [[247, 1068], [669, 1068], [669, 1113], [247, 1113]], "text": "Date: 24.08.2028", "confidence": 0.96},
    {"bbox": [[528, 1135], [797, 1135], [797, 1178], [528, 1178]], "text": "45DAYS", "confidence": 0.45}
]

from app.rules.engine import evaluate_net_quantity_rule

import inspect
lines = inspect.getsource(evaluate_net_quantity_rule)
# patch the function in-memory to print candidates
lines = lines.replace('for cand in candidates:\n            if cand["score"] > best_overall_score', 'print("CANDIDATES:", json.dumps(candidates, default=str))\n        for cand in candidates:\n            if cand["score"] > best_overall_score')

exec(lines)
print(evaluate_net_quantity_rule([field], raw_regions, r"..\storage\dca8d6b4-919d-4978-aa1e-c2bccfcf6905.jpeg"))

