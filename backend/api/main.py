"""FastAPI backend for Hive Trading System"""
import asyncio
import os
from contextlib import asynccontextmanager
from typing import List, Dict, Any, Optional, Literal

import asyncpg
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field

from infra.redis_client import RedisClient

load_dotenv()

# --- Configuration ---
API_KEY = os.getenv("API_KEY", "")
ALLOWED_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")

# --- Global state ---
db_pool: Optional[asyncpg.Pool] = None
redis_client: Optional[RedisClient] = None


# --- Auth ---
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: Optional[str] = Security(api_key_header)):
    """Verify API key if configured"""
    if not API_KEY:
        return  # No API key configured, skip auth
    if api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


# --- Lifespan ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_pool, redis_client

    # Startup
    db_pool = await asyncpg.create_pool(
        host=os.getenv("POSTGRES_HOST", "127.0.0.1"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_DATABASE", "hive_trading_system"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", ""),
        min_size=int(os.getenv("POSTGRES_MIN_CONNECTIONS", "2")),
        max_size=int(os.getenv("POSTGRES_MAX_CONNECTIONS", "10")),
    )

    redis_client = RedisClient(
        host=os.getenv("REDIS_HOST", "127.0.0.1"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        db=int(os.getenv("REDIS_DB", "0")),
        password=os.getenv("REDIS_PASSWORD") or None,
    )
    await redis_client.connect()

    print("[API] Started")
    yield

    # Shutdown
    if redis_client:
        await redis_client.close()
    if db_pool:
        await db_pool.close()


app = FastAPI(title="Hive Trading System API", lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "X-API-Key"],
)


# --- Models ---
class WorkerCommand(BaseModel):
    command: Literal["pause", "resume", "stop"]


class WorkerCreate(BaseModel):
    strategy_name: str
    symbol: str
    capital: float = Field(gt=0)
    config: Dict[str, Any]


# --- Endpoints ---
@app.get("/hive/status", dependencies=[Depends(verify_api_key)])
async def get_hive_status():
    """Get hive overview"""
    async with db_pool.acquire() as conn:
        hive = await conn.fetchrow("SELECT * FROM hives WHERE id = 1")
        if not hive:
            raise HTTPException(404, "Hive not found")

        stats = await conn.fetchrow('''
            SELECT
                COUNT(*) as total_workers,
                COUNT(*) FILTER (WHERE status = 'running') as running_workers,
                COALESCE(SUM(pnl), 0) as total_pnl
            FROM workers WHERE hive_id = 1
        ''')

        return {
            "hive_id": hive["id"],
            "name": hive["name"],
            "exchange": hive["exchange"],
            "total_capital": float(hive["total_capital"]),
            "used_capital": float(hive["used_capital"]),
            "free_capital": float(hive["total_capital"]) - float(hive["used_capital"]),
            "max_workers": hive["max_workers"],
            "total_workers": stats["total_workers"],
            "running_workers": stats["running_workers"],
            "total_pnl": float(stats["total_pnl"]),
        }


@app.get("/workers", dependencies=[Depends(verify_api_key)])
async def list_workers():
    """List all workers"""
    async with db_pool.acquire() as conn:
        rows = await conn.fetch('''
            SELECT id, strategy_name, symbol, capital, status, pnl, total_trades, created_at
            FROM workers
            WHERE hive_id = 1
            ORDER BY created_at DESC
        ''')

        return [
            {
                "id": row["id"],
                "strategy": row["strategy_name"],
                "symbol": row["symbol"],
                "capital": float(row["capital"]),
                "status": row["status"],
                "pnl": float(row["pnl"]),
                "total_trades": row["total_trades"],
                "created_at": row["created_at"].isoformat(),
            }
            for row in rows
        ]


@app.get("/workers/{worker_id}", dependencies=[Depends(verify_api_key)])
async def get_worker(worker_id: int):
    """Get worker details"""
    async with db_pool.acquire() as conn:
        worker = await conn.fetchrow(
            "SELECT * FROM workers WHERE id = $1", worker_id
        )
        if not worker:
            raise HTTPException(404, "Worker not found")

        return {
            "id": worker["id"],
            "strategy": worker["strategy_name"],
            "symbol": worker["symbol"],
            "capital": float(worker["capital"]),
            "status": worker["status"],
            "pnl": float(worker["pnl"]),
            "total_trades": worker["total_trades"],
            "config": worker["config"],
            "state": worker["state"],
            "created_at": worker["created_at"].isoformat(),
        }


