"""
Telegram API Routes
"""
from fastapi import APIRouter, HTTPException
from typing import List
from backend.models.schemas import (
    TelegramConfig,
    TelegramConfigUpdate,
    TelegramSubscriber,
    TelegramSubscriberCreate,
    TelegramSubscriberUpdate,
    BroadcastMessage
)
from backend.services.telegram_service import telegram_service

router = APIRouter(prefix="/api/telegram", tags=["telegram"])


@router.get("/config", response_model=TelegramConfig)
async def get_telegram_config():
    """Get Telegram bot configuration"""
    try:
        return telegram_service.get_config()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/config", response_model=TelegramConfig)
async def update_telegram_config(config: TelegramConfigUpdate):
    """Update Telegram bot configuration"""
    try:
        return telegram_service.update_config(
            bot_token=config.bot_token,
            bot_username=config.bot_username,
            test_mode=config.test_mode
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/subscribers", response_model=List[TelegramSubscriber])
async def get_subscribers():
    """Get all Telegram subscribers"""
    try:
        return telegram_service.get_subscribers()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/subscribers", response_model=TelegramSubscriber)
async def add_subscriber(subscriber: TelegramSubscriberCreate):
    """Add a new Telegram subscriber"""
    try:
        return telegram_service.add_subscriber(subscriber)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/subscribers/{subscriber_id}", response_model=TelegramSubscriber)
async def update_subscriber(subscriber_id: int, update: TelegramSubscriberUpdate):
    """Update a Telegram subscriber"""
    try:
        result = telegram_service.update_subscriber(
            subscriber_id,
            name=update.name,
            active=update.active,
            role=update.role
        )
        if result is None:
            raise HTTPException(status_code=404, detail="Subscriber not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/subscribers/{subscriber_id}")
async def delete_subscriber(subscriber_id: int):
    """Delete a Telegram subscriber"""
    try:
        success = telegram_service.delete_subscriber(subscriber_id)
        if not success:
            raise HTTPException(status_code=404, detail="Subscriber not found")
        return {"message": "Subscriber deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/broadcast")
async def broadcast_message(message: BroadcastMessage):
    """Broadcast a message to all active subscribers"""
    try:
        result = await telegram_service.broadcast_message(message)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
