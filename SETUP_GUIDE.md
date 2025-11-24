# QuantTrade - Complete Setup Guide

This guide will help you set up the complete QuantTrade system with FastAPI backend, React frontend, and Telegram bot.

## Prerequisites

- Python 3.8+ with pip
- Node.js 16+ with npm
- Telegram account (for bot setup)

## Quick Start

### 1. Backend Setup

```bash
# Navigate to backend directory
cd backend

# Install Python dependencies
pip install -r requirements.txt

# Create .env file from example
cp .env.example .env

# Edit .env and add your Telegram bot token
# (See "Telegram Bot Setup" section below)
notepad .env  # or use your preferred editor
```

### 2. Frontend Setup

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

### 3. Start the Backend

```bash
# From backend directory
cd backend
python main.py
```

The backend will start on `http://localhost:8000`

### 4. Access the Application

Open your browser and navigate to `http://localhost:5173`

## Telegram Bot Setup

### Creating a Telegram Bot

1. Open Telegram and search for [@BotFather](https://t.me/botfather)
2. Send `/newbot` command
3. Follow the instructions:
   - Choose a name for your bot (e.g., "QuantTrade Signals")
   - Choose a username (must end in 'bot', e.g., "quant_alpha_bot")
4. BotFather will give you a token like: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`
5. Copy this token

### Configuring the Bot

Edit `backend/.env` and set:

```env
TELEGRAM_BOT_TOKEN=your_actual_token_here
TELEGRAM_BOT_USERNAME=@your_bot_username
```

### Running the Telegram Bot

```bash
# From project root
python telegram_bot_standalone.py
```

### Testing the Bot

1. Search for your bot in Telegram using the username
2. Send `/start` to begin
3. Send `/subscribe` to receive signals
4. Send `/status` to see current portfolio

## Project Structure

```
QuantTrade/
├── backend/                    # FastAPI backend
│   ├── api/routes/            # API endpoints
│   ├── services/              # Business logic
│   ├── models/                # Data models
│   ├── main.py                # FastAPI app
│   └── requirements.txt       # Python dependencies
│
├── frontend/                   # React frontend
│   ├── components/            # React components
│   ├── services/              # API client
│   ├── App.tsx                # Main app component
│   └── package.json           # Node dependencies
│
├── src/quanttrade/            # Core trading logic
│   ├── models_2.0/            # Portfolio manager
│   ├── data_sources/          # Data collection
│   ├── data_processing/       # Data cleaning
│   └── feature_engineering/   # Feature creation
│
├── run_daily_pipeline.py      # Daily data pipeline
└── telegram_bot_standalone.py # Telegram bot
```

## Usage

### Running the Daily Pipeline

Click the "Run Pipeline" button in the frontend Pipeline view, or run manually:

```bash
python run_daily_pipeline.py
```

### Running the Live Portfolio Manager

Click the "Run Live Portfolio Manager" button on the dashboard, or run manually:

```bash
python src/quanttrade/models_2.0/live_portfolio_manager.py
```

This will:
1. Load the latest data
2. Execute pending orders
3. Check stop-loss conditions
4. Generate new signals
5. Update `live_state_T1.json`

### Viewing Portfolio Data

The dashboard automatically loads data from:
- `src/quanttrade/models_2.0/live_state_T1.json` - Current portfolio state
- `src/quanttrade/models_2.0/live_equity_T1.csv` - Equity history
- `src/quanttrade/models_2.0/live_trades_T1.csv` - Trade history

### Telegram Notifications

The Telegram bot automatically monitors `live_state_T1.json` and sends notifications when:
- New buy signals are generated
- Portfolio state changes

## API Endpoints

### Portfolio
- `GET /api/portfolio/state` - Current portfolio state
- `GET /api/portfolio/equity` - Equity curve data
- `GET /api/portfolio/trades` - Trade history
- `GET /api/portfolio/summary` - Portfolio metrics

### Pipeline
- `POST /api/pipeline/run` - Execute pipeline
  ```json
  { "script": "pipeline" }  // or "portfolio_manager"
  ```
- `GET /api/pipeline/status` - Execution status
- `GET /api/pipeline/logs` - Pipeline logs

### Telegram
- `GET /api/telegram/config` - Bot configuration
- `PUT /api/telegram/config` - Update configuration
- `GET /api/telegram/subscribers` - List subscribers
- `POST /api/telegram/subscribers` - Add subscriber
- `DELETE /api/telegram/subscribers/{id}` - Remove subscriber
- `POST /api/telegram/broadcast` - Send message to all

## Configuration

### Backend (.env)

```env
# Telegram
TELEGRAM_BOT_TOKEN=your_token_here
TELEGRAM_BOT_USERNAME=@your_bot

# Server
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
CORS_ORIGINS=http://localhost:5173,http://localhost:3000

# Paths (relative to project root)
PROJECT_ROOT=..
LIVE_STATE_PATH=src/quanttrade/models_2.0/live_state_T1.json
LIVE_EQUITY_PATH=src/quanttrade/models_2.0/live_equity_T1.csv
LIVE_TRADES_PATH=src/quanttrade/models_2.0/live_trades_T1.csv
```

### Frontend (.env.local)

```env
VITE_API_URL=http://localhost:8000
```

## Troubleshooting

### Backend won't start

**Error: "Port 8000 already in use"**
- Change `BACKEND_PORT` in `backend/.env`

**Error: "Module not found"**
- Make sure you installed dependencies: `pip install -r backend/requirements.txt`
- Run from project root directory

### Frontend won't connect to backend

**Error: "Failed to fetch"**
- Verify backend is running on `http://localhost:8000`
- Check CORS settings in `backend/.env`
- Verify `VITE_API_URL` in `frontend/.env.local`

### Telegram bot not working

**Bot doesn't respond**
- Verify token is correct in `backend/.env`
- Make sure bot is running: `python telegram_bot_standalone.py`
- Check bot is not in test mode (can configure via API)

**Signals not being sent**
- Verify `live_state_T1.json` exists and is being updated
- Check bot has subscribers: send `/subscribe` to the bot
- Look for errors in bot console output

### No portfolio data showing

**Dashboard shows "No data"**
- Run the live portfolio manager first
- Verify `live_state_T1.json` exists in `src/quanttrade/models_2.0/`
- Check backend logs for errors

## Development

### API Documentation

Visit `http://localhost:8000/docs` for interactive API documentation (Swagger UI)

### Hot Reload

- Backend: Automatically reloads when files change (if using `--reload` flag)
- Frontend: Vite dev server hot-reloads automatically

### Testing

```bash
# Test backend endpoints
curl http://localhost:8000/health

# Test portfolio state
curl http://localhost:8000/api/portfolio/state

# Run pipeline
curl -X POST http://localhost:8000/api/pipeline/run \
  -H "Content-Type: application/json" \
  -d '{"script": "portfolio_manager"}'
```

## Production Deployment

### Backend

```bash
# Install production server
pip install gunicorn

# Run with gunicorn
gunicorn backend.main:app -w 4 -k uvicorn.workers.UvicornWorker
```

### Frontend

```bash
# Build for production
cd frontend
npm run build

# Serve with a static file server
npx serve -s dist
```

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review API documentation at `/docs`
3. Check console logs for errors
4. Verify all configuration files are correct

## Next Steps

1. ✅ Set up Telegram bot token
2. ✅ Run the backend
3. ✅ Run the frontend
4. ✅ Run the portfolio manager to generate initial data
5. ✅ Subscribe to the Telegram bot
6. ✅ Monitor your portfolio!