@app.post("/workers", dependencies=[Depends(verify_api_key)])
async def create_worker(worker: WorkerCreate):
    """Create a new worker with capital validation"""
    async with db_pool.acquire() as conn:
        async with conn.transaction():
            hive = await conn.fetchrow(
                "SELECT total_capital, used_capital, max_workers FROM hives WHERE id = 1 FOR UPDATE"
            )
            if not hive:
                raise HTTPException(404, "Hive not found")

            # Check max workers
            worker_count = await conn.fetchval(
                "SELECT COUNT(*) FROM workers WHERE hive_id = 1 AND status IN ('init', 'running', 'paused')"
            )
            if worker_count >= hive["max_workers"]:
                raise HTTPException(400, "Maximum worker count reached")

            # Check capital
            free_capital = float(hive["total_capital"]) - float(hive["used_capital"])
            if worker.capital > free_capital:
                raise HTTPException(
                    400,
                    f"Insufficient capital: requested {worker.capital}, available {free_capital:.2f}",
                )

            worker_id = await conn.fetchval(
                '''
                INSERT INTO workers (hive_id, strategy_name, symbol, capital, status, config)
                VALUES (1, $1, $2, $3, 'init', $4)
                RETURNING id
            ''',
                worker.strategy_name,
                worker.symbol,
                worker.capital,
                worker.config,
            )

            # Reserve capital in the same transaction
            await conn.execute(
                "UPDATE hives SET used_capital = used_capital + $1 WHERE id = 1",
                worker.capital,
            )

            return {"worker_id": worker_id, "status": "created"}


@app.put("/workers/{worker_id}/command", dependencies=[Depends(verify_api_key)])
async def send_worker_command(worker_id: int, command: WorkerCommand):
    """Send command to worker"""
    # Verify worker exists
    async with db_pool.acquire() as conn:
        exists = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM workers WHERE id = $1 AND hive_id = 1)",
            worker_id,
        )
        if not exists:
            raise HTTPException(404, "Worker not found")

    await redis_client.send_command(worker_id, command.command)
    return {"status": "command_sent", "command": command.command}


@app.get("/market/prices", dependencies=[Depends(verify_api_key)])
async def get_market_prices():
    """Get current market prices"""
    async with db_pool.acquire() as conn:
        symbols_rows = await conn.fetch(
            "SELECT DISTINCT symbol FROM workers WHERE hive_id = 1"
        )
    symbols = [row["symbol"] for row in symbols_rows] or ["BTC/USDT", "ETH/USDT", "SOL/USDT"]

    prices = []
    for symbol in symbols:
        price_data = await redis_client.get_price(symbol)
        if price_data:
            prices.append(price_data)

    return prices


@app.get("/analytics/pnl", dependencies=[Depends(verify_api_key)])
async def get_pnl_analytics():
    """Get PnL analytics"""
    async with db_pool.acquire() as conn:
        by_strategy = await conn.fetch('''
            SELECT strategy_name, SUM(pnl) as total_pnl, COUNT(*) as worker_count
            FROM workers
            WHERE hive_id = 1
            GROUP BY strategy_name
        ''')

        recent_trades = await conn.fetch('''
            SELECT symbol, profit, created_at
            FROM worker_trades
            WHERE worker_id IN (SELECT id FROM workers WHERE hive_id = 1)
            ORDER BY created_at DESC
            LIMIT 20
        ''')

        return {
            "by_strategy": [
                {
                    "strategy": row["strategy_name"],
                    "total_pnl": float(row["total_pnl"]),
                    "worker_count": row["worker_count"],
                }
                for row in by_strategy
            ],
            "recent_trades": [
                {
                    "symbol": row["symbol"],
                    "profit": float(row["profit"]),
                    "timestamp": row["created_at"].isoformat(),
                }
                for row in recent_trades
            ],
        }


@app.get("/queen/decisions", dependencies=[Depends(verify_api_key)])
async def get_queen_decisions():
    """Get AI decision history"""
    async with db_pool.acquire() as conn:
        rows = await conn.fetch('''
            SELECT symbol, decision, confidence, reasoning, created_at
            FROM queen_decisions
            WHERE hive_id = 1
            ORDER BY created_at DESC
            LIMIT 50
        ''')

        return [
            {
                "symbol": row["symbol"],
                "decision": row["decision"],
                "confidence": float(row["confidence"]) if row["confidence"] else None,
                "reasoning": row["reasoning"],
                "timestamp": row["created_at"].isoformat(),
            }
            for row in rows
        ]


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time updates (requires API key as query param)"""
    # Auth check: expect ?api_key=xxx
    if API_KEY:
        ws_api_key = websocket.query_params.get("api_key", "")
        if ws_api_key != API_KEY:
            await websocket.close(code=4001, reason="Unauthorized")
            return

    await websocket.accept()

    try:
        while True:
            hive_status = await redis_client.get_hive_status(1)
            if hive_status:
                await websocket.send_json({
                    "type": "hive_status",
                    "data": hive_status,
                })

            await asyncio.sleep(2)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[WebSocket] Error: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
