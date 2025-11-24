"""
FastAPI Main Application
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.config import settings
from backend.api.routes import portfolio, pipeline, telegram

# Create FastAPI app
app = FastAPI(
    title="QuantTrade API",
    description="Backend API for QuantTrade algorithmic trading platform",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(portfolio.router)
app.include_router(pipeline.router)
app.include_router(telegram.router)


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
        host=settings.backend_host,
        port=settings.backend_port,
        reload=True
    )
