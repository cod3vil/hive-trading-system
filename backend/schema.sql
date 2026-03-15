-- Hive Trading System Database Schema

-- Hives table: Exchange instances with capital pools
CREATE TABLE IF NOT EXISTS hives (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    exchange VARCHAR(50) NOT NULL,
    total_capital DECIMAL(20, 8) NOT NULL,
    used_capital DECIMAL(20, 8) DEFAULT 0,
    free_capital DECIMAL(20, 8) GENERATED ALWAYS AS (total_capital - used_capital) STORED,
    max_workers INT DEFAULT 10,
    max_capital_usage_percent DECIMAL(5, 2) DEFAULT 60.00,
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Workers table: Strategy instances
CREATE TABLE IF NOT EXISTS workers (
    id SERIAL PRIMARY KEY,
    hive_id INT REFERENCES hives(id) ON DELETE CASCADE,
    strategy_name VARCHAR(100) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    capital DECIMAL(20, 8) NOT NULL,
    status VARCHAR(20) DEFAULT 'init',
    config JSONB NOT NULL DEFAULT '{}',
    state JSONB NOT NULL DEFAULT '{}',
    pnl DECIMAL(20, 8) DEFAULT 0,
    total_trades INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    started_at TIMESTAMP,
    stopped_at TIMESTAMP
);

-- Worker orders table
CREATE TABLE IF NOT EXISTS worker_orders (
    id SERIAL PRIMARY KEY,
    worker_id INT REFERENCES workers(id) ON DELETE CASCADE,
    order_id VARCHAR(100) NOT NULL UNIQUE,
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,
    price DECIMAL(20, 8) NOT NULL,
    amount DECIMAL(20, 8) NOT NULL,
    filled DECIMAL(20, 8) DEFAULT 0,
    status VARCHAR(20) NOT NULL,
    grid_level INT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Worker trades table
CREATE TABLE IF NOT EXISTS worker_trades (
    id SERIAL PRIMARY KEY,
    worker_id INT REFERENCES workers(id) ON DELETE CASCADE,
    symbol VARCHAR(20) NOT NULL,
    buy_order_id VARCHAR(100),
    sell_order_id VARCHAR(100),
    buy_price DECIMAL(20, 8) NOT NULL,
    sell_price DECIMAL(20, 8) NOT NULL,
    amount DECIMAL(20, 8) NOT NULL,
    profit DECIMAL(20, 8) NOT NULL,
    fee_total DECIMAL(20, 8) DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Inventory lots table (FIFO tracking)
CREATE TABLE IF NOT EXISTS inventory_lots (
    id SERIAL PRIMARY KEY,
    worker_id INT REFERENCES workers(id) ON DELETE CASCADE,
    symbol VARCHAR(20) NOT NULL,
    buy_order_id VARCHAR(100) NOT NULL,
    buy_price DECIMAL(20, 8) NOT NULL,
    original_amount DECIMAL(20, 8) NOT NULL,
    remaining_amount DECIMAL(20, 8) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Market snapshots table
CREATE TABLE IF NOT EXISTS market_snapshots (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    price DECIMAL(20, 8) NOT NULL,
    atr DECIMAL(20, 8),
    ma_fast DECIMAL(20, 8),
    ma_slow DECIMAL(20, 8),
    adx DECIMAL(20, 8),
    regime VARCHAR(20),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Queen decisions table
CREATE TABLE IF NOT EXISTS queen_decisions (
    id SERIAL PRIMARY KEY,
    hive_id INT REFERENCES hives(id) ON DELETE CASCADE,
    symbol VARCHAR(20) NOT NULL,
    decision VARCHAR(20) NOT NULL,
    confidence DECIMAL(5, 4),
    strategy_name VARCHAR(100),
    capital DECIMAL(20, 8),
    reasoning TEXT,
    market_data JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_workers_hive_id ON workers(hive_id);
CREATE INDEX IF NOT EXISTS idx_workers_status ON workers(status);
CREATE INDEX IF NOT EXISTS idx_worker_orders_worker_id ON worker_orders(worker_id);
CREATE INDEX IF NOT EXISTS idx_worker_orders_status ON worker_orders(status);
CREATE INDEX IF NOT EXISTS idx_worker_trades_worker_id ON worker_trades(worker_id);
CREATE INDEX IF NOT EXISTS idx_inventory_lots_worker_id ON inventory_lots(worker_id);
CREATE INDEX IF NOT EXISTS idx_market_snapshots_symbol ON market_snapshots(symbol);
CREATE INDEX IF NOT EXISTS idx_queen_decisions_hive_id ON queen_decisions(hive_id);

-- Update timestamp trigger
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_hives_updated_at BEFORE UPDATE ON hives
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_workers_updated_at BEFORE UPDATE ON workers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_worker_orders_updated_at BEFORE UPDATE ON worker_orders
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
