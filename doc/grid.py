#!/usr/bin/env python3
"""
Hive 自适应网格交易系统 - 生产级网格交易机器人
币安 BTC/USDT 现货交易，基于波动率的自适应网格
"""

import asyncio
import argparse
import os
import sys
import signal
import time
import hmac
import hashlib
import json
import threading
import queue
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple, Any
from decimal import Decimal
from dataclasses import dataclass
from enum import Enum

import ccxt.async_support as ccxt
import ccxt.pro as ccxtpro
import asyncpg
import numpy as np
import aiohttp
import base64
from dotenv import load_dotenv


# ============================================================================
# 配置
# ============================================================================

class MarketRegime(Enum):
    RANGE = "震荡"
    BULL = "牛市"
    BEAR = "熊市"

class TradingSignal(Enum):
    ALLOW_BOTH = "允许交易"
    STOP_BUY = "停止买入"
    STOP_SELL = "停止卖出"

@dataclass
class Config:
    # Exchange
    exchange: str
    api_key: str
    api_secret: str
    api_passphrase: str
    symbol: str
    market_type: str
    
    # Trading
    base_position_ratio: float
    grid_order_size_usdt: float
    grid_active_levels: int
    max_open_orders: int
    
    # Fees
    spot_maker_fee: float
    spot_taker_fee: float
    
    # Adaptive Grid
    enable_adaptive_grid: bool
    atr_period: int
    atr_timeframe: str
    atr_ema_alpha: float  # EMA 平滑系数 (0-1), 越小越平滑
    grid_step_k: float
    grid_step_min: float
    grid_step_max: float
    grid_update_interval: int
    step_change_threshold: float
    
    # Infinity Grid
    auto_shift_grid: bool
    shift_trigger_percent: float
    
    # 状态 Detection
    enable_regime_detection: bool
    ma_fast: int
    ma_slow: int
    adx_period: int
    adx_range_threshold: float
    adx_bear_threshold: float
    
    # Bear Protection
    enable_bear_protection: bool
    bear_adx_recovery: float
    
    # Inventory Control
    btc_inventory_min: float
    btc_inventory_max: float
    max_btc_ratio: float
    
    # Risk
    max_drawdown_percent: float
    api_retry_limit: int
    
    # Database
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str
    db_min_conn: int
    db_max_conn: int
    
    # Feishu
    enable_feishu: bool
    feishu_webhook: str
    feishu_secret: str
    
    # Runtime
    worker_loop_seconds: int
    log_level: str
    enable_order_log: bool
    
    # CLI overrides
    max_position: Optional[float] = None
    base_position_price: Optional[float] = None


def load_config(config_file: Optional[str] = None, exchange: str = 'binance') -> Config:
    """从 .env 文件和环境变量加载配置"""
    if config_file and os.path.exists(config_file):
        load_dotenv(config_file)
    else:
        load_dotenv()

    def get_env(key: str, default: Any = None, cast=str) -> Any:
        val = os.getenv(key, default)
        if val is None:
            return None
        if cast == bool:
            if isinstance(val, bool):
                return val
            return str(val).lower() in ('true', '1', 'yes')
        return cast(val)

    # 根据交易所选择对应的 API 凭证
    if exchange == 'okx':
        api_key = get_env('OKX_API_KEY', '')
        api_secret = get_env('OKX_API_SECRET', '')
        api_passphrase = get_env('OKX_PASSPHRASE', '')
    else:
        api_key = get_env('BINANCE_API_KEY', '')
        api_secret = get_env('BINANCE_API_SECRET', '')
        api_passphrase = ''

    return Config(
        exchange=exchange,
        api_key=api_key,
        api_secret=api_secret,
        api_passphrase=api_passphrase,
        symbol=get_env('SYMBOL', 'BTC/USDT'),
        market_type=get_env('MARKET_TYPE', 'spot'),
        base_position_ratio=get_env('BASE_POSITION_RATIO', 0.30, float),
        grid_order_size_usdt=get_env('GRID_ORDER_SIZE_USDT', 100, float),
        grid_active_levels=get_env('GRID_ACTIVE_LEVELS', 2, int),
        max_open_orders=get_env('MAX_OPEN_ORDERS', 8, int),
        spot_maker_fee=get_env('SPOT_MAKER_FEE', 0.001, float),
        spot_taker_fee=get_env('SPOT_TAKER_FEE', 0.001, float),
        enable_adaptive_grid=get_env('ENABLE_ADAPTIVE_GRID', True, bool),
        atr_period=get_env('ATR_PERIOD', 20, int),
        atr_timeframe=get_env('ATR_TIMEFRAME', '5m'),
        atr_ema_alpha=get_env('ATR_EMA_ALPHA', 0.3, float),
        grid_step_k=get_env('GRID_STEP_K', 1.2, float),
        grid_step_min=get_env('GRID_STEP_MIN', 400, float),
        grid_step_max=get_env('GRID_STEP_MAX', 1500, float),
        grid_update_interval=get_env('GRID_UPDATE_INTERVAL_SECONDS', 60, int),
        step_change_threshold=get_env('STEP_CHANGE_THRESHOLD', 0.20, float),
        auto_shift_grid=get_env('AUTO_SHIFT_GRID', True, bool),
        shift_trigger_percent=get_env('SHIFT_TRIGGER_PERCENT', 1.2, float),
        enable_regime_detection=get_env('ENABLE_REGIME_DETECTION', True, bool),
        ma_fast=get_env('MA_FAST', 20, int),
        ma_slow=get_env('MA_SLOW', 60, int),
        adx_period=get_env('ADX_PERIOD', 14, int),
        adx_range_threshold=get_env('ADX_RANGE_THRESHOLD', 20, float),
        adx_bear_threshold=get_env('ADX_BEAR_THRESHOLD', 25, float),
        enable_bear_protection=get_env('ENABLE_BEAR_PROTECTION', True, bool),
        bear_adx_recovery=get_env('BEAR_ADX_RECOVERY', 20, float),
        btc_inventory_min=get_env('BTC_INVENTORY_MIN', 0.20, float),
        btc_inventory_max=get_env('BTC_INVENTORY_MAX', 0.70, float),
        max_btc_ratio=get_env('MAX_BTC_RATIO', 0.70, float),
        max_drawdown_percent=get_env('MAX_DRAWDOWN_PERCENT', 20, float),
        api_retry_limit=get_env('API_RETRY_LIMIT', 3, int),
        db_host=get_env('POSTGRES_HOST', '127.0.0.1'),
        db_port=get_env('POSTGRES_PORT', 5432, int),
        db_name=get_env('POSTGRES_DATABASE', 'hive_grid_system'),
        db_user=get_env('POSTGRES_USER', 'postgres'),
        db_password=get_env('POSTGRES_PASSWORD', ''),
        db_min_conn=get_env('POSTGRES_MIN_CONNECTIONS', 2, int),
        db_max_conn=get_env('POSTGRES_MAX_CONNECTIONS', 10, int),
        enable_feishu=get_env('ENABLE_FEISHU_NOTIFY', True, bool),
        feishu_webhook=get_env('FEISHU_WEBHOOK_URL', ''),
        feishu_secret=get_env('FEISHU_WEBHOOK_SECRET', ''),
        worker_loop_seconds=get_env('WORKER_LOOP_SECONDS', 1, int),
        log_level=get_env('LOG_LEVEL', 'INFO'),
        enable_order_log=get_env('ENABLE_ORDER_LOG', True, bool),
    )


def parse_args() -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='Hive 自适应网格交易机器人')
    parser.add_argument('--max-position', type=float, required=True, help='最大 USDT 仓位')
    parser.add_argument('--base-position-price', type=float, help='底仓建仓价格（在此价格挂限价买单）')
    parser.add_argument('--exchange', type=str, default='binance', choices=['binance', 'okx'], help='交易所 (默认: binance)')
    parser.add_argument('--config', type=str, help='配置文件路径 (.env)')
    return parser.parse_args()


# ============================================================================
# 日志
# ============================================================================

_log_queue: queue.Queue = queue.Queue()


