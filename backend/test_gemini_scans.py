import sqlite3
import json
import os
from app.db.database import SessionLocal
from app.db import models
from app.ocr.pipeline import run_paddle_ocr
from app.ocr.classifier import classify_fields
from app.rules.engine import run_rule_engine

db = SessionLocal()

for scan_id in [15, 24]:
    scan = db.query(models.Scan).filter(models.Scan.id == scan_id).first()
    if not scan:
        print(f"Scan {scan_id} not found")
        continue
        
    print(f"\n{'='*50}\nTesting Scan {scan_id}: {scan.image_path}\n{'='*50}")
    
    if not os.path.exists(scan.image_path):
        print("Image file not found:", scan.image_path)
        continue
        
    raw_regions = run_paddle_ocr(scan.image_path)
    classified = classify_fields(raw_regions)
    
    # Run the rule engine (which now includes Gemini fallback)
    results = run_rule_engine(classified, raw_regions, image_path=scan.image_path)
    
    for r in results:
        print(f"Field: {r['field_type']}")
        print(f"Status: {r['status']}")
        print(f"Detail: {r['detail']}\n")
