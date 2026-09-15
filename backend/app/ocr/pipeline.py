"""
OCR Pipeline — Image preprocessing, primary text extraction (EasyOCR),
and secondary verification/crop extraction (docTR).

This module exposes two public functions:

* ``run_ocr_pipeline`` — run EasyOCR on a preprocessed image and return
  a list of detected text regions with bounding boxes.
* ``verify_with_doctr`` — crop a region around a keyword bounding box
  and run docTR for secondary verification, returning word-level results
  with coordinates mapped back to the original image.
"""

import os
from typing import Optional

import cv2
import numpy as np
import easyocr
from doctr.models import ocr_predictor

# ---------------------------------------------------------------------------
# Singleton OCR engine instances (loaded once at import time)
# ---------------------------------------------------------------------------
_easyocr_reader = easyocr.Reader(["en"])
_doctr_model = ocr_predictor(pretrained=True)


# ---------------------------------------------------------------------------
# Type aliases for clarity
# ---------------------------------------------------------------------------
BBox = list[list[int]]  # [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]

Region = dict  # {"bbox": BBox, "text": str, "confidence": float, "engine": str}

DoctrWord = dict  # {"text", "confidence", "bbox", "engine", "crop_coords"}


# ---------------------------------------------------------------------------
# Image preprocessing
# ---------------------------------------------------------------------------
def preprocess_image(image_path: str, output_path: str) -> str:
    """
    Apply CLAHE contrast enhancement to improve OCR accuracy on
    photographed / poorly-lit labels.

    Args:
        image_path: Path to the original image.
        output_path: Path where the enhanced greyscale image is saved.

    Returns:
        ``output_path`` on success, or ``image_path`` unchanged if the
        image could not be loaded.
    """
    img = cv2.imread(image_path)
    if img is None:
        return image_path

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    cv2.imwrite(output_path, enhanced)
    return output_path


# ---------------------------------------------------------------------------
# Primary OCR extraction (EasyOCR)
# ---------------------------------------------------------------------------
def run_ocr_pipeline(image_path: str) -> list[Region]:
    """
    Preprocess the image and run EasyOCR text detection + recognition.

    Args:
        image_path: Path to the uploaded label image.

    Returns:
        A list of ``Region`` dicts, each containing ``bbox``, ``text``,
        ``confidence``, and ``engine`` (always ``"easyocr"``).
    """
    preprocessed_path = image_path + "_preprocessed.jpg"
    preprocess_image(image_path, preprocessed_path)

    raw_results = _easyocr_reader.readtext(preprocessed_path)

    regions: list[Region] = []
    for bbox_raw, text, confidence in (raw_results or []):
        bbox: BBox = [[int(pt[0]), int(pt[1])] for pt in bbox_raw]
        regions.append({
            "bbox": bbox,
            "text": str(text),
            "confidence": float(confidence),
            "engine": "easyocr",
        })

    return regions


# Keep the legacy name as an alias so existing imports don't break
run_paddle_ocr = run_ocr_pipeline


# ---------------------------------------------------------------------------
# Secondary verification via docTR
# ---------------------------------------------------------------------------
def verify_with_doctr(
    image_path: str,
    bbox: BBox,
) -> tuple[Optional[str], list[DoctrWord]]:
    """
    Crop an adaptively-padded region around *bbox*, run docTR on the crop,
    and map the resulting word-level bounding boxes back to absolute
    coordinates on the original image.

    The padding is proportional to the keyword's own width/height so that
    values printed to the right of or below the keyword are captured
    regardless of image resolution.

    Args:
        image_path: Path to the image (uses preprocessed version if available).
        bbox: The bounding box of the keyword to expand around.

    Returns:
        A tuple of ``(joined_text, mapped_word_list)`` where
        ``joined_text`` is the space-joined recognised text (or ``None``
        if nothing was detected) and ``mapped_word_list`` is a list of
        ``DoctrWord`` dicts with absolute-coordinate bounding boxes.
    """
    preprocessed_path = image_path + "_preprocessed.jpg"
    img = cv2.imread(preprocessed_path) if os.path.exists(preprocessed_path) else cv2.imread(image_path)

    if img is None:
        return None, []

    img_h, img_w = img.shape[:2]

    x_coords = [p[0] for p in bbox]
    y_coords = [p[1] for p in bbox]
    bbox_width = max(x_coords) - min(x_coords)
    bbox_height = max(y_coords) - min(y_coords)

    # Adaptive expansion proportional to keyword size
    pad_y_top = int(bbox_height * 2.0)
    pad_y_bottom = int(bbox_height * 6.0)
    pad_left = int(bbox_width * 1.5)
    pad_right = int(bbox_width * 4.0)

    y_min = max(0, min(y_coords) - pad_y_top)
    y_max = min(img_h, max(y_coords) + pad_y_bottom)
    x_min = max(0, min(x_coords) - pad_left)
    x_max = min(img_w, max(x_coords) + pad_right)

    crop_w = x_max - x_min
    crop_h = y_max - y_min
    if crop_w <= 0 or crop_h <= 0:
        return None, []

    cropped_rgb = cv2.cvtColor(img[y_min:y_max, x_min:x_max], cv2.COLOR_BGR2RGB)
    result = _doctr_model([cropped_rgb])

    texts: list[str] = []
    mapped_bboxes: list[DoctrWord] = []

    for page in result.pages:
        for block in page.blocks:
            for line in block.lines:
                for word in line.words:
                    texts.append(word.value)

                    # Map docTR's relative [0..1] geometry back to absolute pixels
                    (r_xmin, r_ymin), (r_xmax, r_ymax) = word.geometry
                    abs_xmin = int(r_xmin * crop_w) + x_min
                    abs_ymin = int(r_ymin * crop_h) + y_min
                    abs_xmax = int(r_xmax * crop_w) + x_min
                    abs_ymax = int(r_ymax * crop_h) + y_min

                    mapped_bboxes.append({
                        "text": word.value,
                        "confidence": word.confidence,
                        "bbox": [
                            [abs_xmin, abs_ymin],
                            [abs_xmax, abs_ymin],
                            [abs_xmax, abs_ymax],
                            [abs_xmin, abs_ymax],
                        ],
                        "engine": "doctr",
                        "crop_coords": [x_min, y_min, x_max, y_max],
                    })

    if not texts:
        return None, []

    return " ".join(texts), mapped_bboxes


# Legacy alias used by engine.py
verify_price_with_doctr = verify_with_doctr
