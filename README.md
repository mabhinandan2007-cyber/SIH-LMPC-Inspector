# LMPC Label Scanner MVP

An end-to-end FastAPI + React MVP for verifying packaged-commodity labels against Legal Metrology Rules, 2011 (Rule 6).

## Known Limitations

**OCR Constraints (EasyOCR)**
*   **Handwritten Text:** EasyOCR struggles heavily with unstructured or handwritten text (e.g. handwritten MRP prices). These will typically result in low-confidence garbled text or be missed entirely.
*   **Embossed/Etched Text:** Dot-matrix embossing on curved plastic (e.g., water bottle batch codes) lacks ink contrast and is poorly detected by standard OCR models. It typically returns as high-noise garbage (e.g. `PRR` instead of `MRP`).
*   **Resolution:** The OCR pipeline ingests images natively at 1:1 scale (no aggressive downscaling). However, upscaling (`mag_ratio > 1`) has been tested and shown not to overcome the above limitations for handwriting/embossing.
*   **Handling:** The application fails safely. Illegible text (<20% confidence) or missing keywords will route the scan to `UNCERTAIN` and flag it for manual review in the dashboard queab

abhiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiii
...
