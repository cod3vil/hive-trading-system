"""Hive manager for orchestrating workers"""
import asyncio
from typing import Dict, Optional
import asyncpg
from core.worker import Worker
from infra.redis_client import RedisClient


class HiveManager:
    """Manages worker lifecycle and capital allocation"""

    def __init__(self, hive_id: int, db_pool: asyncpg.Pool, redis: RedisClient):
        self.hive_id = hive_id
        self.db_pool = db_pool
        self.redis = redis
        self.workers: Dict[int, Worker] = {}
        self.worker_tasks: Dict[int, asyncio.Task] = {}
        self.running = False
        self.config = {}

    async def load_config(self):
        """Load hive configuration"""
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM hives WHERE id = $1", self.hive_id
            )
            if not row:
                raise Exception(f"Hive {self.hive_id} not found")

            self.config = dict(row)
            return self.config

    async def start(self):
        """Start hive manager"""
        self.running = True
        await self.load_config()

        print(f"[Hive {self.hive_id}] Started: {self.config['name']}")
        print(f"[Hive {self.hive_id}] Capital: {self.config['total_capital']}, Max Workers: {self.config['max_workers']}")

        # Load existing workers
        await self._load_workers()

        # Start monitoring loop
        await self._monitor_loop()

    async def _load_workers(self):
        """Load and resume existing workers"""
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id FROM workers WHERE hive_id = $1 AND status IN ('running', 'paused')",
                self.hive_id,
            )

            for row in rows:
                worker_id = row["id"]
                await self.spawn_worker(worker_id)

    async def spawn_worker(self, worker_id: int) -> bool:
        """Spawn a worker (capital must already be reserved at creation time)"""
        if worker_id in self.workers:
            print(f"[Hive {self.hive_id}] Worker {worker_id} already running")
            return False

        if len(self.workers) >= self.config.get("max_workers", 10):
            print(f"[Hive {self.hive_id}] Max workers reached")
            return False

        # Verify worker exists
        async with self.db_pool.acquire() as conn:
            worker_row = await conn.fetchrow(
                "SELECT id FROM workers WHERE id = $1 AND hive_id = $2",
                worker_id, self.hive_id,
            )
            if not worker_row:
                return False

        # Create and start worker
        worker = Worker(worker_id, self.db_pool, self.redis)
        await worker.load_config()
        await worker.initialize_strategy()

        self.workers[worker_id] = worker
        task = asyncio.create_task(self._run_worker(worker_id, worker))
        self.worker_tasks[worker_id] = task

        await self.load_config()

        print(f"[Hive {self.hive_id}] Worker {worker_id} spawned")
        return True

    async def _run_worker(self, worker_id: int, worker: Worker):
        """Run worker and clean up on exit"""
        try:
            await worker.run()
        except Exception as e:
            print(f"[Hive {self.hive_id}] Worker {worker_id} crashed: {e}")
        finally:
            # Auto-cleanup when worker task finishes (crash or normal exit)
            if worker_id in self.workers:
                del self.workers[worker_id]
            if worker_id in self.worker_tasks:
                del self.worker_tasks[worker_id]
            await self._release_worker_capital(worker_id)

    async def _release_worker_capital(self, worker_id: int):
        """Release capital held by a worker"""
        async with self.db_pool.acquire() as conn:
            async with conn.transaction():
                worker_row = await conn.fetchrow(
                    "SELECT capital FROM workers WHERE id = $1", worker_id
                )
                if worker_row:
                    await conn.execute(
                        "UPDATE hives SET used_capital = GREATEST(used_capital - $1, 0) WHERE id = $2",
                        float(worker_row["capital"]),
                        self.hive_id,
                    )
        await self.load_config()

    async def stop_worker(self, worker_id: int):
        """Stop a worker"""
        if worker_id not in self.workers:
            return

        worker = self.workers[worker_id]
        await worker.shutdown()

        # Cancel task - cleanup happens in _run_worker finally block
        if worker_id in self.worker_tasks:
            self.worker_tasks[worker_id].cancel()

        print(f"[Hive {self.hive_id}] Worker {worker_id} stopped")

    async def _monitor_loop(self):
        """Monitor worker health"""
        while self.running:
            for worker_id in list(self.workers.keys()):
                is_alive = await self.redis.check_heartbeat(worker_id)
                if not is_alive:
                    print(f"[Hive {self.hive_id}] Worker {worker_id} heartbeat lost")
                    await self.stop_worker(worker_id)

            await self._update_hive_status()
            await asyncio.sleep(10)

    async def _update_hive_status(self):
        """Update hive status in Redis"""
        await self.load_config()
        await self.redis.set_hive_status(self.hive_id, {
            "hive_id": self.hive_id,
            "name": self.config["name"],
            "total_capital": float(self.config["total_capital"]),
            "used_capital": float(self.config["used_capital"]),
            "free_capital": float(self.config["total_capital"]) - float(self.config["used_capital"]),
            "workers_running": len(self.workers),
            "max_workers": self.config["max_workers"],
        })

    async def stop(self):
        """Stop hive manager"""
        self.running = False

        for worker_id in list(self.workers.keys()):
            await self.stop_worker(worker_id)

        print(f"[Hive {self.hive_id}] Stopped")
