import sys
import json
import easyocr
import cv2
from PIL import Image

from app.ocr.pipeline import run_paddle_ocr
from app.ocr.classifier import classify_fields
from app.rules.engine import run_rule_engine

def run_test(img_path):
    # Check original image size
    img = Image.open(img_path)
    print(f"Original image resolution: {img.size[0]}x{img.size[1]}")
    
    # Run EasyOCR
    reader = easyocr.Reader(['en'])
    # See if we can tweak easyocr's parameters to find the handwritten price
    # e.g., mag_ratio=2, text_threshold=0.5, link_threshold=0.4
    print("\nRunning EasyOCR with default pipeline...")
    regions = run_paddle_ocr(img_path)
    
    print("\n--- Raw OCR Extraction ---")
    for r in regions:
        print(f"Text: '{r['text']}' | Confidence: {r['confidence']:.2f} | BBox: {r['bbox']}")
        
    print("\n--- Classifier and Verdict ---")
    classified = classify_fields(regions)
    
    verdicts = run_rule_engine(classified, regions, image_path=img_path)
    print("Classified Fields:", json.dumps(classified, indent=2))
    print("Final Verdicts:", json.dumps(verdicts, indent=2))
    
    # Try with custom params
    print("\nRunning EasyOCR with increased mag_ratio (2)...")
    result = reader.readtext(img_path, mag_ratio=2, text_threshold=0.4)
    print("\n--- Raw OCR Extraction (mag_ratio=2) ---")
    for r in result:
        print(f"Text: '{r[1]}' | Confidence: {r[2]:.2f}")

if __name__ == "__main__":
    run_test(sys.argv[1])
