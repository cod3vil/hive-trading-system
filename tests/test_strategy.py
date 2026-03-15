"""Test strategy base class and registry"""
import pytest
from strategies.base_strategy import BaseStrategy, StrategyRegistry, StrategyStatus, StrategyConfig


class MockStrategy(BaseStrategy):
    """Mock strategy for testing"""
    
    async def start(self, initial_state=None):
        self.set_status(StrategyStatus.RUNNING)
        if initial_state:
            self.state = initial_state
    
    async def on_price_update(self, price, timestamp):
        self.state["last_price"] = price
    
    async def on_order_filled(self, order):
        self.state["orders_filled"] = self.state.get("orders_filled", 0) + 1
    
    async def reload_config(self, new_config):
        self.config = new_config
    
    async def stop(self):
        self.set_status(StrategyStatus.STOPPED)


@pytest.mark.asyncio
async def test_strategy_lifecycle():
    """Test strategy lifecycle transitions"""
    config = StrategyConfig(symbol="BTC/USDT", capital=1000)
    strategy = MockStrategy(worker_id=1, config=config)
    
    assert strategy.status == StrategyStatus.INIT
    
    await strategy.start()
    assert strategy.status == StrategyStatus.RUNNING
    
    await strategy.on_price_update(67000, 1234567890)
    assert strategy.state["last_price"] == 67000
    
    await strategy.on_order_filled({"id": "order1"})
    assert strategy.state["orders_filled"] == 1
    
    await strategy.stop()
    assert strategy.status == StrategyStatus.STOPPED


def test_strategy_registry():
    """Test strategy registration and retrieval"""
    
    @StrategyRegistry.register("test_strategy")
    class TestStrategy(BaseStrategy):
        pass
    
    assert "test_strategy" in StrategyRegistry.list()
    assert StrategyRegistry.get("test_strategy") == TestStrategy
    assert StrategyRegistry.get("nonexistent") is None
