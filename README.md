# Astock

行情数据分析平台，覆盖 A 股、美股、全球指数、贵金属、外汇、美债等多类资产，提供牛市统计、成交额排名、资产价格水位、市场行情概览等分析能力。后端基于 FastAPI + SQLite + Redis，前端基于 Vue 3 + Arco Design Pro。

## 功能

平台按四个分析模块组织，对应前端四个页面：

- **A 股牛市数据** — 按上证点位 / 成交额阈值筛选历史牛市区间，展示区间天数、峰值等统计
- **A 股成交额排名** — 大盘（上证 / 深成 / 创业板）与个股的历史成交额 TopN 排名，可按牛市区间过滤
- **全球资产价格水位** — 美股个股、贵金属等资产当前价相对历史高点（ATH）的回撤幅度、距高点天数、日 / 周涨跌及结论标签
- **全球市场概览** — 美股指数、A 股指数、贵金属、原油、外汇、美债收益率等分类行情的日 / 周涨跌一览

数据通过手动调用导入接口拉取并缓存：A 股数据落 SQLite，全球资产 / 市场概览数据落 Redis（行情概览实时抓取，不写库）。

## 技术栈

### 后端

| 类别 | 技术 |
| --- | --- |
| Web 框架 | FastAPI + Uvicorn |
| ORM / 数据库 | SQLModel + SQLite（WAL 模式） |
| 缓存 | Redis（全球资产与行情概览的收盘价快照） |
| 数据源 | BaoStock（A 股指数 / 个股）、腾讯行情（个股市值快照）、akshare（美股 / 商品 / 外汇 / 美债等） |
| 配置 | python-dotenv + YAML（牛市区间、全球资产清单、行情概览分类） |
| 并发 | `ProcessPoolExecutor`（个股日线抓取）；akshare 抓取强制串行 |

### 前端

| 类别 | 技术 |
| --- | --- |
| 框架 | Vue 3（Composition API + `<script setup>`）+ TypeScript |
| UI 组件 | Arco Design Vue（Arco Design Pro 脚手架） |
| 状态管理 | Pinia |
| 路由 | Vue Router 4 |
| HTTP | axios（统一 baseURL `/api/v1`） |
| 国际化 | vue-i18n（中 / 英） |
| 构建 | Vite |

脚手架内置暗色模式、响应式移动端适配等能力。

## 本地运行

### 环境要求

- Python 3.10+
- Node.js 14+、pnpm 8+
- Redis（全球资产与行情概览功能依赖；未连接时自动降级直连数据源）
- 可访问 BaoStock / 腾讯行情 / akshare 数据源的网络环境

### 后端

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # 按需修改 DB_PATH / FASTAPI_PORT / REDIS_URL
python main.py
```

服务默认监听 `http://localhost:8000`，Swagger 文档位于 `/docs`。

### 前端

```bash
cd frontend
pnpm install
pnpm dev
```

前端通过 Vite proxy 将 `/api` 代理到 `http://localhost:8000`，访问终端输出的开发地址即可。

## 数据导入

通过管理接口手动触发，支持按数据集分批导入，或一次性全量导入。导入基于 `SyncMeta` 表记录的最近同步日期做增量更新。

```bash
# 全量导入（turnover → point → stock → global_assets）
curl -X POST "http://localhost:8000/api/v1/admin/data/import?dataset=all"

# A 股三大指数日线成交额（BaoStock）
curl -X POST "http://localhost:8000/api/v1/admin/data/import?dataset=turnover"

# 上证指数日线点位（BaoStock）
curl -X POST "http://localhost:8000/api/v1/admin/data/import?dataset=point"

# 大市值个股成交额切片（BaoStock + 腾讯行情，市值 ≥ 1000 亿、日成交额 ≥ 300 亿）
curl -X POST "http://localhost:8000/api/v1/admin/data/import?dataset=stock"

# 全球资产历史高点刷新（akshare，美股个股 + 贵金属）
curl -X POST "http://localhost:8000/api/v1/admin/data/import?dataset=global_assets"

# 查看各数据集同步状态
curl "http://localhost:8000/api/v1/admin/data/sync-status"
```

> 行情概览（market-overview）由前端访问时实时抓取并缓存于 Redis，无需导入。

## 项目结构

```text
├── backend/
│   ├── main.py                  # uvicorn 启动入口
│   ├── .env.example             # 环境变量模板
│   ├── requirements.txt
│   └── astock/
│       ├── main.py              # FastAPI 应用与路由注册
│       ├── config.py            # 环境变量 + 业务阈值 + YAML 加载
│       ├── config/              # 牛市区间 / 全球资产 / 行情概览 YAML 配置
│       ├── core/                # 数据库、Redis、异常、日志、装饰器
│       ├── models/              # SQLModel 表定义
│       ├── schemas/             # Pydantic 请求 / 响应模型
│       ├── sources/             # 外部数据源客户端（baostock / 腾讯 / akshare）
│       ├── services/            # 业务逻辑（导入、分析、全球资产、行情概览）
│       └── routers/             # HTTP 路由（admin / analysis / meta）
└── frontend/
    └── src/
        ├── views/               # 4 个业务页面
        ├── api/                 # axios 封装与接口模块
        ├── components/          # 通用组件
        ├── router/              # 路由配置
        ├── store/               # Pinia 状态管理
        └── locale/              # 中 / 英文案
```

## 配置项

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| `DB_PATH` | `db/astock.db` | SQLite 库路径（相对 `backend/`） |
| `FASTAPI_PORT` | `8000` | 后端服务端口 |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis 连接地址 |
| `ASSET_PRICE_CACHE_TTL` | `86400` | 全球资产 / 行情缓存 TTL（秒） |
| `LOG_LEVEL` | `INFO` | 日志级别 |
