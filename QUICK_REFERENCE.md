# QuantTrade - Quick Reference

## Quick Start

### Windows
```bash
# Double-click or run:
start.bat
```

### Manual Start
```bash
# Terminal 1 - Backend
cd backend
python main.py

# Terminal 2 - Frontend
cd frontend
npm run dev

# Terminal 3 - Telegram Bot (Optional)
python telegram_bot_standalone.py
```

## URLs

- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

## Common Commands

### Run Pipeline
```bash
# Via UI: Click "Run Pipeline" button in Pipeline view
# Or via API:
curl -X POST http://localhost:8000/api/pipeline/run \
  -H "Content-Type: application/json" \
  -d '{"script": "pipeline"}'
```

### Run Portfolio Manager
```bash
# Via UI: Click "Run Live Portfolio Manager" on dashboard
# Or via API:
curl -X POST http://localhost:8000/api/pipeline/run \
  -H "Content-Type: application/json" \
  -d '{"script": "portfolio_manager"}'
```

### Get Portfolio State
```bash
curl http://localhost:8000/api/portfolio/state
```

### Telegram Bot Commands

In Telegram, send to your bot:
- `/start` - Start the bot
- `/subscribe` - Subscribe to signals
- `/status` - View portfolio status
- `/help` - Show help

## File Locations

### Data Files
- Portfolio State: `src/quanttrade/models_2.0/live_state_T1.json`
- Equity History: `src/quanttrade/models_2.0/live_equity_T1.csv`
- Trade History: `src/quanttrade/models_2.0/live_trades_T1.csv`

### Configuration
- Backend: `backend/.env`
- Frontend: `frontend/.env.local`
- Subscribers: `backend/data/subscribers.json`

## Troubleshooting

### Backend won't start
- Check if port 8000 is available
- Verify Python dependencies: `pip install -r backend/requirements.txt`

### Frontend won't connect
- Verify backend is running
- Check `VITE_API_URL` in `frontend/.env.local`

### No data showing
- Run portfolio manager first
- Check if `live_state_T1.json` exists

### Telegram bot not working
- Verify token in `backend/.env`
- Make sure bot is running
- Send `/subscribe` to bot

## Development

### View Logs
- Backend: Check terminal running `python main.py`
- Frontend: Check browser console (F12)
- Telegram: Check terminal running bot

### API Testing
Use the Swagger UI at http://localhost:8000/docs

### Hot Reload
Both backend and frontend support hot reload - changes are reflected automatically.
