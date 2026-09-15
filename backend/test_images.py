import os
import easyocr
import cv2

reader = easyocr.Reader(['en'])

def test_dir(directory):
    for f in os.listdir(directory):
        if f.lower().endswith(('.jpg', '.jpeg', '.png')) and not f.endswith('_preprocessed.jpg'):
            path = os.path.join(directory, f)
            print(f"\nScanning: {f}")
            res = reader.readtext(path)
            # just print first few texts to identify the image
            texts = [r[1] for r in res[:10]]
            print(texts)

test_dir(r"..\storage")
