# 🐝 Hive Trading System

AI-Orchestrated Multi-Strategy Crypto Trading System

## Architecture

```
Frontend (Next.js) ← HTTP/WebSocket → Backend (Python)
                                        ├─ Hive Manager
                                        ├─ Queen Scheduler → AI (LM Studio)
                                        └─ Worker Pool (asyncio)
                                             └─ Strategy Plugins
                                        ↓
                                  Redis + PostgreSQL
```

## Features

- **AI-Driven Decisions**: LM Studio integration for intelligent worker deployment
- **Multi-Strategy Support**: Pluggable strategy system (starting with Infinite Grid)
- **Real-Time Monitoring**: WebSocket-powered dashboard
- **State Persistence**: Full recovery after crashes
- **Capital Management**: Automatic allocation and risk limits
- **Market Scanner**: Centralized WebSocket data streaming

## Prerequisites

- Python 3.10+
- Node.js 18+
- PostgreSQL 14+
- Redis 7+
- LM Studio (optional, falls back to rule-based)

## Quick Start

### 1. Database Setup

```bash
# Create database
createdb hive_trading_system

# Run schema
psql hive_trading_system < backend/schema.sql
```

### 2. Backend Setup

```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp ../.env.example .env
# Edit .env with your API keys and settings

# Run backend
python main.py
```

### 3. API Server (separate terminal)

```bash
cd backend
python api/main.py
```

### 4. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev
```

### 5. Access Dashboard

Open http://localhost:3000

## Configuration

### Environment Variables

Key settings in `.env`:

```bash
# Exchange
EXCHANGE=binance
BINANCE_API_KEY=your_key
BINANCE_API_SECRET=your_secret

# Hive
HIVE_TOTAL_CAPITAL=10000
HIVE_MAX_WORKERS=10

# Database
POSTGRES_HOST=127.0.0.1
POSTGRES_DATABASE=hive_trading_system

# Redis
REDIS_HOST=127.0.0.1

# LM Studio
LM_STUDIO_URL=http://localhost:1234/v1
LM_STUDIO_API_KEY=lm-studio
LM_STUDIO_MODEL=local-model
LM_STUDIO_ENABLED=true
```

### LM Studio Setup

1. Download LM Studio from https://lmstudio.ai/
2. Load a model (recommended: Mistral 7B or Llama 3)
3. Start local server:
   - Click "Local Server" tab in LM Studio
   - Click "Start Server" (default port 1234)
   - Optional: Set API key in server settings (or use default "lm-studio")
4. Configure in `.env`:
   ```bash
   LM_STUDIO_URL=http://localhost:1234/v1
   LM_STUDIO_API_KEY=lm-studio  # Or your custom key
   LM_STUDIO_MODEL=local-model
   LM_STUDIO_ENABLED=true
   ```

**Note**: LM Studio local server typically doesn't require authentication. The API key is included for compatibility but defaults to "lm-studio" if not set.

If LM Studio is unavailable, system falls back to rule-based logic.

## System Components

### Backend

- **Hive Manager** (`core/hive.py`): Worker orchestration and capital management
- **Queen Scheduler** (`core/queen.py`): AI-driven worker deployment
- **Worker Engine** (`core/worker.py`): Strategy execution engine
- **Market Scanner** (`market/scanner.py`): Centralized data collection
- **AI Engine** (`ai/decision_engine.py`): LM Studio integration
- **Strategies** (`strategies/`): Pluggable trading strategies

### Frontend

- **Dashboard**: Real-time hive overview
- **Workers**: Worker management and control
- **Market**: Live price monitoring
- **Analytics**: Performance metrics
- **Risk**: Risk management dashboard

## API Endpoints

### Hive
- `GET /hive/status` - Hive overview

### Workers
- `GET /workers` - List all workers
- `GET /workers/{id}` - Worker details
- `POST /workers` - Create worker
- `PUT /workers/{id}/command` - Send command (pause/resume/stop)

### Market
- `GET /market/prices` - Current prices

### Analytics
- `GET /analytics/pnl` - PnL analytics
- `GET /queen/decisions` - AI decision history

### WebSocket
- `WS /ws` - Real-time updates

## Adding New Strategies

1. Create strategy class in `backend/strategies/`:

```python
from strategies.base_strategy import BaseStrategy, StrategyRegistry

@StrategyRegistry.register("my_strategy")
class MyStrategy(BaseStrategy):
    async def start(self, initial_state):
        # Initialize strategy
        pass
    
    async def on_price_update(self, price, timestamp):
        # Handle price updates
        pass
    
    async def on_order_filled(self, order):
        # Handle order fills
        pass
    
    async def reload_config(self, new_config):
        # Reload configuration
        pass
    
    async def stop(self):
        # Cleanup
        pass
```

2. Strategy is automatically available for deployment

## Monitoring

### Logs

Backend logs are written to console and can be redirected:

```bash
python main.py 2>&1 | tee hive.log
```

### Database Queries

```sql
-- Active workers
SELECT * FROM workers WHERE status = 'running';

-- Recent trades
SELECT * FROM worker_trades ORDER BY created_at DESC LIMIT 10;

-- AI decisions
SELECT * FROM queen_decisions ORDER BY created_at DESC LIMIT 10;
```

### Redis Monitoring

```bash
redis-cli
> KEYS worker:*:status
> GET worker:1:status
```

## Testing

### Run Tests

```bash
# Install test dependencies
pip install -r tests/requirements.txt

# Run all tests
./run_tests.sh

# Or use pytest directly
pytest tests/ -v
```

### Test Coverage

- **Redis Client**: Connection, price cache, commands, heartbeat
- **Strategy System**: Lifecycle, registry, state management
- **Grid Strategy**: Initialization, grid updates, ATR calculation
- **AI Engine**: Rule-based decisions, prompt building
- **API Endpoints**: All REST endpoints, error handling

## Troubleshooting

### Worker not starting
- Check database connection
- Verify Redis is running
- Check worker logs in console

### No market data
- Verify exchange API keys
- Check Market Scanner is running
- Verify Redis connection

### AI decisions not working
- Check LM Studio is running on port 1234
- System will fall back to rule-based logic
- Check `LM_STUDIO_ENABLED=true` in .env

## Production Deployment

### Docker Compose

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Security

- Use strong PostgreSQL passwords
- Restrict API access with firewall rules
- Store API keys in secure vault
- Enable HTTPS for production

## License

MIT License - see LICENSE file

## Support

For issues and questions, please open a GitHub issue.
