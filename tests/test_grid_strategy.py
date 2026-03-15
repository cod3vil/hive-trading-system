"""Test infinite grid strategy"""
import pytest
from strategies.infinite_grid import InfiniteGridStrategy, GridConfig, Indicators
import numpy as np


@pytest.mark.asyncio
async def test_grid_initialization():
    """Test grid strategy initialization"""
    config = {
        "symbol": "BTC/USDT",
        "capital": 1000,
        "grid_step_min": 400,
        "grid_step_max": 1500,
        "active_levels": 2,
        "order_size_usdt": 100
    }
    
    strategy = InfiniteGridStrategy(worker_id=1, config=config)
    await strategy.start()
    
    assert strategy.status.value == "running"
    assert strategy.current_step == 400


@pytest.mark.asyncio
async def test_grid_update_on_price_move():
    """Test grid updates when price moves"""
    config = {
        "symbol": "BTC/USDT",
        "capital": 1000,
        "grid_step_min": 400,
        "active_levels": 2,
        "order_size_usdt": 100
    }
    
    strategy = InfiniteGridStrategy(worker_id=1, config=config)
    await strategy.start()
    
    # First price update - should create grid
    await strategy.on_price_update(67000, 1234567890)
    assert strategy.grid_center == 67000
    assert len(strategy.open_orders) > 0
    
    # Price moves outside grid range - should update
    await strategy.on_price_update(70000, 1234567891)
    assert strategy.grid_center == 70000


def test_atr_calculation():
    """Test ATR indicator calculation"""
    # Generate mock klines: [timestamp, open, high, low, close, volume]
    klines = []
    for i in range(20):
        klines.append([
            i * 60000,  # timestamp
            67000 + i * 10,  # open
            67100 + i * 10,  # high
            66900 + i * 10,  # low
            67000 + i * 10,  # close
            1000  # volume
        ])
    
    atr = Indicators.calculate_atr(klines, period=14)
    assert atr > 0
    assert isinstance(atr, float)


def test_grid_order_generation():
    """Test grid order generation"""
    config = {
        "symbol": "BTC/USDT",
        "capital": 1000,
        "grid_step_min": 400,
        "active_levels": 2,
        "order_size_usdt": 100
    }
    
    strategy = InfiniteGridStrategy(worker_id=1, config=config)
    orders = strategy._generate_grid_orders(67000)
    
    # Should have 2 buy + 2 sell orders
    assert len(orders) == 4
    
    buy_orders = [o for o in orders if o["side"] == "buy"]
    sell_orders = [o for o in orders if o["side"] == "sell"]
    
    assert len(buy_orders) == 2
    assert len(sell_orders) == 2
    
    # Buy orders should be below center
    assert all(o["price"] < 67000 for o in buy_orders)
    # Sell orders should be above center
    assert all(o["price"] > 67000 for o in sell_orders)
