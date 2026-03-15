阅读 doc/grid.py 和 .env
这是一个已经验证过的网格程序，我现在要将这个程序改成一个工蜂线程，配合蜂巢和蜂王逻辑，
实现一个蜂巢量化交易系统。


整个项目的PRD如下：

# 🐝 Hive Trading System

**AI Strategy Orchestrated Crypto Trading System**

---

# 1. 项目目标

Hive Trading System 是一个 **AI 驱动的多策略自动交易系统**。

核心目标：

1️⃣ **避免一次性重仓进场**

* 将资金分散为多个策略实例
* 每个实例独立运行

2️⃣ **通过 AI 判断入场时机**

* 避免熊市顶入场
* 控制风险

3️⃣ **策略模块化**

未来可以增加：

* 无限网格
* 跨所套利
* 资金费率套利
* 趋势跟踪
* 做市策略

4️⃣ **高并发策略实例**

一个蜂巢可以同时运行：

```
10 ~ 50 个策略实例
```

---

# 2. 系统核心概念

## 2.1 Hive（蜂巢）

一个蜂巢代表：

```
一个交易所
+ 一组资金
+ 一组策略实例
```

示例：

```
Hive-Binance
Hive-OKX
Hive-Bybit
```

每个 Hive：

```
总资金：10000U
子资金：1000U × 10
```

---

## 2.2 Queen（蜂王）

蜂王是 **策略调度中心**。

负责：

* 获取市场行情
* AI 决策
* 派出工蜂
* 风控
* 通知

核心功能：

```
Market Scanner
AI Decision
Worker Dispatch
Risk Control
Notification
```

---

## 2.3 Worker Bee（工蜂）

每个工蜂是：

```
一个策略实例
```

例如：

```
Worker-1
Strategy: Infinite Grid
Capital: 1000U
Pair: BTC/USDT
```

工蜂生命周期：

```
Idle
↓
Assigned
↓
Running
↓
Profit Completed
↓
Return Hive
↓
Closed
```

---

# 3. 资金模型

蜂巢资金：

```
Total Capital: 10000U
```

分为：

```
Capital Slots: 10
```

每个 Slot：

```
1000U
```

蜂王派工蜂：

```
派出工蜂 -> 占用一个 Slot
```

示例：

```
Worker1  BTC grid
Worker2  ETH grid
Worker3  SOL grid
```

---

# 4. 系统架构

```
                ┌─────────────────┐
                │   Feishu Alert  │
                └────────▲────────┘
                         │

                 ┌───────┴───────┐
                 │     Queen     │
                 │ Strategy Core │
                 └───────┬───────┘
                         │
              Redis Event Bus
                         │
        ┌───────────────┼───────────────┐
        │               │               │

   ┌────▼────┐     ┌────▼────┐     ┌────▼────┐
   │ Worker  │     │ Worker  │     │ Worker  │
   │ Bee #1  │     │ Bee #2  │     │ Bee #3  │
   │ Grid    │     │ Grid    │     │ Arb     │
   └─────────┘     └─────────┘     └─────────┘


                ▲
                │

        ┌───────┴────────┐
        │ Market Scanner │
        └────────────────┘
```

---

# 5. 技术架构

语言：

```
Python
```

核心组件：

| 组件   | 技术              |
| ---- | --------------- |
| 交易接口 | ccxt / ccxt.pro |
| 消息系统 | Redis           |
| AI   | 本地 LLM / xAI / Deepseek等 |
| 任务调度 | asyncio         |
| 数据库  | PostgreSQL      |
| 日志   | Loki / ELK      |
| 通知   | Feishu          |

---

# 6. Redis 信息共享设计

Redis 作为：

```
Hive Message Bus
```

共享信息：

---

## 6.1 行情缓存

key

```
market:price:BTCUSDT
```

value

```
{
  price: 67000,
  bid: 66999,
  ask: 67001,
  timestamp: 171000000
}
```

TTL

```
1s
```

---

## 6.2 Worker 状态

```
worker:{id}:status
```

示例：

```
worker:3
```

```
{
 strategy: infinite_grid
 pair: BTC/USDT
 capital: 1000
 pnl: 23.4
 status: running
 entry_price: 65000
}
```

