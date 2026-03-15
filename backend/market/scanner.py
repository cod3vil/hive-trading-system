"""Market scanner for centralized data collection"""
import asyncio
from typing import Dict, List, Optional
import ccxt.pro as ccxtpro
from infra.redis_client import RedisClient
import time


class MarketScanner:
    """Centralized market data collection"""
    
    def __init__(self, exchange_name: str, symbols: List[str], redis: RedisClient):
        self.exchange_name = exchange_name
        self.symbols = symbols
        self.redis = redis
        self.exchange: Optional[ccxtpro.Exchange] = None
        self.running = False
        self.tickers: Dict[str, Dict] = {}
    
    async def start(self):
        """Start market data streaming"""
        self.running = True
        
        # Initialize exchange
        exchange_class = getattr(ccxtpro, self.exchange_name)
        self.exchange = exchange_class({
            'enableRateLimit': True,
        })
        
        print(f"[Scanner] Starting for {len(self.symbols)} symbols on {self.exchange_name}")
        
        # Start streaming tasks
        tasks = [
            asyncio.create_task(self._watch_ticker(symbol))
            for symbol in self.symbols
        ]
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _watch_ticker(self, symbol: str):
        """Watch ticker for a symbol"""
        retry_delay = 5
        
        while self.running:
            try:
                ticker = await self.exchange.watch_ticker(symbol)
                
                # Update local cache
                self.tickers[symbol] = ticker
                
                # Update Redis cache
                await self.redis.set_price(symbol, {
                    "symbol": symbol,
                    "price": ticker["last"],
                    "bid": ticker["bid"],
                    "ask": ticker["ask"],
                    "timestamp": int(time.time() * 1000)
                }, ttl=10)
                
                retry_delay = 5  # Reset on success
                
            except Exception as e:
                print(f"[Scanner] Error watching {symbol}: {e}")
                if self.running:
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, 60)
    
    async def stop(self):
        """Stop market scanner"""
        self.running = False
        if self.exchange:
            await self.exchange.close()
        print("[Scanner] Stopped")
    
    def get_price(self, symbol: str) -> Optional[float]:
        """Get current price from local cache"""
        ticker = self.tickers.get(symbol)
        return ticker["last"] if ticker else None
