import sys
import json
import easyocr
import cv2
from PIL import Image

from app.ocr.pipeline import verify_price_with_doctr

def run_test(img_path):
    img = cv2.imread(img_path)
    
    # Patanjali fallback
    if "7621f60c" in img_path:
        bbox = [[254, 210], [455, 210], [455, 238], [254, 238]]
    # Soya Chips fallback
    elif "a98823cf" in img_path:
        bbox = [[18, 560], [184, 560], [184, 680], [18, 680]]
    else:
        return
        
    print(f"Original EasyOCR Bbox: {bbox}")
    texts, bboxes = verify_price_with_doctr(img_path, bbox)
    if bboxes:
        print(f"Crop coords used: {bboxes[0]['crop_coords']}")
        print(f"Texts found: {texts}")
        for b in bboxes:
            print(f"  {b['text']} (conf: {b['confidence']:.2f}) -> {b['bbox']}")
    else:
        print("Nothing extracted by docTR.")

run_test(r"..\storage\7621f60c-b4ad-4e56-a45b-c0a14cdc0afd.jpeg")
print("---")
run_test(r"..\storage\a98823cf-c1b8-4184-8e98-bf2e63d95b0a.jpeg")
