"""Queen scheduler for AI-driven worker dispatch"""
import asyncio
from typing import Dict, List, Optional
import asyncpg
from ai.decision_engine import AIDecisionEngine
from core.hive import HiveManager
from infra.redis_client import RedisClient
import time


class QueenScheduler:
    """Queen orchestrates worker deployment based on AI decisions"""

    def __init__(
        self,
        hive: HiveManager,
        ai_engine: AIDecisionEngine,
        db_pool: asyncpg.Pool,
        redis: RedisClient,
        scan_interval: int = 300,
    ):
        self.hive = hive
        self.ai_engine = ai_engine
        self.db_pool = db_pool
        self.redis = redis
        self.scan_interval = scan_interval
        self.running = False
        self.last_decision_time: Dict[str, float] = {}
        self.decision_cooldown = 600  # 10 minutes per symbol

    async def start(self):
        """Start Queen scheduler"""
        self.running = True
        print("[Queen] Started")

        await self._scheduling_loop()

    async def _scheduling_loop(self):
        """Main scheduling loop"""
        while self.running:
            try:
                await self._scan_market()
                await self._rebalance_workers()
            except Exception as e:
                print(f"[Queen] Error: {e}")

            await asyncio.sleep(self.scan_interval)

    async def _get_monitored_symbols(self) -> List[str]:
        """Get symbols from market_snapshots + active workers"""
        async with self.db_pool.acquire() as conn:
            # Symbols with active workers
            worker_rows = await conn.fetch(
                "SELECT DISTINCT symbol FROM workers WHERE hive_id = $1",
                self.hive.hive_id,
            )
            # Symbols with recent market data (scanner is writing to Redis, snapshots to DB)
            snapshot_rows = await conn.fetch(
                "SELECT DISTINCT symbol FROM market_snapshots"
            )
        worker_symbols = [row["symbol"] for row in worker_rows]
        snapshot_symbols = [row["symbol"] for row in snapshot_rows]
        all_symbols = list(set(worker_symbols + snapshot_symbols))
        return all_symbols or ["BTC/USDT", "ETH/USDT", "SOL/USDT"]

    async def _scan_market(self):
        """Scan market and make deployment decisions"""
        symbols = await self._get_monitored_symbols()

        for symbol in symbols:
            # Check cooldown
            if symbol in self.last_decision_time:
                if time.time() - self.last_decision_time[symbol] < self.decision_cooldown:
                    continue

            market_data = await self._get_market_data(symbol)
            if not market_data:
                continue

            decision = await self.ai_engine.should_deploy_worker(market_data)

            await self._log_decision(decision, market_data)

            if decision["decision"] == "deploy" and decision["confidence"] > 0.7:
                await self._deploy_worker(symbol, decision)

            self.last_decision_time[symbol] = time.time()

    async def _get_market_data(self, symbol: str) -> Optional[Dict]:
        """Get market data for decision making"""
        price_data = await self.redis.get_price(symbol)
        if not price_data:
            return None

        hive_status = await self.redis.get_hive_status(self.hive.hive_id)

        # Fetch real indicators from market snapshots
        indicators = await self._get_latest_indicators(symbol)

        return {
            "symbol": symbol,
            "price": price_data["price"],
            "timestamp": price_data["timestamp"],
            "available_capital": hive_status["free_capital"] if hive_status else 0,
            "rsi": indicators.get("rsi"),
            "atr": indicators.get("atr"),
            "trend": indicators.get("regime", "unknown"),
            "volume_24h": indicators.get("volume_24h"),
            "change_24h": indicators.get("change_24h"),
        }

    async def _get_latest_indicators(self, symbol: str) -> Dict:
        """Fetch latest indicator values from market_snapshots"""
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT atr, ma_fast, ma_slow, adx, regime
                FROM market_snapshots
                WHERE symbol = $1
                ORDER BY created_at DESC
                LIMIT 1
                """,
                symbol,
            )

        if not row:
            return {}

        result = {}
        if row["atr"] is not None:
            result["atr"] = float(row["atr"])
        if row["adx"] is not None:
            result["adx"] = float(row["adx"])
        if row["regime"]:
            result["regime"] = row["regime"]

        # Derive trend from moving averages
        if row["ma_fast"] is not None and row["ma_slow"] is not None:
            ma_fast = float(row["ma_fast"])
            ma_slow = float(row["ma_slow"])
            if ma_fast > ma_slow * 1.01:
                result["regime"] = result.get("regime", "uptrend")
            elif ma_fast < ma_slow * 0.99:
                result["regime"] = result.get("regime", "downtrend")
            else:
                result["regime"] = result.get("regime", "ranging")

        return result

    async def _deploy_worker(self, symbol: str, decision: Dict):
        """Deploy a new worker"""
        capital = 1000.0

        async with self.db_pool.acquire() as conn:
            async with conn.transaction():
                # Check capital availability
                hive = await conn.fetchrow(
                    "SELECT total_capital, used_capital, max_workers FROM hives WHERE id = $1 FOR UPDATE",
                    self.hive.hive_id,
                )
                if not hive:
                    return

                free = float(hive["total_capital"]) - float(hive["used_capital"])
                if capital > free:
                    print(f"[Queen] Insufficient capital for {symbol}: need {capital}, available {free:.2f}")
                    return

                worker_count = await conn.fetchval(
                    "SELECT COUNT(*) FROM workers WHERE hive_id = $1 AND status IN ('init', 'running', 'paused')",
                    self.hive.hive_id,
                )
                if worker_count >= hive["max_workers"]:
                    print(f"[Queen] Max workers reached, skipping {symbol}")
                    return

                worker_id = await conn.fetchval(
                    '''
                    INSERT INTO workers (hive_id, strategy_name, symbol, capital, status, config)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    RETURNING id
                ''',
                    self.hive.hive_id,
                    decision["strategy"],
                    symbol,
                    capital,
                    "init",
                    {
                        "grid_step_min": 400,
                        "grid_step_max": 1500,
                        "active_levels": 2,
                        "order_size_usdt": 100,
                    },
                )

                # Reserve capital atomically
                await conn.execute(
                    "UPDATE hives SET used_capital = used_capital + $1 WHERE id = $2",
                    capital,
                    self.hive.hive_id,
                )

        success = await self.hive.spawn_worker(worker_id)

        if success:
            print(f"[Queen] Deployed worker {worker_id} for {symbol} (confidence: {decision['confidence']:.2f})")
        else:
            print(f"[Queen] Failed to deploy worker for {symbol}")

    async def _rebalance_workers(self):
        """Check for profitable workers to close"""
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                '''
                SELECT id, symbol, pnl, capital
                FROM workers
                WHERE hive_id = $1 AND status = 'running'
            ''',
                self.hive.hive_id,
            )

            for row in rows:
                worker_id = row["id"]
                pnl = float(row["pnl"])
                capital = float(row["capital"])

                if capital > 0 and pnl / capital > 0.02:
                    print(f"[Queen] Closing profitable worker {worker_id}: PnL={pnl:.2f}")
                    await self.redis.send_command(worker_id, "stop")

    async def _log_decision(self, decision: Dict, market_data: Dict):
        """Log AI decision to database"""
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                '''
                INSERT INTO queen_decisions (hive_id, symbol, decision, confidence, strategy_name, reasoning, market_data)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
            ''',
                self.hive.hive_id,
                market_data["symbol"],
                decision["decision"],
                decision["confidence"],
                decision.get("strategy"),
                decision.get("reasoning"),
                market_data,
            )

    async def stop(self):
        """Stop Queen scheduler"""
        self.running = False
        print("[Queen] Stopped")
