from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import scans
from app.db.database import engine, Base

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="LMPC Label Scanner API")

# Setup CORS for the React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # For dev only, restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(scans.router, prefix="/api/scans", tags=["scans"])

@app.get("/")
def read_root():
    return {"message": "LMPC Scanner API is running"}
