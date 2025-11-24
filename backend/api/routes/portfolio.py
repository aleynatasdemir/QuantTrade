"""
Portfolio API Routes
"""
from fastapi import APIRouter, HTTPException
from typing import List
from backend.models.schemas import PortfolioState, EquityPoint, Trade
from backend.services.portfolio_service import portfolio_service

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


@router.get("/state", response_model=PortfolioState)
async def get_portfolio_state():
    """Get current portfolio state"""
    try:
        return portfolio_service.get_portfolio_state()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/equity", response_model=List[EquityPoint])
async def get_equity_history():
    """Get equity history"""
    try:
        return portfolio_service.get_equity_history()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trades", response_model=List[Trade])
async def get_trades_history():
    """Get trade history"""
    try:
        return portfolio_service.get_trades_history()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary")
async def get_portfolio_summary():
    """Get portfolio summary with key metrics"""
    try:
        return portfolio_service.get_portfolio_summary()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