---

## 6.3 Hive 状态

```
hive:status
```

```
{
 total_capital: 10000
 used_capital: 4000
 free_capital: 6000
 workers_running: 4
}
```

---

# 7. AI 入场决策

蜂王 AI 任务：

```
是否派工蜂
```

输入：

```
价格
RSI
ATR
趋势
资金费率
成交量
```

示例 prompt：

```
Market:

BTC price: 67000
RSI: 38
ATR: 1200
Trend: Downtrend

Capital available: 6000

Question:
Is it a good time to deploy a grid worker?
```

输出：

```
decision: deploy
pair: BTC/USDT
strategy: infinite_grid
confidence: 0.82
```

---

# 8. 工蜂策略接口设计

为了未来扩展策略：

统一接口：

```
class Strategy:

    def start()

    def on_price_update()

    def on_order_filled()

    def stop()
```

示例：

```
InfiniteGridStrategy
FundingArbitrageStrategy
CrossExchangeArbitrage
TrendFollowing
```

---

# 9. 无限网格 Worker

Worker 启动：

```
Worker #3
Strategy: Infinite Grid
Capital: 1000U
Pair: BTCUSDT
```

流程：

```
启动
↓

建立底仓

↓

启动无限网格

↓

持续套利

↓

底仓盈利 > X%

↓

结束策略
```

返回蜂巢：

```
Capital returned: 1023U
Profit: 23U
```

---

# 10. Worker 生命周期

状态机：

```
INIT

↓

READY

↓

RUNNING

↓

PAUSED

↓

PROFIT_EXIT

↓

CLOSED
```

异常：

```
ERROR
NETWORK_FAIL
INSUFFICIENT_BALANCE
```

---

# 11. 风控系统

蜂王风控：

---

### 11 最大工蜂数

```
max_workers = 10
```

---

### 11.2 最大仓位

```
max_capital_usage = 60%
```

---

### 11.3 单币种限制

```
max_workers_per_pair = 2
```

---

### 11.4 熊市保护

当：

```
BTC跌幅 > 15% / 24h
```

蜂王：

```
暂停派工蜂
```

---

# 12. Feishu 通知

通知类型：

---

## Worker 派出

```
🐝 Worker Deployed

Pair: BTC/USDT
Strategy: Infinite Grid
Capital: 1000U
```

---

## Worker 完成

```
🍯 Worker Returned

Profit: 24U
Duration: 6h
```

---

## 风控触发

```
⚠️ Hive Risk Alert

BTC dropped 12%
Worker deployment paused
```

---

# 13. 扩展能力

### 新策略-**暂不实现**

```
Funding Arbitrage
Cross Exchange Arbitrage
Trend Strategy
DCA Strategy
```

---

### 多交易所

```
Hive Binance
Hive OKX
Hive Bybit
```

---

### 多 AI

```
AI-1 Market Scanner
AI-2 Risk Control
AI-3 Strategy Optimizer
```

---

# 14. 未来高级版本（Hive v2）

### AI 自适应策略

AI 自动：

```
调整网格间距
调整杠杆
调整资金
```

---

### Worker 进化系统

根据历史收益：

```
淘汰差策略
增加好策略
```

类似：

```
策略进化系统
```

---

# 15. MVP版本

第一版只做：

```
Hive
Queen
Worker
Infinite Grid
```

功能：

```
AI派工蜂
无限网格
Redis状态共享
Feishu通知
```

周期：

```
开发时间：7~10天
```

---

# 16. 项目目录

```
hive_trading_system/

core/
    queen.py
    hive.py

workers/
    worker.py

strategies/
    infinite_grid.py

market/
    scanner.py

ai/
    decision_engine.py

risk/
    risk_manager.py

infra/
    redis_client.py

notify/
    feishu.py
```

---

# 17. 终极目标

Hive 不是一个机器人。

而是：

```
自动策略生态系统
```

未来：

```
100 Hive
1000 Workers
AI 自动管理
```

-------------------
# 🐝 Hive Trading System 前端技术栈

