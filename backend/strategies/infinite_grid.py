"""Infinite Grid Strategy - Refactored from grid.py"""
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
import numpy as np
from strategies.base_strategy import BaseStrategy, StrategyConfig, StrategyStatus, StrategyRegistry


class GridConfig(BaseModel):
    """Grid strategy configuration (strategy-specific params only)"""
    grid_step_min: float = Field(default=400, gt=0)
    grid_step_max: float = Field(default=1500, gt=0)
    grid_step_k: float = Field(default=1.2, gt=0)
    active_levels: int = Field(default=2, ge=1)
    order_size_usdt: float = Field(default=100, gt=0)
    atr_period: int = Field(default=14, ge=1)
    enable_adaptive: bool = True


class Indicators:
    """Technical indicators"""
    
    @staticmethod
    def calculate_atr(klines: List[List], period: int = 14) -> float:
        if len(klines) < period + 1:
            return 0.0
        highs = np.array([k[2] for k in klines])
        lows = np.array([k[3] for k in klines])
        closes = np.array([k[4] for k in klines])
        tr1 = highs[1:] - lows[1:]
        tr2 = np.abs(highs[1:] - closes[:-1])
        tr3 = np.abs(lows[1:] - closes[:-1])
        tr = np.maximum(tr1, np.maximum(tr2, tr3))
        return float(np.mean(tr[-period:]))


@StrategyRegistry.register("infinite_grid")
class InfiniteGridStrategy(BaseStrategy):
    """Infinite grid trading strategy"""
    
    config_class = GridConfig
    
    def __init__(self, worker_id: int, config: Dict[str, Any]):
        grid_config = GridConfig(**config)
        super().__init__(worker_id, grid_config)
        self.current_step = grid_config.grid_step_min
        self.grid_center = 0.0
        self.open_orders: Dict[str, Dict] = {}
        self.last_price = 0.0
        self.total_pnl = 0.0
        self.total_trades = 0
    
    async def start(self, initial_state: Optional[Dict[str, Any]] = None):
        """Initialize grid strategy"""
        self.set_status(StrategyStatus.RUNNING)
        
        if initial_state:
            self.state = initial_state
            self.current_step = initial_state.get("current_step", self.config.grid_step_min)
            self.grid_center = initial_state.get("grid_center", 0.0)
            self.total_pnl = initial_state.get("pnl", 0.0)
            self.total_trades = initial_state.get("total_trades", 0)
        
        print(f"[Grid {self.worker_id}] Started")
    
    async def on_price_update(self, price: float, timestamp: int):
        """Handle price update and manage grid"""
        if self.status != StrategyStatus.RUNNING:
            return
        
        self.last_price = price
        
        # Check if grid needs update
        if self._should_update_grid(price):
            await self._update_grid(price)
        
        # Update state
        self.state.update({
            "last_price": price,
            "current_step": self.current_step,
            "grid_center": self.grid_center,
            "open_orders_count": len(self.open_orders),
            "pnl": self.total_pnl,
            "total_trades": self.total_trades,
        })
    
    async def on_order_filled(self, order: Dict[str, Any]):
        """Handle order fill"""
        order_id = order["id"]
        if order_id in self.open_orders:
            del self.open_orders[order_id]
            self.total_trades += 1
            if "profit" in order:
                self.total_pnl += order["profit"]
            print(f"[Grid {self.worker_id}] Order filled: {order['side']} @ {order['price']}")
    
    async def reload_config(self, new_config: Dict[str, Any]):
        """Reload configuration"""
        self.config = GridConfig(**new_config)
        print(f"[Grid {self.worker_id}] Config reloaded")
    
    async def stop(self):
        """Stop strategy"""
        self.set_status(StrategyStatus.STOPPED)
        print(f"[Grid {self.worker_id}] Stopped")
    
    def _should_update_grid(self, price: float) -> bool:
        """Check if grid needs update"""
        if self.grid_center == 0:
            return True
        
        # Check if price moved outside grid range
        grid_range = self.current_step * self.config.active_levels
        upper = self.grid_center + grid_range
        lower = self.grid_center - grid_range
        
        return price > upper or price < lower
    
    async def _update_grid(self, price: float):
        """Update grid orders"""
        self.grid_center = price
        
        # Calculate grid step (simplified - would use ATR in full version)
        if self.config.enable_adaptive:
            # Placeholder for ATR calculation
            self.current_step = self.config.grid_step_min
        
        # Generate grid orders
        orders = self._generate_grid_orders(price)
        
        # In full version, would place orders via exchange
        self.open_orders = {f"order_{i}": order for i, order in enumerate(orders)}
        
        print(f"[Grid {self.worker_id}] Grid updated: center={price:.2f}, step={self.current_step:.2f}, orders={len(orders)}")
    
    def _generate_grid_orders(self, center_price: float) -> List[Dict]:
        """Generate grid orders"""
        orders = []
        
        # Buy orders below center
        for level in range(1, self.config.active_levels + 1):
            price = center_price - (self.current_step * level)
            orders.append({
                "side": "buy",
                "price": price,
                "amount": self.config.order_size_usdt / price,
                "level": level
            })
        
        # Sell orders above center
        for level in range(1, self.config.active_levels + 1):
            price = center_price + (self.current_step * level)
            orders.append({
                "side": "sell",
                "price": price,
                "amount": self.config.order_size_usdt / price,
                "level": level
            })
        
        return orders
