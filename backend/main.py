"""Main entry point for Hive Trading System"""
import asyncio
import signal
import sys
from typing import Optional
from dotenv import load_dotenv
import os
import asyncpg
from infra.redis_client import RedisClient
from market.scanner import MarketScanner
from core.hive import HiveManager
from core.queen import QueenScheduler
from ai.decision_engine import AIDecisionEngine

# Load environment
load_dotenv()


class HiveTradingSystem:
    """Main system orchestrator"""
    
    def __init__(self):
        self.db_pool = None
        self.redis = None
        self.scanner = None
        self.hive = None
        self.queen = None
        self.running = False
    
    async def initialize(self):
        """Initialize all components"""
        print("[System] Initializing Hive Trading System...")
        
        # Database
        self.db_pool = await asyncpg.create_pool(
            host=os.getenv("POSTGRES_HOST", "127.0.0.1"),
            port=int(os.getenv("POSTGRES_PORT", 5432)),
            database=os.getenv("POSTGRES_DATABASE", "hive_trading_system"),
            user=os.getenv("POSTGRES_USER", "postgres"),
            password=os.getenv("POSTGRES_PASSWORD", ""),
            min_size=int(os.getenv("POSTGRES_MIN_CONNECTIONS", 2)),
            max_size=int(os.getenv("POSTGRES_MAX_CONNECTIONS", 10))
        )
        print("[System] Database connected")
        
        # Redis
        self.redis = RedisClient(
            host=os.getenv("REDIS_HOST", "127.0.0.1"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            db=int(os.getenv("REDIS_DB", 0)),
            password=os.getenv("REDIS_PASSWORD") or None
        )
        await self.redis.connect()
        
        # Ensure hive exists
        await self._ensure_hive()
        
        # Market Scanner
        symbols = os.getenv("SYMBOLS", "BTC/USDT,ETH/USDT,SOL/USDT").split(",")
        self.scanner = MarketScanner(
            exchange_name=os.getenv("EXCHANGE", "binance"),
            symbols=[s.strip() for s in symbols],
            redis=self.redis
        )
        
        # Hive Manager
        self.hive = HiveManager(
            hive_id=1,
            db_pool=self.db_pool,
            redis=self.redis
        )
        
        # AI Decision Engine
        ai_engine = AIDecisionEngine(
            lm_studio_url=os.getenv("LM_STUDIO_URL", "http://localhost:1234/v1"),
            model=os.getenv("LM_STUDIO_MODEL", "local-model"),
            api_key=os.getenv("LM_STUDIO_API_KEY", "lm-studio"),
            enabled=os.getenv("LM_STUDIO_ENABLED", "true").lower() == "true"
        )
        
        # Queen Scheduler
        self.queen = QueenScheduler(
            hive=self.hive,
            ai_engine=ai_engine,
            db_pool=self.db_pool,
            redis=self.redis,
            scan_interval=300  # 5 minutes
        )
        
        print("[System] All components initialized")
    
    async def _ensure_hive(self):
        """Ensure hive exists in database"""
        async with self.db_pool.acquire() as conn:
            exists = await conn.fetchval("SELECT EXISTS(SELECT 1 FROM hives WHERE id = 1)")
            if not exists:
                await conn.execute('''
                    INSERT INTO hives (id, name, exchange, total_capital, max_workers)
                    VALUES (1, $1, $2, $3, $4)
                ''',
                    os.getenv("HIVE_NAME", "Hive-Binance"),
                    os.getenv("EXCHANGE", "binance"),
                    float(os.getenv("HIVE_TOTAL_CAPITAL", 10000)),
                    int(os.getenv("HIVE_MAX_WORKERS", 10))
                )
                print("[System] Hive created in database")
    
    async def start(self):
        """Start all components"""
        self.running = True
        print("[System] Starting Hive Trading System...")
        
        # Start components
        tasks = [
            asyncio.create_task(self.scanner.start(), name="scanner"),
            asyncio.create_task(self.hive.start(), name="hive"),
            asyncio.create_task(self.queen.start(), name="queen")
        ]
        
        print("[System] All components started")
        print("[System] System is running. Press Ctrl+C to stop.")
        
        # Wait for all tasks
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def stop(self):
        """Stop all components"""
        print("\n[System] Shutting down...")
        self.running = False
        
        if self.queen:
            await self.queen.stop()
        if self.hive:
            await self.hive.stop()
        if self.scanner:
            await self.scanner.stop()
        if self.redis:
            await self.redis.close()
        if self.db_pool:
            await self.db_pool.close()
        
        print("[System] Shutdown complete")


async def main():
    """Main entry point"""
    system = HiveTradingSystem()
    shutdown_task: Optional[asyncio.Task] = None

    def signal_handler():
        nonlocal shutdown_task
        if system.running and shutdown_task is None:
            shutdown_task = asyncio.create_task(system.stop())

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)

    try:
        await system.initialize()
        await system.start()
    except Exception as e:
        print(f"[System] Fatal error: {e}")
        await system.stop()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
