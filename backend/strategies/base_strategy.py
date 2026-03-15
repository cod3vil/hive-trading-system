"""Base strategy interface for all trading strategies"""
from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class StrategyStatus(str, Enum):
    INIT = "init"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


class StrategyConfig(BaseModel):
    """Base configuration for all strategies"""
    symbol: str
    capital: float = Field(gt=0)
    exchange: str = "binance"


class BaseStrategy(ABC):
    """Abstract base class for all trading strategies"""
    
    def __init__(self, worker_id: int, config: Any):
        self.worker_id = worker_id
        self.config = config
        self.status = StrategyStatus.INIT
        self.state: Dict[str, Any] = {}
    
    @abstractmethod
    async def start(self, initial_state: Optional[Dict[str, Any]] = None):
        """Initialize and start the strategy"""
        pass
    
    @abstractmethod
    async def on_price_update(self, price: float, timestamp: int):
        """Handle price update"""
        pass
    
    @abstractmethod
    async def on_order_filled(self, order: Dict[str, Any]):
        """Handle order fill event"""
        pass
    
    @abstractmethod
    async def reload_config(self, new_config: Any):
        """Reload configuration without restart"""
        pass
    
    @abstractmethod
    async def stop(self):
        """Stop the strategy and cleanup"""
        pass
    
    def get_state(self) -> Dict[str, Any]:
        """Get current strategy state"""
        return {
            "status": self.status.value,
            "state": self.state
        }
    
    def set_status(self, status: StrategyStatus):
        """Update strategy status"""
        self.status = status


class StrategyRegistry:
    """Registry for strategy plugins"""
    _strategies: Dict[str, type] = {}
    
    @classmethod
    def register(cls, name: str):
        """Decorator to register strategy"""
        def wrapper(strategy_class):
            cls._strategies[name] = strategy_class
            return strategy_class
        return wrapper
    
    @classmethod
    def get(cls, name: str) -> Optional[type]:
        """Get strategy class by name"""
        return cls._strategies.get(name)
    
    @classmethod
    def list(cls) -> list:
        """List all registered strategies"""
        return list(cls._strategies.keys())
