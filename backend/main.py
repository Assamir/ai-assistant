"""
Main entry point for the Assystent backend service.
This file sets up and runs the FastAPI application.
"""

import logging
from fastapi import FastAPI
from backend.api.routes import router as api_router

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create the FastAPI app
app = FastAPI(
    title="Assystent Backend",
    description="Local AI gaming companion with 3D avatar",
    version="0.1.0"
)

# Include API routes
app.include_router(api_router, prefix="/api/v1")

@app.get("/")
async def root():
    return {"message": "Assystent Backend is running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)