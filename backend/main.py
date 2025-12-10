"""
FastAPI Main Application
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import settings
from api.routes import portfolio, pipeline, telegram, gpt

# Create FastAPI app
app = FastAPI(
    title="QuantTrade API",
    description="Backend API for QuantTrade algorithmic trading platform",
    version="1.0.0"
)

# Configure CORS - Allow all origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,  # Must be False when using "*" origins
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Include routers
app.include_router(portfolio.router)
app.include_router(pipeline.router)
app.include_router(telegram.router)
app.include_router(gpt.router)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "QuantTrade API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "services": {
            "portfolio": "ok",
            "pipeline": "ok",
            "telegram": "ok"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False  # Disable auto-reload for production stability
    )
