# LMPC Inspector — Complete API & Function Reference

## Table of Contents

1. [API Endpoints (`api/scans.py`)](#api-endpoints)
2. [Database Layer (`db/database.py`)](#database-layer)
3. [ORM Models (`db/models.py`)](#orm-models)
4. [OCR Pipeline (`ocr/pipeline.py`)](#ocr-pipeline)
5. [Field Classifier (`ocr/classifier.py`)](#field-classifier)
6. [Rule Engine (`rules/engine.py`)](#rule-engine)

---

## API Endpoints

**Module**: `backend/app/api/scans.py`

### `POST /api/scans/upload`

**Function**: `upload_scan(file, inspector_id, location, product_id, db)`

Accepts a multipart form upload of a product label image, runs the full OCR → Classification → Rule Engine pipeline, and returns a structured compliance report.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `file` | `UploadFile` | Yes | Image file (JPEG, PNG) of the product label |
| `inspector_id` | `str` (Form) | Yes | ID of the inspector performing the scan |
| `location` | `str` (Form) | Yes | Physical location of the inspection |
| `product_id` | `int` (Form) | No | Optional reference to a known product |
| `db` | `Session` | Auto | Injected database session via `Depends(get_db)` |

**Returns**: `ScanResponse` JSON containing `id`, `status`, `validations[]`.

**Status values**: `passed` | `failed` | `needs_review`

**Side effects**:
- Saves image to `storage/<uuid>.<ext>`
- Creates `Scan`, `FieldExtraction`, `ValidationResult`, and `ReviewQueueItem` records
- Runs EasyOCR and docTR engines

---

### `GET /api/scans/review-queue`

**Function**: `get_review_queue(db)`

Returns all items in the human review queue with their associated scan metadata.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `db` | `Session` | Auto | Injected database session |

**Returns**: List of dicts with `id`, `scan_id`, `reason`, `status`, `created_at`, `inspector_id`.

---

### `GET /api/scans/{scan_id}/report`

**Function**: `generate_report(scan_id, db)`

Generates a PDF compliance report for a completed scan using Jinja2 templating and xhtml2pdf.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `scan_id` | `int` (Path) | Yes | ID of the scan to generate a report for |
| `db` | `Session` | Auto | Injected database session |

**Returns**: `StreamingResponse` with `application/pdf` content type.

**Raises**: `HTTPException(404)` if scan not found, `HTTPException(500)` if PDF generation fails.

---

### Pydantic Models

#### `ValidationResultModel`
```python
class ValidationResultModel(BaseModel):
    field_type: str    # "mrp" | "net_quantity"
    status: str        # "present" | "absent" | "uncertain"
    rule_clause: str   # e.g. "Rule 6(1)(e)"
    detail: str        # Human-readable explanation
```

#### `ScanResponse`
```python
class ScanResponse(BaseModel):
    id: int
    product_id: Optional[int]
    image_path: str
    inspector_id: str
    location: str
    status: str
    created_at: datetime.datetime
    validations: List[ValidationResultModel] = []
```

---

## Database Layer

**Module**: `backend/app/db/database.py`

### `get_db() → Generator[Session, None, None]`

FastAPI dependency that yields a transactional SQLAlchemy session. Rolls back on unhandled exceptions and always closes the session in the `finally` block.

**Usage**:
```python
@router.post("/endpoint")
def my_endpoint(db: Session = Depends(get_db)):
    ...
```

### Module-Level Objects

| Name | Type | Description |
|---|---|---|
| `SQLALCHEMY_DATABASE_URL` | `str` | SQLite connection string with absolute path |
| `engine` | `Engine` | SQLAlchemy engine with `check_same_thread=False` |
| `SessionLocal` | `sessionmaker` | Session factory bound to the engine |
| `Base` | `DeclarativeBase` | Base class for all ORM models |

### SQLite Pragma

An event listener on `engine.connect` executes `PRAGMA foreign_keys=ON` to enable foreign-key constraint enforcement (off by default in SQLite).

---

## ORM Models

**Module**: `backend/app/db/models.py`

### `Product`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | Integer | PK, indexed | Auto-incrementing primary key |
| `name` | String | indexed | Product name |
| `category` | String | indexed | Product category |
| `manufacturer_name` | String | — | Manufacturer name |

**Relationships**: `scans` → one-to-many with `Scan`

### `Scan`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | Integer | PK, indexed | Auto-incrementing primary key |
| `product_id` | Integer | FK(products.id), nullable, indexed | Optional product reference |
| `image_path` | String | — | Disk path to uploaded image |
| `inspector_id` | String | indexed | Inspector identifier |
| `location` | String | — | Inspection location |
| `status` | String | default="pending" | pending\|processing\|passed\|failed\|needs_review |
| `created_at` | DateTime | default=utcnow | Timezone-aware UTC timestamp |

**Relationships**: `product`, `field_extractions` (cascade), `validation_results` (cascade), `review_items` (cascade)

### `FieldExtraction`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | Integer | PK, indexed | Auto-incrementing primary key |
| `scan_id` | Integer | FK(scans.id), indexed | Parent scan reference |
| `field_type` | String | — | mrp \| net_quantity \| manufacturer \| ... |
| `bbox` | String | — | JSON-serialised bounding box |
| `ocr_text` | String | — | Raw OCR text |
| `confidence` | Float | — | OCR confidence score [0.0–1.0] |
| `engine_used` | String | — | easyocr \| doctr \| paddleocr |

### `ValidationResult`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | Integer | PK, indexed | Auto-incrementing primary key |
| `scan_id` | Integer | FK(scans.id), indexed | Parent scan reference |
| `field_type` | String | — | Field that was evaluated |
| `status` | String | — | present \| absent \| uncertain |
| `rule_clause` | String | — | LMPC rule reference (e.g. "Rule 6(1)(e)") |
| `detail` | String | — | Human-readable explanation |

### `RuleVersion`
Versioned snapshot of LMPC rule definitions (currently unpopulated).

### `ReviewQueueItem`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | Integer | PK, indexed | Auto-incrementing primary key |
| `scan_id` | Integer | FK(scans.id), indexed | Parent scan reference |
| `reason` | String | — | Why this scan needs review |
| `assigned_to` | String | nullable | Human reviewer assigned |
| `resolved` | Boolean | default=False | Whether review is complete |

---

## OCR Pipeline

**Module**: `backend/app/ocr/pipeline.py`

### `preprocess_image(image_path, output_path) → str`

Applies CLAHE (Contrast Limited Adaptive Histogram Equalisation) to improve OCR accuracy on photographed labels.

| Parameter | Type | Description |
|---|---|---|
| `image_path` | `str` | Path to the original image |
| `output_path` | `str` | Path to save the enhanced greyscale image |

**Returns**: `output_path` on success, `image_path` if the image could not be loaded.

---

### `run_ocr_pipeline(image_path) → list[Region]`

Preprocesses the image and runs EasyOCR text detection + recognition.

| Parameter | Type | Description |
|---|---|---|
| `image_path` | `str` | Path to the uploaded label image |

**Returns**: List of `Region` dicts:
```python
{
    "bbox": [[x1,y1], [x2,y2], [x3,y3], [x4,y4]],
    "text": "MRP RS:",
    "confidence": 0.77,
    "engine": "easyocr"
}
```

**Legacy alias**: `run_paddle_ocr = run_ocr_pipeline`

---

### `verify_with_doctr(image_path, bbox) → tuple[str | None, list[DoctrWord]]`

Crops an adaptively-padded region around the given bounding box, runs docTR OCR, and maps word-level results back to absolute coordinates on the original image.

| Parameter | Type | Description |
|---|---|---|
| `image_path` | `str` | Path to the image |
| `bbox` | `BBox` | Four-corner bounding box of the keyword |

**Adaptive padding** (proportional to keyword size):
- Top: `2.0 × height`
- Bottom: `6.0 × height`
- Left: `1.5 × width`
- Right: `4.0 × width`

**Returns**: Tuple of `(joined_text, word_list)` where each word contains:
```python
{
    "text": "45.00",
    "confidence": 0.999,
    "bbox": [[295, 921], [448, 921], [448, 950], [295, 950]],
    "engine": "doctr",
    "crop_coords": [x_min, y_min, x_max, y_max]
}
```

**Legacy alias**: `verify_price_with_doctr = verify_with_doctr`

---

## Field Classifier

**Module**: `backend/app/ocr/classifier.py`

### `classify_fields(extracted_regions) → list[dict]`

Iterates over raw OCR regions and tags each one with a `field_type` if it matches a known statutory keyword pattern.

| Parameter | Type | Description |
|---|---|---|
| `extracted_regions` | `list[dict]` | Regions from `run_ocr_pipeline` |

**Returns**: List of classified field dicts, each with an added `field_type` key.

**Classification rules**:

| Field Type | Pattern | Confidence Modifier |
|---|---|---|
| `mrp` (explicit) | `\b(m\.?r\.?p\b\|maximum retail price\|price)\b` | ×1.2 |
| `mrp` (currency) | `\b(rs\b\|inr\b)` | ×0.8 |
| `net_quantity` | `\b(net wt\|net qty\|net volume\|net weight\|volume\|quantity\|net vt)\b` | ×1.0 |

---

## Rule Engine

**Module**: `backend/app/rules/engine.py`

### Shared Helper Functions

#### `_bbox_center(bbox) → tuple[float, float]`
Returns the `(cx, cy)` centre point of a four-corner bounding box.

#### `_bbox_height(bbox) → int`
Returns the pixel height of a bounding box (minimum 1).

#### `_extract_date_numbers(text) → set[str]`
Finds date patterns (`24.08.2026`, `12/2024`) and returns individual numeric components for blacklisting.

#### `_extract_phone_numbers(text) → set[str]`
Returns 8–14 digit strings that look like phone or barcode numbers.

#### `_extract_unit_prices(text) → set[str]`
Finds unit-price patterns like `0.83/ml` and returns the numeric part.

#### `_spatial_score(dx, dy, f_height) → float`
Computes a proximity bonus that decays linearly with distance (max 100, min 0).

---

### `evaluate_mrp_rule(mrp_fields, raw_regions, image_path) → Verdict`

Evaluates the Maximum Retail Price declaration using spatial candidate scoring.

| Parameter | Type | Description |
|---|---|---|
| `mrp_fields` | `list[dict]` | Classified MRP keyword regions |
| `raw_regions` | `list[dict]` | All raw OCR regions |
| `image_path` | `str \| None` | Path to image for docTR verification |

**Scoring bonuses**:
| Feature | Score |
|---|---|
| Decimal point in value | +50 |
| Currency marker (Rs/₹/INR) | +50 |
| `/-` suffix | +30 |
| In label box itself | +100 |
| docTR source bonus | +20 |
| Proximity (max) | +100 |

**Scoring penalties**:
| Feature | Score |
|---|---|
| Value in bad-numbers blacklist | −1000 |
| 5+ digit integer without decimal | −50 |

**Returns**: Verdict dict with `status`, `value`, `label_bbox`, `value_bbox`, `confidence`.

---

### `evaluate_net_quantity_rule(netqty_fields, raw_regions, image_path) → Verdict`

Evaluates the Net Quantity declaration using unit-aware spatial candidate scoring.

| Parameter | Type | Description |
|---|---|---|
| `netqty_fields` | `list[dict]` | Classified Net Quantity keyword regions |
| `raw_regions` | `list[dict]` | All raw OCR regions |
| `image_path` | `str \| None` | Path to image for docTR verification |

**Unit normalisation**:
| Input | Normalised |
|---|---|
| `gm`, `gms`, `grams` | `g` |
| `litres`, `liters`, `litre`, `liter` | `l` |
| `kg`, `mg`, `ml` | unchanged |

**Returns**: Verdict dict with `status`, `value`, `unit`, `raw_text`, `label_bbox`, `value_bbox`.

---

### `run_rule_engine(classified_fields, raw_regions, image_path) → list[Verdict]`

Orchestrates all field-specific rule evaluators.

| Parameter | Type | Description |
|---|---|---|
| `classified_fields` | `list[dict]` | Output from `classify_fields()` |
| `raw_regions` | `list[dict]` | All raw OCR regions |
| `image_path` | `str \| None` | Path to image for docTR verification |

**Returns**: List of verdict dicts, each with an added `field_type` key. Currently evaluates:
1. MRP → `evaluate_mrp_rule()` — Rule 6(1)(e)
2. Net Quantity → `evaluate_net_quantity_rule()` — Rule 6(1)(c)

---

### `evaluate_field_rule(...)` *(Deprecated)*

Legacy generic field evaluator using rigid same-line Y-axis matching. Retained for backward compatibility with future field types that have not been upgraded to spatial scoring.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `field_type` | `str` | — | Name of the field being evaluated |
| `rule_clause` | `str` | — | LMPC rule reference |
| `fields` | `list[dict]` | — | Classified keyword regions |
| `raw_regions` | `list[dict]` | — | All raw OCR regions |
| `image_path` | `str \| None` | — | Path to image |
| `value_pattern` | `re.Pattern` | — | Regex to match value text |
| `secondary_pattern` | `re.Pattern \| None` | — | Optional secondary pattern |
| `value_extraction_fn` | `callable` | — | Function to extract value from text |
| `min_keyword_confidence` | `float` | `0.3` | Minimum confidence for keyword |
| `min_value_confidence` | `float` | `0.7` | Minimum confidence for value |
| `require_dual_engine` | `bool` | `True` | Whether to require docTR agreement |
