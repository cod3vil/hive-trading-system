"""Worker engine for executing trading strategies"""
import asyncio
import time
from typing import Optional, Dict, Any
from datetime import datetime
import asyncpg
from strategies.base_strategy import BaseStrategy, StrategyStatus, StrategyRegistry
from infra.redis_client import RedisClient


class Worker:
    """Worker manages a single strategy instance"""

    # How often to sync state to database (seconds)
    DB_SYNC_INTERVAL = 10

    def __init__(self, worker_id: int, db_pool: asyncpg.Pool, redis: RedisClient):
        self.worker_id = worker_id
        self.db_pool = db_pool
        self.redis = redis
        self.strategy: Optional[BaseStrategy] = None
        self.running = False
        self.config: Dict[str, Any] = {}
        self.metrics = {
            "pnl": 0.0,
            "total_trades": 0,
            "uptime": 0,
        }
        self._last_db_sync = 0.0

    async def load_config(self):
        """Load worker configuration from database"""
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT strategy_name, symbol, capital, config, state, status, pnl, total_trades FROM workers WHERE id = $1",
                self.worker_id,
            )
            if not row:
                raise Exception(f"Worker {self.worker_id} not found")

            self.config = {
                "strategy_name": row["strategy_name"],
                "symbol": row["symbol"],
                "capital": float(row["capital"]),
                "config": row["config"],
                "state": row["state"],
                "status": row["status"],
            }
            # Restore persisted metrics
            self.metrics["pnl"] = float(row["pnl"]) if row["pnl"] else 0.0
            self.metrics["total_trades"] = row["total_trades"] or 0
            return self.config

    async def initialize_strategy(self):
        """Initialize strategy instance"""
        strategy_class = StrategyRegistry.get(self.config["strategy_name"])
        if not strategy_class:
            raise Exception(f"Strategy {self.config['strategy_name']} not found")

        self.strategy = strategy_class(self.worker_id, self.config["config"])
        await self.strategy.start(self.config.get("state"))

    async def run(self):
        """Main worker loop"""
        self.running = True
        start_time = datetime.now()

        await self._update_status("running")

        heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        try:
            while self.running:
                # Check for commands
                command = await self.redis.get_command(self.worker_id)
                if command:
                    await self._handle_command(command)

                # Get price from Redis cache
                price_data = await self.redis.get_price(self.config["symbol"])
                if price_data:
                    await self.strategy.on_price_update(
                        price_data["price"], price_data["timestamp"]
                    )

                # Sync PnL from strategy
                strategy_state = self.strategy.get_state()
                state_data = strategy_state.get("state", {})
                if "pnl" in state_data:
                    self.metrics["pnl"] = state_data["pnl"]
                if "total_trades" in state_data:
                    self.metrics["total_trades"] = state_data["total_trades"]

                # Update metrics
                self.metrics["uptime"] = (datetime.now() - start_time).total_seconds()
                await self._sync_state()

                await asyncio.sleep(1)

        except Exception as e:
            print(f"[Worker {self.worker_id}] Error: {e}")
            await self._update_status("error")

        finally:
            heartbeat_task.cancel()
            if self.strategy:
                await self.strategy.stop()
            self.running = False

    async def _handle_command(self, command: str):
        """Handle control commands"""
        if command == "pause":
            self.strategy.set_status(StrategyStatus.PAUSED)
            await self._update_status("paused")
        elif command == "resume":
            self.strategy.set_status(StrategyStatus.RUNNING)
            await self._update_status("running")
        elif command == "stop":
            self.running = False
            await self._update_status("stopped")
        elif command == "reload_config":
            await self.load_config()
            await self.strategy.reload_config(self.config["config"])

    async def _heartbeat_loop(self):
        """Send heartbeat every 3 seconds"""
        while self.running:
            await self.redis.set_heartbeat(self.worker_id)
            await asyncio.sleep(3)

    async def _sync_state(self):
        """Sync state to Redis (always) and database (throttled)"""
        state = self.strategy.get_state()

        # Always update Redis (lightweight)
        await self.redis.set_worker_status(self.worker_id, {
            "worker_id": self.worker_id,
            "symbol": self.config["symbol"],
            "strategy": self.config["strategy_name"],
            "capital": self.config["capital"],
            "pnl": self.metrics["pnl"],
            "total_trades": self.metrics["total_trades"],
            "status": state["status"],
            "uptime": self.metrics["uptime"],
        })

        # Throttle database writes
        now = time.monotonic()
        if now - self._last_db_sync < self.DB_SYNC_INTERVAL:
            return

        self._last_db_sync = now
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                "UPDATE workers SET state = $1, pnl = $2, total_trades = $3, updated_at = NOW() WHERE id = $4",
                state["state"],
                self.metrics["pnl"],
                self.metrics["total_trades"],
                self.worker_id,
            )

    async def _update_status(self, status: str):
        """Update worker status in database"""
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                "UPDATE workers SET status = $1, updated_at = NOW() WHERE id = $2",
                status,
                self.worker_id,
            )

    async def shutdown(self):
        """Graceful shutdown — signals the run loop to exit.
        Strategy cleanup happens in run()'s finally block."""
        self.running = False
        await self._update_status("stopped")
