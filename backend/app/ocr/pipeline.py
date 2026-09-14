import cv2
import json
import easyocr
import re
import numpy as np
import os
from doctr.io import DocumentFile
from doctr.models import ocr_predictor

# Initialize EasyOCR
ocr_engine = easyocr.Reader(['en'])

# Initialize docTR
doctr_model = ocr_predictor(pretrained=True)

def preprocess_image_for_ocr(image_path: str, temp_path: str):
    img = cv2.imread(image_path)
    if img is None:
        return image_path
        
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    enhanced = clahe.apply(gray)
    cv2.imwrite(temp_path, enhanced)
    return temp_path

def run_paddle_ocr(image_path: str):
    # This is actually EasyOCR as primary
    preprocessed_path = image_path + "_preprocessed.jpg"
    preprocess_image_for_ocr(image_path, preprocessed_path)
    
    result = ocr_engine.readtext(preprocessed_path)
    
    extracted_regions = []
    if result:
        for line in result:
            bbox = line[0]
            text = line[1]
            confidence = line[2]
            
            bbox = [[int(pt[0]), int(pt[1])] for pt in bbox]
            
            extracted_regions.append({
                "bbox": bbox,
                "text": str(text),
                "confidence": float(confidence),
                "engine": "easyocr"
            })
            
    return extracted_regions

def verify_price_with_doctr(image_path: str, bbox: list):
    """
    Crops the image to the specified bbox and runs docTR on it.
    Returns the extracted text and confidence.
    """
    preprocessed_path = image_path + "_preprocessed.jpg"
    if os.path.exists(preprocessed_path):
        img = cv2.imread(preprocessed_path)
    else:
        img = cv2.imread(image_path)
        
    if img is None:
        return None, 0.0
        
    x_coords = [p[0] for p in bbox]
    y_coords = [p[1] for p in bbox]
    
    x_min, x_max = max(0, min(x_coords)), min(img.shape[1], max(x_coords))
    y_min, y_max = max(0, min(y_coords)), min(img.shape[0], max(y_coords))
    
    pad = 5
    y_min = max(0, y_min - pad)
    y_max = min(img.shape[0], y_max + pad)
    x_min = max(0, x_min - pad)
    x_max = min(img.shape[1], x_max + pad)
    
    cropped = img[y_min:y_max, x_min:x_max]
    
    # docTR expects RGB, and DocumentFile.from_images takes path or bytes or np array.
    # But for a numpy array, doctr.io takes (H, W, C) RGB
    cropped_rgb = cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB)
    
    # We pass it as a list to doctr model
    result = doctr_model([cropped_rgb])
    
    texts = []
    for page in result.pages:
        for block in page.blocks:
            for line in block.lines:
                for word in line.words:
                    texts.append(word.value)
                    
    if not texts:
        return None, 0.0
        
    return " ".join(texts), 1.0
