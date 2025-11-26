"""
Pipeline API Routes
"""
from fastapi import APIRouter, HTTPException
from models.schemas import (
    PipelineStatus, 
    PipelineRunRequest, 
    PipelineRunResponse
)
from services.pipeline_service import pipeline_service

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


@router.post("/run", response_model=PipelineRunResponse)
async def run_pipeline(request: PipelineRunRequest):
    """Execute a pipeline script"""
    try:
        result = await pipeline_service.run_pipeline(request.script)
        return PipelineRunResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop")
async def stop_pipeline():
    """Stop running pipeline"""
    result = await pipeline_service.stop_pipeline()
    return result


@router.get("/status", response_model=PipelineStatus)
async def get_pipeline_status():
    """Get current pipeline execution status"""
    try:
        return pipeline_service.get_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/logs")
async def get_logs(since_line: int = 0):
    """Get pipeline logs from specific line"""
    try:
        result = pipeline_service.get_logs(since_line=since_line)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
