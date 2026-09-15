# LMPC Inspector — Coding Standards & Constraints

## Python Conventions

### Naming
- **Files**: `snake_case.py`
- **Functions / Variables**: `snake_case`
- **Classes**: `PascalCase`
- **Constants**: `UPPER_SNAKE_CASE`
- **Private helpers**: prefix with `_` (e.g. `_bbox_center`)

### Formatting
- Max line length: 100 characters (soft limit), 120 (hard limit).
- Use trailing commas in multi-line collections and function signatures.
- Imports ordered: stdlib → third-party → local, separated by blank lines.

### Type Annotations
- All public functions must have full type annotations (arguments + return).
- Use `from __future__ import annotations` in modules with forward refs.
- Prefer `list[dict]` over `List[Dict]` (Python 3.10+ style).

### Docstrings
- Every module, class, and public function requires a docstring.
- Use Google-style docstrings with `Args:`, `Returns:`, `Raises:` sections.
- Explain *why* the function exists, not just what it does.

## Error Handling

- Database sessions must be wrapped in try/except/finally with `db.rollback()` on exception.
- OCR functions must never raise — return `None` or empty containers on failure.
- API endpoints should catch OCR/rule-engine errors and return structured HTTP 500 responses.

## Architecture Patterns

### Allowed
- **Spatial candidate scoring**: search a neighbourhood, score candidates, pick the best.
- **Deterministic regex penalties**: blacklist numbers matching date/phone/price patterns.
- **Adaptive bounding-box expansion**: padding proportional to keyword size, not hard-coded pixels.
- **Legacy aliases**: keep old function names as aliases (`run_paddle_ocr = run_ocr_pipeline`).

### Forbidden (Anti-Patterns)
- ❌ **Hard-coded pixel offsets** for bounding box expansion (breaks at different resolutions).
- ❌ **First-number extraction** (`numbers[0]`) — always score all candidates.
- ❌ **Rigid same-line Y-axis matching** for value association — use 2D spatial search.
- ❌ **External API calls** (Gemini, OpenAI, etc.) in the OCR/rule path — must stay offline.
- ❌ **`datetime.datetime.utcnow()`** — use `datetime.datetime.now(datetime.timezone.utc)`.
- ❌ **Relative paths** (`../storage`) — resolve from `__file__` or config.
- ❌ **`allow_origins=["*"]` with `allow_credentials=True`** — explicitly list origins.

## Testing

- Benchmark images are stored in `storage/`:
  - Soya Chips: `dca8d6b4-919d-4978-aa1e-c2bccfcf6905.jpeg`
  - Patanjali: `7621f60c-b4ad-4e56-a45b-c0a14cdc0afd.jpeg`
- After any `engine.py` or `classifier.py` change, verify:
  - Soya: MRP → `45.00`, Net Qty → `100 g`
  - Patanjali: MRP → `50.00`
- Use `test_jar.py` for end-to-end pipeline tests.

## Logging
- Use `print()` for debugging only — remove before committing.
- Future: migrate to `logging` module with structured log levels.

## Frontend
- Single HTML file with CDN-loaded React/Tailwind — no build step.
- API base URL is hardcoded to `http://localhost:8000` — extract to config for deployment.