Hive Trading System 的核心是 **策略编排 + 实时状态可视化**，前端主要承担：

1️⃣ 蜂巢监控
2️⃣ 工蜂策略控制
3️⃣ 实时交易状态
4️⃣ 风控报警
5️⃣ AI 决策展示

---
## 1. 核心框架

**推荐**

* Next.js (App Router)

原因：

* SSR + CSR 混合
* WebSocket 支持好
* API Route 可做轻量中间层
* 生态成熟

技术：

```text
Framework: Next.js 14+
Language: TypeScript
Rendering: App Router
```

---

# 2. UI组件系统

推荐：

* shadcn/ui

优势：

* 不是组件库，而是 **代码级组件**
* 完全可定制
* 很适合交易系统后台

UI风格：

```text
Dark Trading Theme
类似 TradingView / Binance
```

基础组件：

```text
Card
Table
Dialog
Drawer
Tabs
Alert
Badge
```

---

# 3. 样式系统

推荐：

* Tailwind CSS

优点：

```text
开发速度极快
非常适合Dashboard
```

配置：

```js
darkMode: "class"
```

交易系统 **必须深色主题**。

---

# 4. 状态管理

推荐：

* Zustand

为什么不用 Redux：

```text
Redux 太重
Zustand 非常轻
实时系统很好用
```

使用场景：

```text
Market状态
Worker状态
Hive状态
用户配置
```

---

# 5. 实时数据通信

量化系统核心是 **实时状态**。

推荐：

### WebSocket

后端：

```text
FastAPI WebSocket
```

前端：

```text
native WebSocket
```

或：

* Socket.IO

实时数据：

```text
Worker状态
价格
PnL
订单状态
```

---

# 6. 数据请求

推荐：

* TanStack Query

优势：

```text
缓存
自动重试
实时刷新
```

示例：

```ts
useQuery({
  queryKey: ["workers"],
  queryFn: fetchWorkers,
  refetchInterval: 3000
})
```

---

# 7. 图表系统

交易系统必备。

推荐：

### 1 轻量

* Recharts

用于：

```text
收益曲线
策略统计
资金分布
```

---

### 2 K线图

强烈推荐：

* TradingView Lightweight Charts

用于：

```text
K线
网格展示
策略标记
```

效果：

```text
BTC Kline
+ Worker entry
+ grid lines
```

---

# 8. 数据表格

推荐：

* TanStack Table

展示：

```text
Worker列表
交易记录
订单记录
```

---

# 9. 前端权限系统

推荐：

```text
JWT
```

Next.js 中间件：

```ts
middleware.ts
```

角色：

```text
Admin
Trader
Viewer
```

---

# 10. Dashboard UI结构

前端结构建议：

```
/app

/dashboard
    hive
    workers
    strategies
    market
    orders
    risk
```

---

# 11. Hive 控制面板

页面：

```
/dashboard/hive
```

显示：

```text
Hive资金
Worker数量
收益
风险
```

UI：

```
Hive Binance

Total Capital   10000U
Used Capital    4000U
Workers         4
Profit          +213U
```

---

# 12. Worker 管理

```
/dashboard/workers
```

表格：

| ID                                   | Pair | Strategy | Capital | PnL | Status |
| ------------------------------------ | ---- | -------- | ------- | --- | ------ |
| Worker-1 BTC Grid 1000U +24U Running |      |          |         |     |        |

操作：

```text
暂停
恢复
关闭
```

---

# 13. Strategy 面板

```
/dashboard/strategies
```

展示：

```text
Infinite Grid
Funding Arbitrage
Cross Exchange Arb
```

可以：

```text
手动派出 Worker
```

---

# 14. Market Scanner

```
/dashboard/market
```

展示：

```text
BTC
ETH
SOL
```

指标：

```text
RSI
ATR
Volume
Funding Rate
```

---

# 15. 风控中心

```
/dashboard/risk
```

显示：

```text
最大仓位
最大Worker
BTC跌幅
```

报警：

```text
⚠ BTC 24h drop 12%
```

---

# 16. 收益统计

```
/dashboard/analytics
```

图表：

```text
Total PnL
Worker收益排行
策略收益
资金利用率
```

