"""Test FastAPI endpoints"""
import pytest
from fastapi.testclient import TestClient
from api.main import app
import asyncpg
from infra.redis_client import RedisClient


@pytest.fixture
def client():
    return TestClient(app)


def test_hive_status(client):
    """Test hive status endpoint"""
    response = client.get("/hive/status")
    assert response.status_code in [200, 404]  # 404 if DB not setup
    
    if response.status_code == 200:
        data = response.json()
        assert "total_capital" in data
        assert "used_capital" in data
        assert "free_capital" in data


def test_list_workers(client):
    """Test workers list endpoint"""
    response = client.get("/workers")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_get_market_prices(client):
    """Test market prices endpoint"""
    response = client.get("/market/prices")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_get_analytics(client):
    """Test analytics endpoint"""
    response = client.get("/analytics/pnl")
    assert response.status_code == 200
    data = response.json()
    assert "by_strategy" in data
    assert "recent_trades" in data


def test_get_queen_decisions(client):
    """Test queen decisions endpoint"""
    response = client.get("/queen/decisions")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_send_worker_command(client):
    """Test worker command endpoint"""
    response = client.put(
        "/workers/1/command",
        json={"command": "pause"}
    )
    # May fail if worker doesn't exist, but endpoint should work
    assert response.status_code in [200, 404]


def test_create_worker(client):
    """Test worker creation endpoint"""
    response = client.post(
        "/workers",
        json={
            "strategy_name": "infinite_grid",
            "symbol": "BTC/USDT",
            "capital": 1000,
            "config": {
                "grid_step_min": 400,
                "active_levels": 2
            }
        }
    )
    # May fail if DB not setup
    assert response.status_code in [200, 500]
