"""
SQLAlchemy ORM models for the LMPC Scanner system.

Defines the relational schema for products, scans, OCR field extractions,
rule-engine validation results, rule versioning, and the human review queue.
"""

import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from .database import Base


class Product(Base):
    """Master product catalogue entry."""

    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    category = Column(String, index=True)
    manufacturer_name = Column(String)

    scans = relationship("Scan", back_populates="product")


class Scan(Base):
    """
    Represents a single inspection event — one label image uploaded by
    an inspector at a specific location.
    """

    __tablename__ = "scans"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True, index=True)
    image_path = Column(String)
    inspector_id = Column(String, index=True)
    location = Column(String)
    status = Column(String, default="pending")  # pending | processing | passed | failed | needs_review
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))

    product = relationship("Product", back_populates="scans")
    field_extractions = relationship(
        "FieldExtraction", back_populates="scan", cascade="all, delete-orphan"
    )
    validation_results = relationship(
        "ValidationResult", back_populates="scan", cascade="all, delete-orphan"
    )
    review_items = relationship(
        "ReviewQueueItem", back_populates="scan", cascade="all, delete-orphan"
    )


class FieldExtraction(Base):
    """
    A single OCR-detected text region classified as a statutory field
    (e.g. MRP, Net Quantity).
    """

    __tablename__ = "field_extractions"

    id = Column(Integer, primary_key=True, index=True)
    scan_id = Column(Integer, ForeignKey("scans.id"), index=True)
    field_type = Column(String)  # mrp | net_quantity | manufacturer | ...
    bbox = Column(String)  # JSON-serialised bounding box [[x1,y1],...]
    ocr_text = Column(String)
    confidence = Column(Float)
    engine_used = Column(String)  # easyocr | doctr | paddleocr

    scan = relationship("Scan", back_populates="field_extractions")


class ValidationResult(Base):
    """
    Outcome of a single rule-engine check against a classified field.
    Status is one of: ``present``, ``absent``, or ``uncertain``.
    """

    __tablename__ = "validation_results"

    id = Column(Integer, primary_key=True, index=True)
    scan_id = Column(Integer, ForeignKey("scans.id"), index=True)
    field_type = Column(String)
    status = Column(String)  # present | absent | uncertain
    rule_clause = Column(String)  # e.g. "Rule 6(1)(e)"
    detail = Column(String)

    scan = relationship("Scan", back_populates="validation_results")


class RuleVersion(Base):
    """
    Versioned snapshot of the LMPC rule definitions, stored as JSON
    so that historical scans can be re-evaluated against the rules
    that were active at the time.
    """

    __tablename__ = "rule_versions"

    id = Column(Integer, primary_key=True, index=True)
    version = Column(String)
    effective_date = Column(DateTime)
    rules_json = Column(String)  # JSON blob


class ReviewQueueItem(Base):
    """
    An item routed to the human review queue when the rule engine
    returns an ``uncertain`` verdict.
    """

    __tablename__ = "review_queue_items"

    id = Column(Integer, primary_key=True, index=True)
    scan_id = Column(Integer, ForeignKey("scans.id"), index=True)
    reason = Column(String)
    assigned_to = Column(String, nullable=True)
    resolved = Column(Boolean, default=False)

    scan = relationship("Scan", back_populates="review_items")
