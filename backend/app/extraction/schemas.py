"""
Declaration Extraction Schemas — Data models for extracted statutory declarations.

Defines Pydantic models for structured output produced by the Declaration
Extraction module, bridging OCR text detection with the downstream Legal Rules Engine.
"""

from typing import Any, Optional
from pydantic import BaseModel, Field

# Bounding box matching the OCR pipeline's representation: [[x1, y1], [x2, y2], [x3, y3], [x4, y4]]
BBox = list[list[int]]


class DeclarationField(BaseModel):
    """
    Represents a single extracted statutory declaration field.

    Supports fields such as MRP, NET_QUANTITY, PRODUCT_NAME, MANUFACTURER,
    PACKER, IMPORTER, PACK_DATE, MFG_DATE, BEST_BEFORE, CONSUMER_CARE,
    ADDRESS, COUNTRY_OF_ORIGIN, GSTIN, etc.
    """

    field: str = Field(..., description="Declaration field identifier (e.g. MRP, NET_QUANTITY, MANUFACTURER)")
    value: Any = Field(default=None, description="Extracted and parsed value (e.g. numeric, string, or structured object)")
    raw_text: str = Field(..., description="Original raw OCR text associated with this field")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Extraction confidence score between 0.0 and 1.0")
    bbox: Optional[BBox] = Field(default=None, description="Bounding box coordinates in [[x1, y1], [x2, y2], [x3, y3], [x4, y4]] format")
    source: Optional[str] = Field(default=None, description="OCR engine or source origin (e.g. easyocr, doctr, paddleocr)")
    extraction_method: Optional[str] = Field(default=None, description="Method used for extraction (e.g. regex, spatial_scoring, ner)")


class DeclarationExtractionResult(BaseModel):
    """
    Represents the complete result of declaration extraction for an image or scan.
    """

    declarations: list[DeclarationField] = Field(default_factory=list, description="List of extracted declaration fields")
    image_id: Optional[str] = Field(default=None, description="Optional scan or image identifier")
    overall_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Overall extraction confidence score between 0.0 and 1.0")
