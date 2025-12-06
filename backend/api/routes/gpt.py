"""
GPT Analysis API Routes
"""
from fastapi import APIRouter, HTTPException
from services.gpt_service import get_latest_analysis

router = APIRouter(prefix="/api/gpt", tags=["gpt"])


@router.get("/analysis")
async def get_gpt_analysis():
    """Get latest GPT portfolio analysis"""
    try:
        analysis = get_latest_analysis()
        
        if analysis is None:
            return {
                "available": False,
                "message": "No GPT analysis available yet"
            }
        
        return {
            "available": True,
            "data": analysis
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