def _log_writer_thread():
    """后台线程：从队列消费日志并写入文件，避免阻塞事件循环"""
    while True:
        msg = _log_queue.get()
        if msg is None:  # 关闭哨兵
            break
        try:
            now = datetime.now()
            log_dir = os.path.join('logs', str(now.year), f'{now.month:02d}', f'{now.day:02d}')
            os.makedirs(log_dir, exist_ok=True)
            log_file = os.path.join(log_dir, 'grid.log')
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(msg + '\n')
        except Exception as e:
            print(f"[ERROR] 写入日志文件失败: {e}")


_log_thread = threading.Thread(target=_log_writer_thread, daemon=True)
_log_thread.start()


def log(level: str, message: str, **kwargs):
    """日志函数：控制台同步输出，文件写入交给后台线程"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    extra = ' '.join(f'{k}={v}' for k, v in kwargs.items()) if kwargs else ''
    log_message = f"[{timestamp}] [{level}] {message} {extra}"
    print(log_message)
    _log_queue.put_nowait(log_message)


# ============================================================================
# 数据库层
# ============================================================================

class Database:
    """PostgreSQL 数据库连接和操作"""
    
    def __init__(self, config: Config):
        self.config = config
        self.pool: Optional[asyncpg.Pool] = None
    
    async def connect(self):
        """初始化数据库连接池，带重试逻辑"""
        for attempt in range(self.config.api_retry_limit):
            try:
                self.pool = await asyncpg.create_pool(
                    host=self.config.db_host,
                    port=self.config.db_port,
                    database=self.config.db_name,
                    user=self.config.db_user,
                    password=self.config.db_password,
                    min_size=self.config.db_min_conn,
                    max_size=self.config.db_max_conn,
                )
                log('INFO', '数据库已连接')
                return
            except Exception as e:
                wait = 2 ** attempt
                log('ERROR', f'数据库连接失败 (尝试 {attempt+1}): {e}')
                if attempt < self.config.api_retry_limit - 1:
                    await asyncio.sleep(wait)
        raise Exception('无法连接到数据库')
    
    async def close(self):
        """关闭数据库连接池"""
        if self.pool:
            await self.pool.close()
            log('INFO', '数据库已关闭')
    
    async def save_order(self, order: Dict):
        """保存或更新订单到数据库"""
        async with self.pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO grid_orders (order_id, symbol, side, price, amount, filled, status, grid_level, is_base_position)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (order_id) DO UPDATE SET
                    filled = EXCLUDED.filled,
                    status = EXCLUDED.status,
                    updated_at = NOW()
            ''', order['id'], order['symbol'], order['side'], float(order['price']), 
                 float(order['amount']), float(order.get('filled', 0)), order['status'],
                 order.get('grid_level'), order.get('is_base_position', False))
    
    async def load_open_orders(self, symbol: str) -> List[Dict]:
        """从数据库加载未完成订单"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM grid_orders WHERE symbol = $1 AND status IN ('open', 'partial') ORDER BY created_at",
                symbol
            )
            return [dict(row) for row in rows]
    
    async def update_order_status(self, order_id: str, status: str, filled: float):
        """更新订单状态"""
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE grid_orders SET status = $1, filled = $2, updated_at = NOW() WHERE order_id = $3",
                status, filled, order_id
            )
    
    async def save_trade(self, trade: Dict):
        """保存完成的交易"""
        async with self.pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO grid_trades (symbol, buy_order_id, sell_order_id, buy_price, sell_price, amount, profit, fee_total)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ''', trade['symbol'], trade['buy_order_id'], trade['sell_order_id'],
                 float(trade['buy_price']), float(trade['sell_price']), float(trade['amount']),
                 float(trade['profit']), float(trade['fee_total']))
    
    async def save_grid_state(self, state: Dict):
        """保存网格状态"""
        async with self.pool.acquire() as conn:
            await conn.execute('''
                UPDATE grid_state SET
                    symbol = $1, current_step = $2, range_high = $3, range_low = $4,
                    base_position_btc = $5, base_position_cost = $6, total_profit = $7,
                    peak_portfolio_value = $8, active_levels = $9, order_size_usdt = $10,
                    last_atr = $11, last_ma_fast = $12, last_ma_slow = $13, last_adx = $14,
                    circuit_breaker_open = $15, circuit_breaker_failures = $16, updated_at = NOW()
                WHERE id = 1
            ''', state['symbol'], state.get('current_step'), state.get('range_high'), state.get('range_low'),
                 state.get('base_position_btc', 0), state.get('base_position_cost', 0), state.get('total_profit', 0),
                 state.get('peak_portfolio_value', 0), state.get('active_levels', 2), state.get('order_size_usdt', 100),
                 state.get('last_atr'), state.get('last_ma_fast'), state.get('last_ma_slow'), state.get('last_adx'),
                 state.get('circuit_breaker_open', False), state.get('circuit_breaker_failures', 0))
    
    async def load_grid_state(self, symbol: str) -> Dict:
        """加载网格状态"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM grid_state WHERE id = 1")
            return dict(row) if row else {'symbol': symbol}
    
    async def save_regime(self, regime: str, indicators: Dict):
        """保存市场状态变化"""
        async with self.pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO market_regime (symbol, regime, atr, ma_fast, ma_slow, adx)
                VALUES ($1, $2, $3, $4, $5, $6)
            ''', indicators['symbol'], regime, indicators.get('atr'), 
                 indicators.get('ma_fast'), indicators.get('ma_slow'), indicators.get('adx'))
    
    async def add_inventory_lot(self, symbol: str, buy_order_id: str, buy_price: float, amount: float):
        """FIFO: 添加一个买入批次"""
        async with self.pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO inventory_lots (symbol, buy_order_id, buy_price, original_amount, remaining_amount)
                VALUES ($1, $2, $3, $4, $5)
            ''', symbol, buy_order_id, buy_price, amount, amount)

    async def consume_inventory_fifo(self, symbol: str, sell_amount: float) -> List[Dict]:
        """FIFO: 在单个事务中消耗库存，防止中途崩溃导致部分扣减"""
        matched = []
        remaining = sell_amount
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                rows = await conn.fetch('''
                    SELECT id, buy_order_id, buy_price, remaining_amount FROM inventory_lots
                    WHERE symbol = $1 AND remaining_amount > 0
                    ORDER BY created_at ASC
                    FOR UPDATE
                ''', symbol)
                for row in rows:
                    if remaining <= 0:
                        break
                    take = min(float(row['remaining_amount']), remaining)
                    await conn.execute(
                        'UPDATE inventory_lots SET remaining_amount = remaining_amount - $1 WHERE id = $2',
                        take, row['id']
                    )
                    matched.append({
                        'buy_order_id': row['buy_order_id'],
                        'buy_price': float(row['buy_price']),
                        'amount': take,
                    })
                    remaining -= take
        return matched

    async def get_last_regime(self, symbol: str) -> Optional[str]:
        """获取最后的市场状态"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT regime FROM market_regime WHERE symbol = $1 ORDER BY created_at DESC LIMIT 1",
                symbol
            )
            return row['regime'] if row else None


# ============================================================================
# 飞书通知
# ============================================================================

class FeishuNotifier:
    """飞书 Webhook 通知客户端，带限流"""
    
    def __init__(self, config: Config):
        self.config = config
        self.last_notify: Dict[str, float] = {}
        self.throttle_seconds = 60
    
    async def send(self, event_type: str, title: str, content: str):
        """发送飞书通知，带限流"""
        if not self.config.enable_feishu or not self.config.feishu_webhook:
            return
        
        # 限流
        now = time.time()
        if event_type in self.last_notify:
            if now - self.last_notify[event_type] < self.throttle_seconds:
                return
        self.last_notify[event_type] = now
        
        try:
            timestamp = str(int(now))
            
            # 将内容按行分割
            lines = content.split('\n')
            elements = [[{"tag": "text", "text": line}] for line in lines]
            
            msg = {
                "msg_type": "post",
                "content": {
                    "post": {
                        "zh_cn": {
                            "title": title,
                            "content": elements
                        }
                    }
                }
            }
            
            # 如果提供了密钥，添加签名
            if self.config.feishu_secret:
                sign = self._gen_sign(timestamp)
                msg['timestamp'] = timestamp
                msg['sign'] = sign
            
            async with aiohttp.ClientSession() as session:
                async with session.post(self.config.feishu_webhook, json=msg, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    body = await resp.json()
                    if body.get('code') != 0:
                        log('WARN', f'飞书通知失败: {body}')
        except Exception as e:
            log('ERROR', f'飞书通知错误: {e}')
    
    def _gen_sign(self, timestamp: str) -> str:
        """生成飞书 Webhook 签名（飞书文档: key=空串, msg=timestamp\\nsecret）"""
        string_to_sign = f'{timestamp}\n{self.config.feishu_secret}'
        hmac_code = hmac.new(
            self.config.feishu_secret.encode('utf-8'),
            string_to_sign.encode('utf-8'),
            digestmod=hashlib.sha256
        ).digest()
        return base64.b64encode(hmac_code).decode('utf-8')



# ============================================================================
# 技术指标
# ============================================================================

class Indicators:
    """技术指标计算"""

    _smoothed_atr: float = 0.0  # 类级别 EMA 平滑 ATR

    @classmethod
    def calculate_atr_smoothed(cls, klines: List[List], period: int = 20, alpha: float = 0.3) -> float:
        """计算 EMA 平滑的 ATR，减少噪声导致的网格频繁重建"""
        raw_atr = cls.calculate_atr(klines, period)
        if raw_atr == 0:
            return cls._smoothed_atr
        if cls._smoothed_atr == 0:
            cls._smoothed_atr = raw_atr
        else:
            cls._smoothed_atr = alpha * raw_atr + (1 - alpha) * cls._smoothed_atr
        return cls._smoothed_atr

    @staticmethod
    def calculate_atr(klines: List[List], period: int = 14) -> float:
        """计算平均真实波幅 (ATR)"""
        if len(klines) < period + 1:
            return 0.0
        
        highs = np.array([k[2] for k in klines])
        lows = np.array([k[3] for k in klines])
        closes = np.array([k[4] for k in klines])
        
        tr1 = highs[1:] - lows[1:]
        tr2 = np.abs(highs[1:] - closes[:-1])
        tr3 = np.abs(lows[1:] - closes[:-1])
        tr = np.maximum(tr1, np.maximum(tr2, tr3))
        
        atr = np.mean(tr[-period:])
        return float(atr)
    
    @staticmethod
    def calculate_ma(klines: List[List], period: int) -> float:
        """计算移动平均线 (MA)"""
        if len(klines) < period:
            return 0.0
        closes = [k[4] for k in klines[-period:]]
        return float(np.mean(closes))
    
    @staticmethod
    def calculate_adx(klines: List[List], period: int = 14) -> float:
        """计算平均趋向指数 (ADX)"""
        if len(klines) < period * 2:
            return 0.0
        
        highs = np.array([k[2] for k in klines])
        lows = np.array([k[3] for k in klines])
        closes = np.array([k[4] for k in klines])
        
        # 计算 +DM 和 -DM
        high_diff = np.diff(highs)
        low_diff = -np.diff(lows)
        
        plus_dm = np.where((high_diff > low_diff) & (high_diff > 0), high_diff, 0)
        minus_dm = np.where((low_diff > high_diff) & (low_diff > 0), low_diff, 0)
        
        # 计算 TR
        tr1 = highs[1:] - lows[1:]
        tr2 = np.abs(highs[1:] - closes[:-1])
        tr3 = np.abs(lows[1:] - closes[:-1])
        tr = np.maximum(tr1, np.maximum(tr2, tr3))
        
        # 平滑 TR, +DM, -DM
        atr_smooth = np.zeros(len(tr))
        plus_dm_smooth = np.zeros(len(plus_dm))
        minus_dm_smooth = np.zeros(len(minus_dm))
        
        atr_smooth[period-1] = np.mean(tr[:period])
        plus_dm_smooth[period-1] = np.mean(plus_dm[:period])
        minus_dm_smooth[period-1] = np.mean(minus_dm[:period])
        
        for i in range(period, len(tr)):
            atr_smooth[i] = (atr_smooth[i-1] * (period - 1) + tr[i]) / period
            plus_dm_smooth[i] = (plus_dm_smooth[i-1] * (period - 1) + plus_dm[i]) / period
            minus_dm_smooth[i] = (minus_dm_smooth[i-1] * (period - 1) + minus_dm[i]) / period
        
        # 计算 +DI 和 -DI
        plus_di = 100 * plus_dm_smooth / (atr_smooth + 1e-10)
        minus_di = 100 * minus_dm_smooth / (atr_smooth + 1e-10)
        
        # 计算 DX
        dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
        
        # 计算 ADX (DX 的 EMA)
        adx = np.mean(dx[-period:])
        return float(adx)


# ============================================================================
# 市场状态检测器
# ============================================================================

class RegimeDetector:
    """检测市场状态：震荡、牛市、熊市"""
    
    def __init__(self, config: Config):
        self.config = config
        self.current_regime = MarketRegime.RANGE
        self.regime_change_count = 0
    
    def detect(self, ma_fast: float, ma_slow: float, adx: float) -> MarketRegime:
        """检测市场状态，带滞后"""
        new_regime = self.current_regime
        
        if adx < self.config.adx_range_threshold:
            new_regime = MarketRegime.RANGE
        elif ma_fast > ma_slow and adx > self.config.adx_range_threshold:
            new_regime = MarketRegime.BULL
        elif ma_fast < ma_slow and adx > self.config.adx_bear_threshold:
            new_regime = MarketRegime.BEAR
        
        # 滞后：需要3次连续确认
        if new_regime != self.current_regime:
            self.regime_change_count += 1
            if self.regime_change_count >= 3:
                self.current_regime = new_regime
                self.regime_change_count = 0
                return new_regime
        else:
            self.regime_change_count = 0
        
        return self.current_regime


# ============================================================================
# 库存风险管理器
# ============================================================================

class InventoryManager:
    """管理 BTC 库存风险 - 渐进式控制"""

    def __init__(self, config: Config):
        self.config = config

    def check_inventory(self, btc_balance: float, usdt_balance: float, btc_price: float) -> TradingSignal:
        """检查库存并返回交易信号（保留用于硬限制）"""
        btc_value = btc_balance * btc_price
        total_value = btc_value + usdt_balance

        if total_value == 0:
            return TradingSignal.ALLOW_BOTH

        btc_ratio = btc_value / total_value

        # 硬限制仍然保留在极端情况
        if btc_ratio > self.config.btc_inventory_max + 0.1:  # 超过上限10%才硬停
            return TradingSignal.STOP_BUY
        elif btc_ratio < self.config.btc_inventory_min - 0.1:
            return TradingSignal.STOP_SELL

        return TradingSignal.ALLOW_BOTH

    def get_level_adjustment(self, btc_balance: float, usdt_balance: float, btc_price: float) -> Tuple[int, int]:
        """渐进式库存控制：返回 (buy_level_reduction, sell_level_reduction)"""
        btc_value = btc_balance * btc_price
        total_value = btc_value + usdt_balance

        if total_value == 0:
            return (0, 0)

        btc_ratio = btc_value / total_value
        buy_reduce = 0
        sell_reduce = 0

        # BTC 偏多 → 逐步减少买入层数
        if btc_ratio > 0.6:
            buy_reduce += 1
        if btc_ratio > 0.7:
            buy_reduce += 1

        # BTC 偏少 → 逐步减少卖出层数
        if btc_ratio < 0.3:
            sell_reduce += 1
        if btc_ratio < 0.2:
            sell_reduce += 1

        return (buy_reduce, sell_reduce)


# ============================================================================
# ADAPTIVE GRID ENGINE
# ============================================================================

class GridEngine:
    """Adaptive grid calculation and order generation"""
    
    def __init__(self, config: Config):
        self.config = config
        self.current_step = config.grid_step_min
    
    def calculate_step(self, atr: float) -> float:
        """Calculate grid step from ATR"""
        if not self.config.enable_adaptive_grid or atr == 0:
            return self.config.grid_step_min
        
        step = atr * self.config.grid_step_k
        step = max(self.config.grid_step_min, min(step, self.config.grid_step_max))
        return step
    
    def should_update_grid(self, new_step: float) -> bool:
        """Check if grid should be updated based on step change"""
        if self.current_step == 0:
            return True
        change_ratio = abs(new_step - self.current_step) / self.current_step
        return change_ratio > self.config.step_change_threshold
    
    def generate_orders(
        self,
        current_price: float,
        step: float,
        regime: MarketRegime,
        inventory_signal: TradingSignal,
        active_levels: int,
        inventory_adjustment: Tuple[int, int] = (0, 0),
        max_buy_levels: Optional[int] = None,
        max_sell_levels: Optional[int] = None
    ) -> List[Dict]:
        """Generate grid orders based on market conditions"""
        orders = []

        # Adjust levels based on regime (渐进式，不完全停止)
        buy_levels = active_levels
        sell_levels = active_levels

        if regime == MarketRegime.BULL:
            buy_levels = max(1, active_levels - 1)
            sell_levels = max(1, active_levels - 1)  # 防止卖光BTC
        elif regime == MarketRegime.BEAR:
            buy_levels = max(1, active_levels - 1)

        # 渐进式库存控制
        buy_reduce, sell_reduce = inventory_adjustment
        buy_levels = max(1, buy_levels - buy_reduce)
        sell_levels = max(1, sell_levels - sell_reduce)

        # 余额硬上限（买受 USDT 限制，卖受 BTC 限制，互不影响）
        if max_buy_levels is not None:
            buy_levels = min(buy_levels, max_buy_levels)
        if max_sell_levels is not None:
            sell_levels = min(sell_levels, max_sell_levels)

        # 库存极端硬限制
        if inventory_signal == TradingSignal.STOP_BUY:
            buy_levels = 0
        elif inventory_signal == TradingSignal.STOP_SELL:
            sell_levels = 0
        
        # Generate buy orders
        for level in range(1, buy_levels + 1):
            price = current_price - (step * level)
            orders.append({
                'side': 'buy',
                'price': price,
                'level': level
            })
        
        # Generate sell orders
        for level in range(1, sell_levels + 1):
            price = current_price + (step * level)
            orders.append({
                'side': 'sell',
                'price': price,
                'level': level
            })
        
        return orders
    
    def calculate_order_size(self, base_size: float, atr: float, price: float) -> float:
        """Calculate order size with volatility adjustment"""
        if atr == 0 or price == 0:
            return base_size
        
        volatility_factor = atr / price
        adjusted_size = base_size * (1 + volatility_factor * 10)  # Scale factor
        return min(adjusted_size, base_size * 1.5)  # Cap at 1.5x



# ============================================================================
# EXCHANGE CLIENT WITH ORDER MANAGEMENT
# ============================================================================

class ExchangeClient:
    """交易所客户端，带订单管理和熔断器"""
    
    def __init__(self, config: Config):
        self.config = config
        self.exchange: Optional[ccxt.Exchange] = None
        self.exchange_ws: Optional[ccxtpro.Exchange] = None  # WebSocket 连接
        self.circuit_breaker_open = False
        self.circuit_breaker_until = 0.0  # 冷却截止时间戳
        self.circuit_breaker_cooldown = 60  # 冷却秒数，每次触发翻倍
        self.failure_count = 0
        self.max_failures = 5
    
    async def initialize(self):
        """初始化交易所连接，带重试"""
        max_retries = 5
        retry_delay = 5
        
        for attempt in range(max_retries):
            try:
                # REST API 连接
                exchange_class = getattr(ccxt, self.config.exchange)
                exchange_opts = {
                    'apiKey': self.config.api_key,
                    'secret': self.config.api_secret,
                    'enableRateLimit': True,
                }
                if self.config.api_passphrase:
                    exchange_opts['password'] = self.config.api_passphrase
                self.exchange = exchange_class(exchange_opts)
                
                log('INFO', f'正在加载市场数据... (尝试 {attempt + 1}/{max_retries})')
                await self.exchange.load_markets()
                
                # WebSocket 连接（需要 API 密钥用于 watch_orders 等私有流）
                exchange_ws_class = getattr(ccxtpro, self.config.exchange)
                ws_opts = {
                    'apiKey': self.config.api_key,
                    'secret': self.config.api_secret,
                    'enableRateLimit': True,
                }
                if self.config.api_passphrase:
                    ws_opts['password'] = self.config.api_passphrase
                self.exchange_ws = exchange_ws_class(ws_opts)
                
                log('INFO', f'交易所已初始化: {self.config.exchange}')
                return
                
            except Exception as e:
                log('ERROR', f'交易所初始化失败 (尝试 {attempt + 1}/{max_retries}): {e}')
                
                # 关闭失败的连接
                if self.exchange:
                    try:
                        await self.exchange.close()
                    except:
                        pass
                    self.exchange = None
                
                if self.exchange_ws:
                    try:
                        await self.exchange_ws.close()
                    except:
                        pass
                    self.exchange_ws = None
                
                if attempt < max_retries - 1:
                    log('INFO', f'等待 {retry_delay} 秒后重试...')
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # 指数退避
                else:
                    raise Exception(f'交易所初始化失败，已重试 {max_retries} 次')
    
    async def close(self):
        """关闭交易所连接"""
        if self.exchange:
            await self.exchange.close()
        if self.exchange_ws:
            await self.exchange_ws.close()
    
    async def _retry_api_call(self, func, *args, **kwargs):
        """执行 API 调用，带重试逻辑和熔断器（含自动冷却恢复）"""
        if self.circuit_breaker_open:
            now = time.time()
            if now >= self.circuit_breaker_until:
                # 冷却到期，半开状态：允许一次试探
                log('INFO', f'熔断器冷却到期，尝试恢复...')
                self.circuit_breaker_open = False
                self.failure_count = 0
            else:
                remaining = int(self.circuit_breaker_until - now)
                raise Exception(f'Circuit breaker is open, {remaining}s until retry')

        for attempt in range(self.config.api_retry_limit):
            try:
                result = await func(*args, **kwargs)
                self.failure_count = 0
                # 成功调用后重置冷却时间
                self.circuit_breaker_cooldown = 60
                return result
            except Exception as e:
                self.failure_count += 1
                wait = 2 ** attempt
                log('WARN', f'API 调用失败 (尝试 {attempt+1}): {e}')

                if self.failure_count >= self.max_failures:
                    self.circuit_breaker_open = True
                    self.circuit_breaker_until = time.time() + self.circuit_breaker_cooldown
                    log('ERROR', f'熔断器已打开，{self.circuit_breaker_cooldown}s 后自动重试')
                    # 下次触发冷却翻倍，上限 10 分钟
                    self.circuit_breaker_cooldown = min(self.circuit_breaker_cooldown * 2, 600)
                    raise

                if attempt < self.config.api_retry_limit - 1:
                    await asyncio.sleep(wait)
                else:
                    raise
    
    async def create_limit_order(self, symbol: str, side: str, amount: float, price: float) -> Dict:
        """创建限价单"""
        return await self._retry_api_call(
            self.exchange.create_limit_order,
            symbol, side, amount, price
        )
    
    async def create_market_order(self, symbol: str, side: str, amount: float) -> Dict:
        """创建市价单"""
        return await self._retry_api_call(
            self.exchange.create_market_order,
            symbol, side, amount
        )
    
    async def cancel_order(self, order_id: str, symbol: str) -> Dict:
        """取消订单"""
        return await self._retry_api_call(
            self.exchange.cancel_order,
            order_id, symbol
        )
    
    async def fetch_order(self, order_id: str, symbol: str) -> Dict:
        """获取订单状态"""
        return await self._retry_api_call(
            self.exchange.fetch_order,
            order_id, symbol
        )
    
    async def fetch_open_orders(self, symbol: str) -> List[Dict]:
        """获取未完成订单"""
        return await self._retry_api_call(
            self.exchange.fetch_open_orders,
            symbol
        )
    
    async def fetch_balance(self) -> Dict:
        """获取账户余额"""
        return await self._retry_api_call(self.exchange.fetch_balance)
    
    async def fetch_ticker(self, symbol: str) -> Dict:
        """获取行情"""
        return await self._retry_api_call(self.exchange.fetch_ticker, symbol)
    
    async def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int) -> List[List]:
        """获取 OHLCV 数据"""
        return await self._retry_api_call(
            self.exchange.fetch_ohlcv,
            symbol, timeframe, limit=limit
        )


# ============================================================================
# WEBSOCKET MARKET DATA MANAGER
# ============================================================================

class MarketDataManager:
    """WebSocket 市场数据管理器，使用 ccxt.pro"""

    def __init__(self, exchange: ExchangeClient, symbol: str):
        self.exchange = exchange
        self.symbol = symbol
        self.ticker: Dict = {}
        self.klines: List[List] = []
        self.balance: Dict = {}
        self.order_updates: asyncio.Queue = asyncio.Queue()  # 所有非 open 状态的订单更新
        self.running = False
    
    async def start(self):
        """启动 WebSocket 流"""
        self.running = True
        
        # 先获取历史 K 线数据
        try:
            log('INFO', '正在获取历史 K 线数据...')
            historical_klines = await self.exchange.exchange.fetch_ohlcv(
                self.symbol, '1m', limit=100
            )
            self.klines = historical_klines
            log('INFO', f'历史 K 线已加载: {len(self.klines)} 根')
        except Exception as e:
            log('ERROR', f'获取历史 K 线失败: {e}')
        
        await asyncio.gather(
            self._watch_ticker(),
            self._watch_ohlcv(),
            self._poll_balance(),
            self._watch_orders(),  # WebSocket 监听订单成交
        )
    
    async def stop(self):
        """停止 WebSocket 流"""
        self.running = False
    
    async def _watch_ticker(self):
        """监听行情更新"""
        retry_delay = 5
        first_data = True
        while self.running:
            try:
                self.ticker = await self.exchange.exchange_ws.watch_ticker(self.symbol)
                if first_data:
                    log('INFO', f'Ticker 数据流已连接: {self.ticker.get("last", 0)}')
                    first_data = False
                retry_delay = 5  # 重置延迟
            except Exception as e:
                log('ERROR', f'Ticker 流错误: {e}')
                first_data = True
                if self.running:
                    log('INFO', f'等待 {retry_delay} 秒后重连...')
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, 60)  # 最多等待 60 秒
    
    async def _watch_ohlcv(self):
        """监听 OHLCV 更新"""
        retry_delay = 5
        first_data = True
        while self.running:
            try:
                klines = await self.exchange.exchange_ws.watch_ohlcv(self.symbol, '1m')
                if klines:
                    # 如果已有历史数据，只更新最新的 K 线
                    if len(self.klines) >= 60:
                        # 更新最后一根或追加新 K 线
                        if klines[-1][0] == self.klines[-1][0]:  # 同一时间戳，更新
                            self.klines[-1] = klines[-1]
                        else:  # 新 K 线，追加
                            self.klines.append(klines[-1])
                            self.klines = self.klines[-100:]  # 保留最后 100 根
                    else:
                        # 没有足够历史数据，直接使用
                        self.klines = klines[-100:]
                    
                    if first_data:
                        log('INFO', f'K线 数据流已连接: {len(self.klines)} 根')
                        first_data = False
                retry_delay = 5  # 重置延迟
            except Exception as e:
                log('ERROR', f'OHLCV 流错误: {e}')
                first_data = True
                if self.running:
                    log('INFO', f'等待 {retry_delay} 秒后重连...')
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, 60)
    
    async def _watch_balance(self):
        """监听余额更新（已弃用，改用轮询）"""
        pass
    
    async def _poll_balance(self):
        """轮询余额更新（每 10 秒）"""
        retry_delay = 5
        while self.running:
            try:
                balance = await self.exchange.exchange.fetch_balance()
                self.balance = balance
                retry_delay = 5
                await asyncio.sleep(10)  # 缩短至 10 秒 (修复8)
            except Exception as e:
                log('ERROR', f'余额查询错误: {e}')
                if self.running:
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, 60)

    async def _watch_orders(self):
        """WebSocket 监听订单状态变化，替代 polling (修复7)"""
        retry_delay = 5
        first_data = True
        while self.running:
            try:
                orders = await self.exchange.exchange_ws.watch_orders(self.symbol)
                for order in orders:
                    status = order.get('status')
                    if status and status != 'open':
                        await self.order_updates.put(order)
                if first_data:
                    log('INFO', '订单 WebSocket 流已连接')
                    first_data = False
                retry_delay = 5
            except Exception as e:
                log('ERROR', f'订单流错误: {e}')
                first_data = True
                if self.running:
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, 60)
    
    def get_current_price(self) -> float:
        """从行情获取当前价格"""
        return self.ticker.get('last', 0)
    
    def get_klines(self) -> List[List]:
        """获取当前 K 线"""
        return self.klines
    
    def get_balance(self) -> Tuple[float, float]:
        """获取 BTC 和 USDT 可用余额（用于下单判断）"""
        btc = float(self.balance.get('BTC', {}).get('free', 0) or 0)
        usdt = float(self.balance.get('USDT', {}).get('free', 0) or 0)
        return btc, usdt

    def get_total_balance(self) -> Tuple[float, float]:
        """获取 BTC 和 USDT 总余额（含挂单冻结，用于回撤计算）"""
        btc = float(self.balance.get('BTC', {}).get('total', 0) or 0)
        usdt = float(self.balance.get('USDT', {}).get('total', 0) or 0)
        return btc, usdt



# ============================================================================
# GRID TRADING BOT
# ============================================================================

class GridTradingBot:
    """主网格交易机器人协调器"""
    
    def __init__(self, config: Config):
        self.config = config
        self.db = Database(config)
        self.exchange = ExchangeClient(config)
        self.notifier = FeishuNotifier(config)
        self.market_data: Optional[MarketDataManager] = None
        self.grid_engine = GridEngine(config)
        self.regime_detector = RegimeDetector(config)
        self.inventory_manager = InventoryManager(config)
        
        self.state: Dict = {}
        self.open_orders: Dict[str, Dict] = {}
        self.running = False
    
    async def initialize(self):
        """初始化机器人组件"""
        log('INFO', '正在初始化 Hive 自适应网格交易系统...')
        
        await self.db.connect()
        await self.exchange.initialize()
        
        self.market_data = MarketDataManager(self.exchange, self.config.symbol)
        
        # 从数据库加载状态
        self.state = await self.db.load_grid_state(self.config.symbol)
        
        # 如果是首次运行，初始化状态
        if not self.state.get('base_position_btc'):
            await self._initialize_base_position()
        
        # 恢复未完成订单
        await self._resume_orders()
        
        await self.notifier.send(
            'startup',
            '🚀 Hive 网格机器人已启动',
            f"交易对: {self.config.symbol}\n最大仓位: {self.config.max_position}"
        )
        
        log('INFO', '机器人初始化成功')
    
    async def _initialize_base_position(self):
        """购买初始底仓"""
        # 计算底仓数量（使用 BASE_POSITION_RATIO 比例）
        base_position_usdt = self.config.max_position * self.config.base_position_ratio
        
        if self.config.base_position_price:
            # 指定了底仓价格，挂限价单
            target_price = self.config.base_position_price
            log('INFO', f'正在初始化底仓: 在 {target_price} 价格挂限价买单')
            amount = base_position_usdt / target_price
            
            try:
                order = await self.exchange.create_limit_order(
                    self.config.symbol, 'buy', amount, target_price
                )
                await self.db.save_order({**order, 'is_base_position': True, 'grid_level': 0})
                log('INFO', f'底仓限价单已下单: {order["id"]}, 数量: {amount:.6f} BTC @ {target_price}')
                
                await self.notifier.send(
                    'base_position',
                    '💰 底仓限价单已下单',
                    f"目标价格: {target_price}\n数量: {amount:.6f} BTC\n金额: {base_position_usdt:.2f} USDT\n\n等待成交后开始网格交易"
                )
                
                # 等待底仓订单成交（超时 30 分钟，可被 self.running 中断）
                log('INFO', '等待底仓订单成交（超时 30 分钟）...')
                wait_start = time.time()
                max_wait = 1800  # 30 分钟
                filled = False
                while time.time() - wait_start < max_wait:
                    if not self.running:
                        log('INFO', '收到关闭信号，取消底仓等待')
                        break
                    await asyncio.sleep(5)
                    try:
                        updated_order = await self.exchange.fetch_order(order['id'], self.config.symbol)
                        if updated_order['status'] == 'closed':
                            filled_amount = updated_order['filled']
                            avg_price = updated_order['average']
                            self.state['base_position_btc'] = filled_amount
                            self.state['base_position_cost'] = filled_amount * avg_price
                            await self.db.save_grid_state(self.state)
                            await self.db.update_order_status(order['id'], 'filled', filled_amount)

                            log('INFO', f'底仓已成交: {filled_amount:.6f} BTC @ {avg_price:.2f}')
                            await self.notifier.send(
                                'base_position_filled',
                                '✅ 底仓已成交',
                                f"数量: {filled_amount:.6f} BTC\n成交价: {avg_price:.2f}\n成本: {self.state['base_position_cost']:.2f} USDT"
                            )
                            filled = True
                            break
                    except Exception as e:
                        log('ERROR', f'查询底仓订单失败: {e}')
                        await asyncio.sleep(5)

                if not filled:
                    # 超时未成交，取消限价单，回退到市价建仓
                    log('WARN', '底仓限价单超时未成交，取消并改用市价建仓')
                    try:
                        await self.exchange.cancel_order(order['id'], self.config.symbol)
                        await self.db.update_order_status(order['id'], 'cancelled', 0)
                    except Exception:
                        pass
                    await self._initialize_base_position_market(base_position_usdt)
            except Exception as e:
                log('ERROR', f'创建底仓失败: {e}')
                return
        else:
            await self._initialize_base_position_market(base_position_usdt)

    async def _initialize_base_position_market(self, base_position_usdt: float):
        """市价建仓（也作为限价单超时后的回退）"""
        log('INFO', f'市价建仓: {base_position_usdt:.2f} USDT')

        ticker = await self.exchange.exchange.fetch_ticker(self.config.symbol)
        current_price = ticker['last']
        amount = base_position_usdt / current_price

        try:
            order = await self.exchange.create_market_order(
                self.config.symbol, 'buy', amount
            )

            filled_amount = order.get('filled', amount)
            avg_price = order.get('average', current_price)
            cost = filled_amount * avg_price

            self.state['base_position_btc'] = filled_amount
            self.state['base_position_cost'] = cost
            await self.db.save_grid_state(self.state)

            log('INFO', f'底仓市价单已成交: 数量={filled_amount:.6f} BTC, 均价={avg_price:.2f}, 成本={cost:.2f} USDT')

            await self.notifier.send(
                'base_position',
                '💰 底仓已建立',
                f"数量: {filled_amount:.6f} BTC\n均价: {avg_price:.2f}\n成本: {cost:.2f} USDT\n\n开始网格交易"
            )
        except Exception as e:
            log('ERROR', f'市价建仓失败: {e}')
            await self.notifier.send('error', '❌ 市价建仓失败', str(e))
            raise
    
    async def _resume_orders(self):
        """从数据库恢复管理现有订单，查询交易所真实状态"""
        db_orders = await self.db.load_open_orders(self.config.symbol)

        if not db_orders:
            return

        log('INFO', f'正在恢复 {len(db_orders)} 个未完成订单（从数据库）')

        try:
            exchange_orders = await self.exchange.fetch_open_orders(self.config.symbol)
            exchange_order_ids = {o['id'] for o in exchange_orders}

            for db_order in db_orders:
                oid = db_order['order_id']
                if oid in exchange_order_ids:
                    # 仍然挂单中，恢复管理
                    self.open_orders[oid] = db_order
                else:
                    # 不在挂单列表，必须查真实状态，不能盲标 filled
                    try:
                        real_order = await self.exchange.fetch_order(oid, self.config.symbol)
                        real_status = real_order.get('status', 'cancelled')
                        real_filled = float(real_order.get('filled', 0))

                        if real_status == 'closed' and real_filled > 0:
                            await self.db.update_order_status(oid, 'filled', real_filled)
                            # 如果是买单，补录 FIFO 库存
                            if db_order.get('side') == 'buy':
                                await self.db.add_inventory_lot(
                                    self.config.symbol, oid,
                                    float(db_order['price']), real_filled
                                )
                            log('INFO', f'恢复: 订单 {oid} 已成交 {real_filled}')
                        else:
                            await self.db.update_order_status(oid, 'cancelled', real_filled)
                            log('INFO', f'恢复: 订单 {oid} 状态={real_status}，标记取消')
                    except Exception as e:
                        # 查不到就标记 cancelled，比错标 filled 安全
                        log('WARN', f'恢复: 无法查询订单 {oid}: {e}，标记取消')
                        await self.db.update_order_status(oid, 'cancelled', 0)
        except Exception as e:
            log('ERROR', f'恢复订单失败: {e}')
    
    async def run(self):
        """主机器人循环"""
        self.running = True
        
        # Start market data streams
        market_data_task = asyncio.create_task(self.market_data.start())
        
        # Wait for initial data
        await asyncio.sleep(5)
        
        log('INFO', '正在启动主交易循环...')
        
        last_grid_update = 0
        
        try:
            while self.running:
                try:
                    # 更新市场数据和指标
                    current_price = self.market_data.get_current_price()
                    if current_price == 0:
                        log('WARN', '等待价格数据...')
                        await asyncio.sleep(self.config.worker_loop_seconds)
                        continue
                    
                    klines = self.market_data.get_klines()
                    if len(klines) < 60:
                        log('WARN', f'等待 K 线数据... (当前: {len(klines)}/60)')
                        await asyncio.sleep(self.config.worker_loop_seconds)
                        continue
                    
                    # 计算指标 (使用 EMA 平滑 ATR，修复1)
                    atr = Indicators.calculate_atr_smoothed(
                        klines, self.config.atr_period, self.config.atr_ema_alpha
                    )
                    ma_fast = Indicators.calculate_ma(klines, self.config.ma_fast)
                    ma_slow = Indicators.calculate_ma(klines, self.config.ma_slow)
                    adx = Indicators.calculate_adx(klines, self.config.adx_period)
                    
                    # 检测市场状态
                    regime = self.regime_detector.detect(ma_fast, ma_slow, adx)
                    
                    # 检查市场状态是否变化
                    last_regime = await self.db.get_last_regime(self.config.symbol)
                    if last_regime != regime.value:
                        await self.db.save_regime(regime.value, {
                            'symbol': self.config.symbol,
                            'atr': atr,
                            'ma_fast': ma_fast,
                            'ma_slow': ma_slow,
                            'adx': adx
                        })
                        await self.notifier.send(
                            'regime_change',
                            f'📊 市场状态: {regime.value}',
                            f"ADX: {adx:.2f}\n快线MA: {ma_fast:.2f}\n慢线MA: {ma_slow:.2f}"
                        )
                        log('INFO', f'市场状态变更为 {regime.value}', adx=adx)
                    
                    # 计算网格间距
                    new_step = self.grid_engine.calculate_step(atr)
                    log('INFO', f'ATR={atr:.2f}, 计算间距={new_step:.2f}')
                    
                    # 检查是否需要更新网格
                    now = time.time()
                    
                    # 获取当前网格状态
                    active_levels = self.state.get('active_levels', self.config.grid_active_levels) or self.config.grid_active_levels
                    grid_center = self.state.get('grid_center_price', 0) or 0
                    grid_step = self.grid_engine.current_step or 0
                    last_atr = self.state.get('last_atr', atr) or atr
                    
                    # 获取余额计算库存比例
                    btc_balance, usdt_balance = self.market_data.get_balance()
                    btc_value = btc_balance * current_price
                    total_value = btc_value + usdt_balance
                    btc_ratio = btc_value / total_value if total_value > 0 else 0
                    
                    # 条件 1: 价格突破网格范围
                    if grid_center > 0 and grid_step > 0:
                        grid_upper = grid_center + (grid_step * active_levels)
                        grid_lower = grid_center - (grid_step * active_levels)
                        price_out_of_range = current_price > grid_upper or current_price < grid_lower
                    else:
                        price_out_of_range = True  # 首次运行
                    
                    # 条件 2: ATR 变化 >25% 且距离上次更新 >5 分钟
                    atr_change_ratio = abs(atr - last_atr) / last_atr if last_atr > 0 else 0
                    time_since_update = now - last_grid_update
                    atr_changed = atr_change_ratio > 0.25 and time_since_update > 300
                    
                    # 条件 3: 库存比例越界 且距离上次更新 >5 分钟
                    # 使用配置的阈值，而不是硬编码
                    inventory_out_of_range = (
                        btc_ratio > self.config.btc_inventory_max or 
                        btc_ratio < self.config.btc_inventory_min
                    ) and time_since_update > 300
                    
                    # 条件 4: 时间兜底 >10 分钟
                    timeout = time_since_update > 600
                    
                    should_update = price_out_of_range or atr_changed or inventory_out_of_range or timeout
                    
                    if should_update:
                        if price_out_of_range:
                            reason = '价格突破'
                            new_grid_center = current_price
                        elif atr_changed:
                            reason = f'ATR变化 {atr_change_ratio*100:.1f}%'
                            # ATR 大变化时也移动 center，避免订单远离市场
                            new_grid_center = current_price
                        elif inventory_out_of_range:
                            reason = f'库存越界 {btc_ratio*100:.1f}%'
                            # 库存越界时，保持网格中心不变
                            new_grid_center = grid_center if grid_center > 0 else current_price
                        else:
                            reason = '定时更新'
                            # 定时更新时，保持网格中心不变
                            new_grid_center = grid_center if grid_center > 0 else current_price
                        
                        log('INFO', f'触发网格更新: {reason}')
                        await self._update_grid(new_grid_center, new_step, regime, atr)
                        self.state['grid_center_price'] = new_grid_center
                        self.state['last_atr'] = atr
                        last_grid_update = now
                    
                    # Process order fills
                    await self._process_fills()
                    
                    # Check infinity grid shift（本轮已更新过则跳过，避免双重重建）
                    if self.config.auto_shift_grid and not should_update:
                        await self._check_grid_shift(current_price)
                    
                    # Risk checks
                    await self._check_drawdown()
                    
                    # Update state
                    self.state.update({
                        'symbol': self.config.symbol,
                        'current_step': new_step,
                        'last_atr': atr,
                        'last_ma_fast': ma_fast,
                        'last_ma_slow': ma_slow,
                        'last_adx': adx,
                        'circuit_breaker_open': self.exchange.circuit_breaker_open,
                        'circuit_breaker_failures': self.exchange.failure_count,
                    })
                    await self.db.save_grid_state(self.state)
                    
                except Exception as e:
                    log('ERROR', f'主循环错误: {e}')
                    await self.notifier.send('error', '❌ 机器人错误', str(e))
                
                await asyncio.sleep(self.config.worker_loop_seconds)
        
        finally:
            # 停止市场数据流
            await self.market_data.stop()
            # 取消并等待任务完成
            market_data_task.cancel()
            try:
                await market_data_task
            except asyncio.CancelledError:
                pass
    
    async def _update_grid(self, current_price: float, step: float, regime: MarketRegime, atr: float):
        """更新网格订单"""
        log('INFO', f'更新网格: 价格={current_price:.2f}, 间距={step:.2f}, 状态={regime.value}')
        
        # 获取余额
        btc_balance, usdt_balance = self.market_data.get_balance()
        log('INFO', f'当前余额: BTC={btc_balance:.6f}, USDT={usdt_balance:.2f}')
        
        # Check inventory
        inventory_signal = self.inventory_manager.check_inventory(btc_balance, usdt_balance, current_price)
        inventory_adj = self.inventory_manager.get_level_adjustment(btc_balance, usdt_balance, current_price)
        log('INFO', f'库存信号: {inventory_signal.value}, 渐进调整: buy-{inventory_adj[0]} sell-{inventory_adj[1]}')

        # 分别计算买卖最大层数（买单受 USDT 限制，卖单受 BTC 限制）
        active_levels = self.state.get('active_levels', self.config.grid_active_levels)
        order_size = self.state.get('order_size_usdt', self.config.grid_order_size_usdt)

        max_buy_levels = max(0, int(usdt_balance / order_size)) if order_size > 0 else 0
        max_sell_levels = max(0, int(btc_balance * current_price / order_size)) if order_size > 0 else 0

        if max_buy_levels < active_levels or max_sell_levels < active_levels:
            log('INFO', f'余额限制: 买最多{max_buy_levels}层, 卖最多{max_sell_levels}层')

        # Generate new orders (with gradual inventory adjustment + per-side balance caps)
        new_orders = self.grid_engine.generate_orders(
            current_price, step, regime, inventory_signal, active_levels, inventory_adj,
            max_buy_levels=max_buy_levels, max_sell_levels=max_sell_levels
        )

        # 增量更新：只取消价格变化的订单，保留未变化的
        new_prices = {(o['side'], round(o['price'], 2)) for o in new_orders}
        existing_prices = {}
        for oid, o in list(self.open_orders.items()):
            key = (o.get('side', ''), round(float(o.get('price', 0)), 2))
            existing_prices[key] = oid

        # 取消不再需要的旧订单
        to_cancel = set(existing_prices.keys()) - new_prices
        for key in to_cancel:
            await self._cancel_order(existing_prices[key])

        # 只下新增的订单
        to_place = new_prices - set(existing_prices.keys())
        orders_by_key = {(o['side'], round(o['price'], 2)): o for o in new_orders}
        for key in to_place:
            await self._place_order(orders_by_key[key], order_size, atr, current_price)
        
        self.grid_engine.current_step = step
        self.state['active_levels'] = active_levels
        
        await self.notifier.send(
            'grid_update',
            '🔄 网格已更新',
            f"间距: {step:.2f}\n订单数: {len(new_orders)}\n状态: {regime.value}\nATR: {atr:.2f}"
        )
    
    async def _place_order(self, order_spec: Dict, base_size: float, atr: float, current_price: float):
        """下单一个网格订单，含精度截断和最小量校验"""
        size_usdt = self.grid_engine.calculate_order_size(base_size, atr, current_price)
        amount = size_usdt / order_spec['price']
        price = order_spec['price']

        # 用交易所 market 信息做精度截断和最小量校验
        ex = self.exchange.exchange
        market = ex.market(self.config.symbol)
        amount = float(ex.amount_to_precision(self.config.symbol, amount))
        price = float(ex.price_to_precision(self.config.symbol, price))

        limits = market.get('limits', {})
        min_amount = float(limits.get('amount', {}).get('min', 0) or 0)
        min_cost = float(limits.get('cost', {}).get('min', 0) or 0)

        if amount < min_amount:
            log('WARN', f'订单数量 {amount} 低于最小量 {min_amount}，跳过')
            return
        if amount * price < min_cost:
            log('WARN', f'订单名义金额 {amount * price:.2f} 低于最小值 {min_cost}，跳过')
            return

        try:
            order = await self.exchange.create_limit_order(
                self.config.symbol,
                order_spec['side'],
                amount,
                price
            )
            order['grid_level'] = order_spec['level']
            await self.db.save_order(order)
            self.open_orders[order['id']] = order
            
            if self.config.enable_order_log:
                log('INFO', f"订单已下单: {order['id']} {order_spec['side']} {amount:.6f} @ {order_spec['price']:.2f}")
            
            await self.notifier.send(
                'order_placed',
                f"📝 订单已下单: {order_spec['side'].upper()}",
                f"价格: {order_spec['price']:.2f}\n数量: {amount:.6f}\n层级: {order_spec['level']}"
            )
        except Exception as e:
            log('ERROR', f'下单失败: {e}')
    
    async def _cancel_all_orders(self):
        """取消所有未完成订单"""
        for order_id in list(self.open_orders.keys()):
            await self._cancel_order(order_id)
    
    async def _cancel_order(self, order_id: str):
        """取消单个订单"""
        try:
            await self.exchange.cancel_order(order_id, self.config.symbol)
            await self.db.update_order_status(order_id, 'cancelled', 0)
            if order_id in self.open_orders:
                del self.open_orders[order_id]
            if self.config.enable_order_log:
                log('INFO', f'订单已取消: {order_id}')
        except Exception as e:
            log('ERROR', f'取消订单失败 {order_id}: {e}')
    
    async def _process_fills(self):
        """处理 WebSocket 推送的订单状态变化（closed/canceled/expired）"""
        while not self.market_data.order_updates.empty():
            try:
                order = self.market_data.order_updates.get_nowait()
                order_id = order['id']
                status = order.get('status')

                if order_id not in self.open_orders:
                    continue

                if status == 'closed':
                    await self._handle_fill(order)
                elif status in ('canceled', 'expired', 'rejected'):
                    # 从本地状态中清除，数据库标记取消
                    del self.open_orders[order_id]
                    await self.db.update_order_status(order_id, 'cancelled', float(order.get('filled', 0)))
                    log('INFO', f'订单已{status}: {order_id}')
            except asyncio.QueueEmpty:
                break
            except Exception as e:
                log('ERROR', f'处理订单状态变化失败: {e}')
    
    async def _handle_fill(self, order: Dict):
        """处理已成交订单"""
        order_id = order['id']

        await self.db.update_order_status(order_id, 'filled', order['amount'])

        if order_id in self.open_orders:
            del self.open_orders[order_id]

        log('INFO', f"订单已成交: {order_id} {order['side']} {order['amount']:.6f} @ {order['price']:.2f}")

        await self.notifier.send(
            'order_filled',
            f"✅ 订单已成交: {order['side'].upper()}",
            f"价格: {order['price']:.2f}\n数量: {order['amount']:.6f}"
        )

        # FIFO 库存管理
        if order['side'] == 'buy':
            # 买入 → 添加库存批次
            await self.db.add_inventory_lot(
                self.config.symbol, order_id,
                float(order['price']), float(order['amount'])
            )
        else:
            # 卖出 → FIFO 消耗库存并计算利润
            await self._calculate_profit_fifo(order)

        # 成交后立即刷新余额 (修复8)
        try:
            balance = await self.exchange.fetch_balance()
            self.market_data.balance = balance
        except Exception as e:
            log('WARN', f'成交后余额刷新失败: {e}')

    async def _calculate_profit_fifo(self, sell_order: Dict):
        """FIFO 匹配库存并计算真实利润"""
        sell_price = float(sell_order['price'])
        sell_amount = float(sell_order['amount'])

        lots = await self.db.consume_inventory_fifo(self.config.symbol, sell_amount)

        if not lots:
            log('WARN', f'卖出 {sell_amount} 但无匹配库存，可能来自底仓')
            return

        total_profit = 0
        total_fee = 0
        weighted_buy_price = 0

        for lot in lots:
            buy_price = lot['buy_price']
            amount = lot['amount']
            gross = (sell_price - buy_price) * amount
            fee = (buy_price * amount * self.config.spot_maker_fee +
                   sell_price * amount * self.config.spot_maker_fee)
            net = gross - fee
            total_profit += net
            total_fee += fee
            weighted_buy_price += buy_price * amount

        avg_buy_price = weighted_buy_price / sell_amount if sell_amount > 0 else 0

        trade = {
            'symbol': self.config.symbol,
            'buy_order_id': lots[0]['buy_order_id'] if lots else 'unknown',
            'sell_order_id': sell_order['id'],
            'buy_price': avg_buy_price,
            'sell_price': sell_price,
            'amount': sell_amount,
            'profit': total_profit,
            'fee_total': total_fee
        }

        await self.db.save_trade(trade)

        self.state['total_profit'] = self.state.get('total_profit', 0) + total_profit

        log('INFO', f'网格利润(FIFO): {total_profit:.2f} USDT (买均价: {avg_buy_price:.2f})')

        await self.notifier.send(
            'profit',
            '💰 网格利润',
            f"利润: {total_profit:.2f} USDT\n买均价: {avg_buy_price:.2f}\n卖出: {sell_price:.2f}\n总计: {self.state['total_profit']:.2f}"
        )
    
    async def _check_grid_shift(self, current_price: float):
        """检查网格是否需要移动（无限网格）"""
        if not self.open_orders:
            return
        
        # 统一转 float，避免交易所返回 float 与数据库 Decimal 混合比较
        buy_prices = [float(o['price']) for o in self.open_orders.values() if o.get('side') == 'buy']
        sell_prices = [float(o['price']) for o in self.open_orders.values() if o.get('side') == 'sell']

        if not buy_prices or not sell_prices:
            return

        lowest_buy = min(buy_prices)
        highest_sell = max(sell_prices)
        
        # shift 使用 step * levels 作为阈值，避免频繁移动
        active_levels = self.state.get('active_levels', self.config.grid_active_levels)
        shift_threshold = self.grid_engine.current_step * max(2, active_levels)
        
        if current_price > highest_sell + shift_threshold:
            log('INFO', '网格向上移动')
            await self._update_grid(
                current_price,
                self.grid_engine.current_step,
                self.regime_detector.current_regime,
                self.state.get('last_atr', 0)
            )
        elif current_price < lowest_buy - shift_threshold:
            log('INFO', '网格向下移动')
            await self._update_grid(
                current_price,
                self.grid_engine.current_step,
                self.regime_detector.current_regime,
                self.state.get('last_atr', 0)
            )
    
    async def _check_drawdown(self):
        """检查最大回撤保护"""
        current_price = self.market_data.get_current_price()
        
        # 用 total 余额（含挂单冻结），避免挂单多时虚报回撤误触熔断
        btc_balance, usdt_balance = self.market_data.get_total_balance()

        portfolio_value = btc_balance * current_price + usdt_balance
        
        peak = self.state.get('peak_portfolio_value', portfolio_value)
        if portfolio_value > peak:
            peak = portfolio_value
            self.state['peak_portfolio_value'] = peak
        
        if peak > 0:
            drawdown = (peak - portfolio_value) / peak * 100
            
            if drawdown > self.config.max_drawdown_percent:
                log('ERROR', f'最大回撤已超限: {drawdown:.2f}%')
                await self.notifier.send(
                    'risk_alert',
                    '🚨 最大回撤已超限',
                    f"回撤: {drawdown:.2f}%\n停止所有交易！"
                )
                await self._cancel_all_orders()
                self.running = False
    
    async def shutdown(self):
        """优雅关闭"""
        log('INFO', '正在关闭机器人...')
        self.running = False
        
        # 停止市场数据流
        if self.market_data:
            await self.market_data.stop()
        
        # 取消所有订单
        order_count = len(self.open_orders)
        if order_count > 0:
            log('INFO', f'正在取消 {order_count} 个未完成订单...')
            await self._cancel_all_orders()
            log('INFO', '所有订单已取消')
        
        # 关闭连接
        await self.exchange.close()
        await self.db.close()
        
        # 发送通知
        await self.notifier.send(
            'shutdown',
            '🛑 机器人已停止',
            f"总利润: {self.state.get('total_profit', 0):.2f} USDT"
        )
        
        log('INFO', '机器人已关闭')
        
        # 等待一下让通知发送完成
        await asyncio.sleep(1)



# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

async def main():
    """主入口点"""
    # 解析参数
    args = parse_args()
    
    # 加载配置
    config = load_config(args.config, args.exchange)
    
    # 应用 CLI 覆盖
    if args.max_position:
        config.max_position = args.max_position
    if args.base_position_price:
        config.base_position_price = args.base_position_price
    
    # 验证配置
    if not config.api_key or not config.api_secret:
        log('ERROR', 'API 凭证未配置')
        sys.exit(1)
    if config.exchange == 'okx' and not config.api_passphrase:
        log('ERROR', 'OKX 需要配置 OKX_PASSPHRASE')
        sys.exit(1)
    
    if not config.max_position:
        log('ERROR', '--max-position 参数必填')
        sys.exit(1)
    
    # 创建机器人
    bot = GridTradingBot(config)
    
    # 信号处理：只设标志位，让主循环自行退出并完成优雅关闭
    # 不调用 loop.stop()，否则 shutdown 协程（取消订单、关连接）会被截断
    def request_shutdown():
        if bot.running:
            log('INFO', '收到关闭信号，正在优雅关闭...')
            bot.running = False

    loop = asyncio.get_event_loop()
    loop.add_signal_handler(signal.SIGINT, request_shutdown)
    loop.add_signal_handler(signal.SIGTERM, request_shutdown)

    # 初始化并运行
    try:
        await bot.initialize()
        await bot.run()
    except Exception as e:
        log('ERROR', f'致命错误: {e}')
    finally:
        await bot.shutdown()


if __name__ == '__main__':
    asyncio.run(main())
