import cv2
import pytesseract
import sys

image_path = r'..\storage\d30aa4ec-602f-482a-98ba-f610078ea068.jpeg_preprocessed.jpg'
img = cv2.imread(image_path)

if img is not None:
    # Soya chips MRP bbox approx [18, 550] to [1500, 750] (capturing the whole line)
    cropped = img[540:760, 10:1500]
    
    cv2.imwrite("soya_crop_debug.jpg", cropped)
    
    try:
        text = pytesseract.image_to_string(cropped)
        print("Tesseract extracted:", repr(text))
    except Exception as e:
        print("Tesseract Error:", e)
else:
    print("Could not load image")
