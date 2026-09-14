from PIL import Image, ImageDraw, ImageFont
import os
import sys

# Create a clean white image
img = Image.new('RGB', (200, 100), color=(255, 255, 255))
d = ImageDraw.Draw(img)

# Try to use a default windows font or basic text
try:
    font = ImageFont.truetype('arial.ttf', 40)
except:
    font = ImageFont.load_default()

# Draw '45.00'
d.text((30, 20), '45.00', fill=(0, 0, 0), font=font)
img.save('test_digits.png')

import os
os.environ['FLAGS_enable_pir_api'] = '0'

from paddleocr import PaddleOCR
ocr = PaddleOCR(use_angle_cls=False, lang='en', enable_mkldnn=False)
result = ocr.ocr('test_digits.png')
print('=== PADDLEOCR RESULT ===')
print(result)
