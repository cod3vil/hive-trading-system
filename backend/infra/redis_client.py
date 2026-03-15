"""Redis client for shared state management"""
import asyncio
import json
from typing import Optional, Dict, Any
import redis.asyncio as redis
from datetime import timedelta


class RedisClient:
    def __init__(self, host: str = '127.0.0.1', port: int = 6379, db: int = 0, password: Optional[str] = None):
        self.host = host
        self.port = port
        self.db = db
        self.password = password
        self.client: Optional[redis.Redis] = None
        self.pubsub: Optional[redis.client.PubSub] = None
    
    async def connect(self):
        """Connect to Redis with retry logic"""
        for attempt in range(5):
            try:
                self.client = await redis.Redis(
                    host=self.host,
                    port=self.port,
                    db=self.db,
                    password=self.password,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_keepalive=True
                )
                await self.client.ping()
                print(f"[Redis] Connected to {self.host}:{self.port}")
                return
            except Exception as e:
                wait = 2 ** attempt
                print(f"[Redis] Connection failed (attempt {attempt+1}): {e}")
                if attempt < 4:
                    await asyncio.sleep(wait)
        raise Exception("Failed to connect to Redis")
    
    async def close(self):
        """Close Redis connection"""
        if self.client:
            await self.client.close()
            print("[Redis] Connection closed")
    
    # Market price cache
    async def set_price(self, symbol: str, data: Dict[str, Any], ttl: int = 10):
        """Cache market price with TTL"""
        key = f"market:price:{symbol}"
        await self.client.setex(key, ttl, json.dumps(data))
    
    async def get_price(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get cached market price"""
        key = f"market:price:{symbol}"
        data = await self.client.get(key)
        return json.loads(data) if data else None
    
    # Worker status
    async def set_worker_status(self, worker_id: int, status: Dict[str, Any]):
        """Update worker status"""
        key = f"worker:{worker_id}:status"
        await self.client.set(key, json.dumps(status))
    
    async def get_worker_status(self, worker_id: int) -> Optional[Dict[str, Any]]:
        """Get worker status"""
        key = f"worker:{worker_id}:status"
        data = await self.client.get(key)
        return json.loads(data) if data else None
    
    # Worker commands
    async def send_command(self, worker_id: int, command: str):
        """Send command to worker"""
        key = f"worker:{worker_id}:command"
        await self.client.setex(key, 60, command)
    
    async def get_command(self, worker_id: int) -> Optional[str]:
        """Get worker command and delete"""
        key = f"worker:{worker_id}:command"
        command = await self.client.get(key)
        if command:
            await self.client.delete(key)
        return command
    
    # Worker heartbeat
    async def set_heartbeat(self, worker_id: int):
        """Update worker heartbeat"""
        key = f"worker:{worker_id}:heartbeat"
        await self.client.setex(key, 10, "alive")
    
    async def check_heartbeat(self, worker_id: int) -> bool:
        """Check if worker is alive"""
        key = f"worker:{worker_id}:heartbeat"
        return await self.client.exists(key) > 0
    
    # Hive status
    async def set_hive_status(self, hive_id: int, status: Dict[str, Any]):
        """Update hive status"""
        key = f"hive:{hive_id}:status"
        await self.client.set(key, json.dumps(status))
    
    async def get_hive_status(self, hive_id: int) -> Optional[Dict[str, Any]]:
        """Get hive status"""
        key = f"hive:{hive_id}:status"
        data = await self.client.get(key)
        return json.loads(data) if data else None
    
    # Pub/Sub
    async def publish(self, channel: str, message: Dict[str, Any]):
        """Publish message to channel"""
        await self.client.publish(channel, json.dumps(message))
    
    async def subscribe(self, *channels: str):
        """Subscribe to channels"""
        self.pubsub = self.client.pubsub()
        await self.pubsub.subscribe(*channels)
        return self.pubsub
    
    async def listen(self):
        """Listen for messages"""
        if not self.pubsub:
            raise Exception("Not subscribed to any channel")
        async for message in self.pubsub.listen():
            if message['type'] == 'message':
                yield json.loads(message['data'])
