import cv2
from doctr.models import ocr_predictor

doctr_model = ocr_predictor(pretrained=True)
image_path = r"..\storage\7621f60c-b4ad-4e56-a45b-c0a14cdc0afd.jpeg"
bbox = [[254, 210], [455, 210], [455, 238], [254, 238]]

def test_crop(image_path, bbox):
    img = cv2.imread(image_path)
    x_coords = [p[0] for p in bbox]
    y_coords = [p[1] for p in bbox]
    
    bbox_width = max(x_coords) - min(x_coords)
    bbox_height = max(y_coords) - min(y_coords)
    
    pad_y_top = int(bbox_height * 2.0)
    pad_y_bottom = int(bbox_height * 6.0) # 6 line heights down
    pad_left = int(bbox_width * 1.5)
    pad_right = int(bbox_width * 4.0)
    
    y_min = max(0, min(y_coords) - pad_y_top)
    y_max = min(img.shape[0], max(y_coords) + pad_y_bottom)
    x_min = max(0, min(x_coords) - pad_left)
    x_max = min(img.shape[1], max(x_coords) + pad_right)
    
    print(f"Crop coords: x_min={x_min}, y_min={y_min}, x_max={x_max}, y_max={y_max}")
    
    cropped = img[y_min:y_max, x_min:x_max]
    cropped_rgb = cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB)
    result = doctr_model([cropped_rgb])
    
    texts = []
    for page in result.pages:
        for block in page.blocks:
            for line in block.lines:
                for word in line.words:
                    texts.append(word.value)
                    
    print("Extracted text:", " ".join(texts))

test_crop(image_path, bbox)
