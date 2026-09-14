from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List
import datetime
import uuid
import os
import json
import base64
import io
from jinja2 import Environment, FileSystemLoader
from xhtml2pdf import pisa

from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db import models
from app.ocr.pipeline import run_paddle_ocr
from app.ocr.classifier import classify_fields
from app.rules.engine import run_rule_engine

router = APIRouter()

class ValidationResultModel(BaseModel):
    field_type: str
    status: str
    rule_clause: str
    detail: str

class ScanResponse(BaseModel):
    id: int
    product_id: Optional[int]
    image_path: str
    inspector_id: str
    location: str
    status: str
    created_at: datetime.datetime
    validations: List[ValidationResultModel] = []

@router.post("/upload", response_model=ScanResponse)
async def upload_scan(
    file: UploadFile = File(...),
    inspector_id: str = Form(...),
    location: str = Form(...),
    product_id: Optional[int] = Form(None),
    db: Session = Depends(get_db)
):
    storage_dir = "../storage"
    os.makedirs(storage_dir, exist_ok=True)
    
    file_extension = file.filename.split(".")[-1] if file.filename else "jpg"
    unique_filename = f"{uuid.uuid4()}.{file_extension}"
    file_path = os.path.join(storage_dir, unique_filename)
    
    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())
        
    # 1. Create Scan record
    db_scan = models.Scan(
        product_id=product_id,
        image_path=file_path,
        inspector_id=inspector_id,
        location=location,
        status="processing"
    )
    db.add(db_scan)
    db.commit()
    db.refresh(db_scan)
    
    # 2. Run OCR Pipeline (PaddleOCR detection & extraction)
    raw_regions = run_paddle_ocr(file_path)
    
    # 3. Classify OCR output into Rule 6 fields
    classified_fields = classify_fields(raw_regions)
    
    # Save extractions to DB
    for field in classified_fields:
        db_extraction = models.FieldExtraction(
            scan_id=db_scan.id,
            field_type=field["field_type"],
            bbox=json.dumps(field["bbox"]),
            ocr_text=field["text"],
            confidence=field["confidence"],
            engine_used=field["engine"]
        )
        db.add(db_extraction)
        
    # Run Rule Engine
    validation_results = run_rule_engine(classified_fields, raw_regions, image_path=file_path)
    
    # Save validations and route to review queue if uncertain
    has_uncertain = False
    has_violation = False
    
    for v in validation_results:
        db_val = models.ValidationResult(
            scan_id=db_scan.id,
            field_type=v["field_type"],
            status=v["status"],
            rule_clause=v["rule_clause"],
            detail=v["detail"]
        )
        db.add(db_val)
        
        if v["status"] == "uncertain":
            has_uncertain = True
            db.add(models.ReviewQueueItem(scan_id=db_scan.id, reason=v["detail"]))
        elif v["status"] == "absent":
            has_violation = True
            
    db_scan.status = "needs_review" if has_uncertain else ("failed" if has_violation else "passed")
    db.commit()
    db.refresh(db_scan)
    
    return {
        "id": db_scan.id,
        "product_id": db_scan.product_id,
        "image_path": db_scan.image_path,
        "inspector_id": db_scan.inspector_id,
        "location": db_scan.location,
        "status": db_scan.status,
        "created_at": db_scan.created_at,
        "validations": validation_results
    }

@router.get("/review-queue")
def get_review_queue(db: Session = Depends(get_db)):
    items = db.query(models.ReviewQueueItem).all()
    result = []
    for item in items:
        scan = db.query(models.Scan).filter(models.Scan.id == item.scan_id).first()
        result.append({
            "id": item.id,
            "scan_id": item.scan_id,
            "reason": item.reason,
            "status": "pending",
            "created_at": scan.created_at if scan else datetime.datetime.utcnow(),
            "inspector_id": scan.inspector_id if scan else "Unknown"
        })
    return result

@router.get("/{scan_id}/report")
def generate_report(scan_id: int, db: Session = Depends(get_db)):
    scan = db.query(models.Scan).filter(models.Scan.id == scan_id).first()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
        
    validations = db.query(models.ValidationResult).filter(models.ValidationResult.scan_id == scan_id).all()
    
    # Base64 encode the image
    image_data = None
    if scan.image_path and os.path.exists(scan.image_path):
        try:
            with open(scan.image_path, "rb") as img_file:
                image_data = base64.b64encode(img_file.read()).decode('utf-8')
        except Exception as e:
            pass # fallback to no image
            
    # Load Jinja template
    env = Environment(loader=FileSystemLoader("app/templates"))
    template = env.get_template("report.html")
    
    html_out = template.render(scan=scan, validations=validations, image_data=image_data)
    
    # Generate PDF
    pdf_buffer = io.BytesIO()
    pisa_status = pisa.CreatePDF(io.StringIO(html_out), dest=pdf_buffer)
    
    if pisa_status.err:
        raise HTTPException(status_code=500, detail="PDF generation failed")
        
    pdf_buffer.seek(0)
    
    return StreamingResponse(
        pdf_buffer, 
        media_type="application/pdf", 
        headers={"Content-Disposition": f"attachment; filename=LMPC_Report_{scan_id}.pdf"}
    )
