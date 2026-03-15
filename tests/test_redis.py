"""Test Redis client functionality"""
import pytest
import asyncio
from infra.redis_client import RedisClient


@pytest.fixture
async def redis_client():
    client = RedisClient(host='127.0.0.1', port=6379, db=1)
    await client.connect()
    yield client
    await client.close()


@pytest.mark.asyncio
async def test_price_cache(redis_client):
    """Test price caching with TTL"""
    await redis_client.set_price("BTC/USDT", {
        "price": 67000,
        "bid": 66999,
        "ask": 67001,
        "timestamp": 1234567890
    }, ttl=1)
    
    price = await redis_client.get_price("BTC/USDT")
    assert price["price"] == 67000
    
    # Wait for TTL expiration
    await asyncio.sleep(2)
    price = await redis_client.get_price("BTC/USDT")
    assert price is None


@pytest.mark.asyncio
async def test_worker_commands(redis_client):
    """Test worker command queue"""
    await redis_client.send_command(1, "pause")
    command = await redis_client.get_command(1)
    assert command == "pause"
    
    # Command should be deleted after retrieval
    command = await redis_client.get_command(1)
    assert command is None


@pytest.mark.asyncio
async def test_heartbeat(redis_client):
    """Test worker heartbeat"""
    await redis_client.set_heartbeat(1)
    assert await redis_client.check_heartbeat(1) is True
    
    # Wait for heartbeat expiration
    await asyncio.sleep(11)
    assert await redis_client.check_heartbeat(1) is False