---

# 17. 项目目录

前端结构：

```
hive-ui

app
  dashboard
  workers
  hive
  strategies
  market
  analytics

components
  hive
  worker
  charts
  tables

lib
  api
  websocket
  utils

store
  hiveStore
  workerStore
```

---

# 18. UI设计风格

建议参考：

交易系统 UI：

* Binance
* OKX
* TradingView

风格：

```text
深色
数据密集
实时更新
```

---

# 19. 推荐完整前端技术栈

最终：

```
Framework
Next.js

Language
TypeScript

UI
shadcn/ui

Style
Tailwind CSS

State
Zustand

Data Fetch
TanStack Query

Table
TanStack Table

Charts
Recharts

Kline
TradingView Lightweight Charts

Realtime
WebSocket
```

---

# 20. 部署

Docker
端口 10080

---

下面是一份 **Hive Trading System – Grid Strategy 改造 PRD**。
目标是把原来的 `grid.py` 从 **单机器人脚本**升级为 **Hive Worker Strategy Plugin**，支持：

* 多 Worker
* 动态配置
* Redis 行情共享
* Dashboard 管理
* 策略扩展

---

# 🐝 Hive Trading System

# Grid Strategy 改造 PRD

版本

```
v1.0
```

目标

```
将原 grid.py 升级为 Hive 系统的 Strategy Worker
```

---

# 1 项目目标

原系统：

```
grid.py
```

特点：

* 单策略
* 单进程
* env 配置
* 不可动态调整
* 不支持 Worker 调度

改造目标：

```
Grid Strategy → Hive Worker Strategy
```

支持：

```
多 Worker
策略插件化
动态配置
Redis 状态共享
Dashboard 控制
系统恢复
```

---

# 2 原系统架构问题

原 grid.py

```
while True:
    price = fetch_price()
    check_grid()
```

问题：

| 问题       | 说明         |
| -------- | ---------- |
| 配置写死     | env 参数     |
| 无法多实例    | 只能跑一个 grid |
| API 请求过多 | 每个策略请求交易所  |
| 无法控制     | 无法暂停       |
| 无状态恢复    | 重启丢网格      |

---

# 3 改造总体架构

目标架构：

```
Hive
   │
   ├── Queen (调度)
   │
   └── Worker
           │
           └── Strategy
                   │
                   └── InfiniteGridStrategy
```

Worker 负责：

```
策略运行
状态更新
订单处理
```

---

# 4 Strategy Plugin 架构

新增目录：

```
strategies/
```

结构：

```
strategies/

base_strategy.py
infinite_grid.py
funding_arbitrage.py
trend_strategy.py
```

---

# 5 Strategy Base Interface

所有策略统一接口：

```python
class Strategy:

    async def start()

    async def on_price_update(price)

    async def on_order_filled(order)

    async def reload_config()

    async def stop()
```

说明：

| 函数              | 用途    |
| --------------- | ----- |
| start           | 初始化策略 |
| on_price_update | 行情更新  |
| on_order_filled | 订单成交  |
| reload_config   | 配置更新  |
| stop            | 停止策略  |

---

# 6 Worker Engine

新增模块：

```
core/worker.py
```

Worker 启动流程：

```
Load Worker Config
Load Strategy
Start Strategy
Subscribe Market
Run Event Loop
```

Worker 运行逻辑：

```python
while running:

    price = redis.get("price:BTCUSDT")

    strategy.on_price_update(price)

    sleep(0.5)
```

---

# 7 配置系统改造

原系统：

```
.env
```

示例：

```
GRID_STEP=0.002
GRID_LEVELS=20
GRID_CAPITAL=1000
```

问题：

```
无法动态修改
不支持多 Worker
```

---

# 8 Worker 配置数据库设计

表：

```
workers
```

字段：

```
id
hive_id
strategy_name
pair
capital
status
config jsonb
state jsonb
created_at
updated_at
```

---

# 9 config JSON 设计

示例：

Grid Worker

```json
{
  "strategy": "infinite_grid",
  "params": {
    "grid_step": 0.002,
    "grid_levels": 20,
    "atr_multiplier": 1.2
  },
  "risk": {
    "take_profit": 0.02,
    "max_drawdown": 0.05
  }
}
```

