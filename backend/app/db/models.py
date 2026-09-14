from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Float, DateTime
from sqlalchemy.orm import relationship
import datetime
from .database import Base

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    category = Column(String, index=True)
    manufacturer_name = Column(String)
    
    scans = relationship("Scan", back_populates="product")

class Scan(Base):
    __tablename__ = "scans"
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    image_path = Column(String)
    inspector_id = Column(String)
    location = Column(String)
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    product = relationship("Product", back_populates="scans")
    field_extractions = relationship("FieldExtraction", back_populates="scan")
    validation_results = relationship("ValidationResult", back_populates="scan")

class FieldExtraction(Base):
    __tablename__ = "field_extractions"
    id = Column(Integer, primary_key=True, index=True)
    scan_id = Column(Integer, ForeignKey("scans.id"))
    field_type = Column(String)
    bbox = Column(String) # Stored as JSON string
    ocr_text = Column(String)
    confidence = Column(Float)
    engine_used = Column(String)
    
    scan = relationship("Scan", back_populates="field_extractions")

class ValidationResult(Base):
    __tablename__ = "validation_results"
    id = Column(Integer, primary_key=True, index=True)
    scan_id = Column(Integer, ForeignKey("scans.id"))
    field_type = Column(String)
    status = Column(String) # present, absent, uncertain
    rule_clause = Column(String)
    detail = Column(String)
    
    scan = relationship("Scan", back_populates="validation_results")

class RuleVersion(Base):
    __tablename__ = "rule_versions"
    id = Column(Integer, primary_key=True, index=True)
    version = Column(String)
    effective_date = Column(DateTime)
    rules_json = Column(String) # stored as JSON string

class ReviewQueueItem(Base):
    __tablename__ = "review_queue_items"
    id = Column(Integer, primary_key=True, index=True)
    scan_id = Column(Integer, ForeignKey("scans.id"))
    reason = Column(String)
    assigned_to = Column(String, nullable=True)
    resolved = Column(Boolean, default=False)
