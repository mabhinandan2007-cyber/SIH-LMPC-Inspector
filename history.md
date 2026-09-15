# LMPC Inspector — Project History & Decision Log

## Chronological Development Timeline

### Phase 0: Initial Scaffold (Pre-Audit)
- **Backend**: FastAPI project created with `main.py`, `scans.py`, `database.py`, `models.py`.
- **Frontend**: Single `index.html` with React 18 + Tailwind CSS via CDN.
- **OCR**: Function named `run_paddle_ocr()` was created but internally used **EasyOCR** — PaddleOCR was never actually wired in despite being installed.
- **Rule Engine**: Used a rigid `evaluate_field_rule()` with strict same-line Y-axis matching and naive first-number extraction.

### Phase 1: Codebase Audit (Session 1)
**Objective**: Diagnose why OCR was failing to reliably extract MRP and Net Quantity from real product images.

**Key Findings**:
1. `run_paddle_ocr()` was a misnomer — it called `easyocr.Reader(['en'])`.
2. The docTR crop verification used a fixed 5px padding, making it blind to prices printed more than a few pixels away from the keyword.
3. The rule engine's `same_line_regions` check dropped any value not on the exact same Y-coordinate as the keyword.
4. The `re.search(r'\d+')` extraction grabbed the first number it found, often noise or dates.
5. The MRP classifier regex matched `rs` inside words like `cadersis`.

### Phase 2: docTR Cropping Fix
**Decision**: Replace fixed 5px crop padding with **adaptive padding proportional to the keyword's own bounding-box dimensions**.

**Rationale**: Different images have vastly different resolutions. A fixed pixel offset that works on one image fails on another. By scaling the crop to `1.5x width left, 4x width right, 2x height top, 6x height bottom`, the crop captures the keyword's surrounding context regardless of scale.

**Also added**: Coordinate mapping from docTR's relative `[0..1]` geometry back to absolute pixel coordinates on the original uploaded image. This was essential for preserving bounding boxes through the entire pipeline.

### Phase 3: MRP Classifier False Positives
**Decision**: Add explicit word boundaries (`\b`) to the classifier regex and separate explicit MRP labels from standalone currency indicators.

**Rationale**: The word `cadersis` contained the substring `rs`, which the old regex matched as a currency indicator. This sent docTR to verify the wrong region of the image. By requiring word boundaries and applying a confidence penalty (0.8x) to standalone currency matches, false positives were eliminated while preserving genuine `Rs.` matches.

### Phase 4: MRP Spatial Scoring
**Decision**: Completely rewrite `evaluate_mrp_rule()` with a 2D spatial candidate scoring algorithm.

**Rationale**: The old approach required values to be on the exact same horizontal line as the keyword. The Patanjali product has `₹ 50.00` printed two lines below the `MRP` label. A rigid Y-axis constraint is fundamentally incompatible with real-world product label layouts.

**Key design choices**:
- **Full-text blacklisting**: Scan the entire OCR output to identify dates, phone numbers, batch codes, and unit prices, then penalize any candidate whose numeric value appears in that blacklist by −1000 points.
- **Multi-source scoring**: Evaluate candidates from the label box itself, nearby EasyOCR regions, AND nearby docTR word boxes.
- **Proximity decay**: Closer candidates score higher via a linear decay function.

### Phase 5: Net Quantity Extraction
**Decision**: Apply the same spatial scoring architecture to `evaluate_net_quantity_rule()`, with unit-aware candidate filtering and canonical unit normalisation.

**Rationale**: Net Quantity suffered from the identical rigid Y-axis and first-number bugs as MRP. The additional requirement was that candidates must contain a recognised physical unit (g, kg, ml, etc.) to be considered — bare numbers without units are not valid Net Quantity declarations.

**Key design choices**:
- Unit aliases (`gms` → `g`, `litres` → `l`) for consistent comparison.
- docTR word boxes clustered into lines before scoring, since docTR outputs word-by-word.
- MRP-prefixed numbers explicitly blacklisted to prevent price values from being selected as quantities.
- Added `net\s*vt` to the classifier regex for the common docTR misreading of "Net Wt".

---

## Refactoring Session (Current)

### Changes Applied

| File | Change | Rationale |
|---|---|---|
| `main.py` | Moved `create_all` to lifespan handler; restricted CORS origins; added docstrings and type annotations | Prevents DDL side-effects on import; fixes CORS spec violation |
| `database.py` | Absolute path resolution via `__file__`; SQLite FK enforcement; exception rollback in `get_db()` | Eliminates CWD-dependent path bugs; enforces referential integrity |
| `models.py` | Added cascade deletes, FK indexes, timezone-aware timestamps, ReviewQueueItem↔Scan relationship | Prevents orphan rows; improves query performance |
| `pipeline.py` | Renamed functions to meaningful names; added type hints, docstrings; kept legacy aliases | Improved readability without breaking backward compatibility |
| `classifier.py` | Extracted regexes to module-level constants; added docstrings | Cleaner code, easier to modify patterns |
| `engine.py` | Extracted shared helpers (`_bbox_center`, `_spatial_score`, `_extract_date_numbers`, etc.); added module and function docstrings | Eliminated code duplication between MRP and Net Qty evaluators |
