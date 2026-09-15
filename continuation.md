# LMPC Inspector — Continuation & Hand-off Guide

## Current State (Post-Refactor)

The codebase has been audited, refactored for production quality, and documented. All working OCR/rule-engine logic is preserved. The following files have been refactored with docstrings, type annotations, and structural improvements:

- `backend/app/main.py` — lifespan-based DB init, restricted CORS
- `backend/app/db/database.py` — absolute paths, FK enforcement, rollback
- `backend/app/db/models.py` — cascades, indexes, timezone-aware timestamps
- `backend/app/ocr/pipeline.py` — renamed functions, type hints, legacy aliases
- `backend/app/ocr/classifier.py` — extracted regex constants, docstrings
- `backend/app/rules/engine.py` — extracted shared helpers, full documentation

## Where to Pick Up Work

### Priority 1: Integrate Real PaddleOCR

The function `run_paddle_ocr()` currently calls EasyOCR. PaddleOCR 3.7.0 is already installed. The next step is to:

1. Add a `run_paddleocr_pipeline()` function to `pipeline.py` that calls the actual `PaddleOCR` class.
2. Test it against the Soya and Patanjali benchmark images.
3. Compare extraction quality vs EasyOCR.
4. Either replace EasyOCR or run both engines and merge results.

### Priority 2: Add Fuzzy Matching to Classifier

The classifier currently uses exact regex. OCR frequently misreads keywords:
- `Volume` → `Volunie` (Patanjali)
- `Net Wt` → `Net Vt` (already handled)

Add lightweight fuzzy matching (RapidFuzz) with a high threshold (≥80%) to catch these variants without introducing false positives.

### Priority 3: Add More Field Evaluators

Currently only MRP and Net Quantity are evaluated. The LMPC Rules require:
- **Manufacturer/Packer name and address** — Rule 6(1)(a)
- **Common/generic name** — Rule 6(1)(b)
- **Best Before / Use By date** — Rule 6(1)(f)
- **Country of Origin** (for imports) — Rule 6(1)(h)
- **Customer Care details** — Rule 6(1)(j)

Each needs a dedicated `evaluate_*_rule()` function in `engine.py`.

### Priority 4: Formal Test Suite

The `backend/app/tests/` directory is empty. Create:
- Unit tests for `classifier.py` (regex matching edge cases)
- Unit tests for `engine.py` scoring functions (mock regions, verify scores)
- Integration tests using the benchmark images
- API tests for all endpoints

### Priority 5: Frontend Improvements

- Extract API base URL to a configurable constant
- Add image preview before upload
- Add inline review/approve/reject actions in the review queue
- Mobile-responsive layout optimisation

## Open Technical Debt

| Item | Location | Severity |
|---|---|---|
| `scans.py` uses synchronous file I/O inside an `async def` handler | `scans.py:54-55` | Medium |
| File upload has no size limit or content-type validation | `scans.py:50-55` | Medium |
| `ScanResponse` Pydantic model lacks `model_config = ConfigDict(from_attributes=True)` | `scans.py:29` | Low |
| `storage/` accumulates preprocessed images (`*_preprocessed.jpg`) with no cleanup | `pipeline.py:84` | Low |
| `RuleVersion` model exists but is never populated or queried | `models.py` | Low |
| Frontend hardcodes `http://localhost:8000` | `index.html:33,68` | Low |
| No migration tooling (Alembic) — schema changes require dropping the DB | `database.py` | Low |

## Benchmark Test Commands

```bash
# From backend/ directory with venv311 activated:

# End-to-end Soya Chips test
python test_jar.py ../storage/dca8d6b4-919d-4978-aa1e-c2bccfcf6905.jpeg

# End-to-end Patanjali test
python test_jar.py ../storage/7621f60c-b4ad-4e56-a45b-c0a14cdc0afd.jpeg

# Expected results:
# Soya:      MRP → 45.00, Net Qty → 100 g
# Patanjali: MRP → 50.00, Net Qty → uncertain (keyword not detected)
```

## Running the Application

```bash
# Backend (from backend/ directory)
.\venv311\Scripts\activate
uvicorn app.main:app --reload --port 8000

# Frontend
# Open frontend/index.html directly in a browser (or use VS Code Live Server)
```