---

# 10 state JSON

state 存储运行状态：

```json
{
  "entry_price": 67000,
  "grid_range": [65000,72000],
  "active_grids": 18,
  "realized_pnl": 24.5
}
```

作用：

```
系统恢复
Dashboard展示
```

---

# 11 Worker 生命周期

Worker 状态：

```
INIT
RUNNING
PAUSED
STOPPED
ERROR
```

状态流：

```
INIT → RUNNING
RUNNING → PAUSED
PAUSED → RUNNING
RUNNING → STOPPED
```

---

# 12 Redis 行情共享

原系统：

```
grid.py → 交易所 API
```

问题：

```
多 Worker 会打爆 API
```

改造：

行情统一缓存。

Redis key：

```
price:BTCUSDT
price:ETHUSDT
```

结构：

```json
{
 "price":67000,
 "bid":66999,
 "ask":67001,
 "ts":171000000
}
```

刷新：

```
500ms
```

---

# 13 Worker 状态同步

Worker 定期更新 Redis：

key

```
worker:{id}:status
```

示例：

```json
{
 "pair":"BTCUSDT",
 "strategy":"infinite_grid",
 "capital":1000,
 "pnl":24.3,
 "status":"running"
}
```

Dashboard 使用。

---

# 14 Worker 控制机制

控制 key：

```
worker:{id}:command
```

命令：

```
pause
resume
stop
```

Worker 监听：

```python
cmd = redis.get(command_key)
```

---

# 15 Grid 状态持久化

新增表：

```
grid_orders
```

字段：

```
worker_id
price
side
amount
order_id
status
created_at
```

作用：

```
系统恢复
订单追踪
```

---

# 16 Worker 恢复机制

Worker 启动：

```
Load worker state
Load grid orders
Rebuild grids
```

避免：

```
重启丢网格
```

---

# 17 Grid 动态参数更新

Dashboard 修改：

```
workers.config
```

Worker 每 5 秒检查：

```
updated_at
```

更新：

```
reload_config()
```

例如：

```
grid_step 0.002 → 0.003
```

---

# 18 风控接口

Strategy 必须支持：

```python
async def risk_check()
```

示例：

```
BTC 24h 跌幅 > 10%
```

Worker：

```
pause strategy
```

---

# 19 Worker 心跳

Worker 每 3 秒发送：

```
worker:{id}:heartbeat
```

Hive 检测：

```
> 10 秒
```

判定：

```
Worker Crash
```

---

# 20 Grid 可视化数据

Worker 输出：

```
worker:{id}:grid
```

数据：

```json
{
 "grids":[
   {"price":66000,"side":"buy"},
   {"price":68000,"side":"sell"}
 ]
}
```

Dashboard 可以画：

```
Grid Lines
```

---

# 21 Grid Strategy 类结构

```
strategies/infinite_grid.py
```

核心方法：

```
start()
init_position()
on_price_update()
check_grid()
on_order_filled()
reload_config()
stop()
```

---

# 22 项目目录结构

```
hive_trading_system

core
   worker.py
   queen.py

strategies
   base_strategy.py
   infinite_grid.py

market
   scanner.py

infra
   redis_client.py
   db_client.py

notify
   feishu.py
```

---

# 23 Dashboard 支持

Dashboard 可以：

```
查看 Worker
修改 config
暂停 Worker
关闭 Worker
```

数据来自：

```
Redis
Postgres
```


新增模块：

```
worker engine
strategy base
config loader
state manager
```

---

# 25 改造后的能力

系统获得：

```
多 Worker
动态参数
策略插件
实时监控
系统恢复
策略扩展
```

---

# 26 未来扩展

Hive 将支持：

```
Infinite Grid
Funding Arbitrage
Cross Exchange Arbitrage
Trend Strategy
```

无需修改数据库结构。

---

# 27 成功标准

系统完成时必须满足：

```
可同时运行10个Worker
Dashboard可动态修改参数
Worker状态实时更新
系统重启可恢复网格
API调用减少80%
```

---