# QuantTrade Backend

FastAPI backend for the QuantTrade algorithmic trading platform.

## Features

- **Portfolio Management**: Real-time portfolio state, equity history, and trade tracking
- **Pipeline Execution**: Run data pipelines and live portfolio manager
- **Telegram Bot**: Send trading signals to subscribers via Telegram

## Setup

### 1. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

Edit `.env` and set your Telegram bot token:

```env
TELEGRAM_BOT_TOKEN=your_actual_bot_token_here
```

To create a Telegram bot:
1. Message [@BotFather](https://t.me/botfather) on Telegram
2. Send `/newbot` and follow instructions
3. Copy the token provided

### 3. Run the Backend

```bash
# From the backend directory
python main.py

# Or use uvicorn directly
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

## API Documentation

Once running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## API Endpoints

### Portfolio
- `GET /api/portfolio/state` - Current portfolio state
- `GET /api/portfolio/equity` - Equity history
- `GET /api/portfolio/trades` - Trade history
- `GET /api/portfolio/summary` - Portfolio summary

### Pipeline
- `POST /api/pipeline/run` - Execute pipeline script
- `GET /api/pipeline/status` - Pipeline execution status
- `GET /api/pipeline/logs` - Pipeline logs

### Telegram
- `GET /api/telegram/config` - Bot configuration
- `PUT /api/telegram/config` - Update bot configuration
- `GET /api/telegram/subscribers` - List subscribers
- `POST /api/telegram/subscribers` - Add subscriber
- `PUT /api/telegram/subscribers/{id}` - Update subscriber
- `DELETE /api/telegram/subscribers/{id}` - Delete subscriber
- `POST /api/telegram/broadcast` - Broadcast message

## Telegram Bot

### Run Standalone Bot

```bash
# From project root
python telegram_bot_standalone.py
```

### Bot Commands

- `/start` - Start the bot
- `/subscribe` - Subscribe to daily signals
- `/unsubscribe` - Unsubscribe from signals
- `/status` - View current portfolio status
- `/help` - Show help message

## Project Structure

```
backend/
├── api/
│   └── routes/
│       ├── portfolio.py    # Portfolio endpoints
│       ├── pipeline.py     # Pipeline endpoints
│       └── telegram.py     # Telegram endpoints
├── models/
│   └── schemas.py          # Pydantic models
├── services/
│   ├── portfolio_service.py    # Portfolio data management
│   ├── pipeline_service.py     # Pipeline execution
│   └── telegram_service.py     # Telegram bot management
├── data/
│   └── subscribers.json    # Telegram subscribers database
├── config.py               # Configuration management
├── main.py                 # FastAPI application
└── requirements.txt        # Python dependencies
```

## Development

### CORS Configuration

The backend is configured to allow requests from:
- `http://localhost:5173` (Vite dev server)
- `http://localhost:3000` (Alternative dev server)

To add more origins, update `CORS_ORIGINS` in `.env`.

### Test Mode

Telegram bot starts in test mode by default. Messages won't actually be sent to Telegram. To disable test mode, update the configuration via the API or set it in the Telegram service.

## Troubleshooting

### Port Already in Use

If port 8000 is already in use, change it in `.env`:

```env
BACKEND_PORT=8001
```

### Module Import Errors

Make sure you're running from the project root directory and the backend package is in your Python path.

### Telegram Bot Not Working

1. Verify your bot token is correct in `.env`
2. Check that the bot is not already running elsewhere
3. Ensure subscribers.json has the correct chat IDs
