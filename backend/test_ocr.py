import cv2
import sys
import json
from app.ocr.pipeline import run_paddle_ocr

def test_ocr(image_path):
    print(f"Running PaddleOCR on {image_path}...")
    results = run_paddle_ocr(image_path)
    
    print("\n--- Extracted Text ---")
    for r in results:
        print(f"Text: '{r['text']}' | Confidence: {r['confidence']:.2f}")
    
    print("\n--- Raw JSON Output ---")
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    test_ocr(sys.argv[1])
