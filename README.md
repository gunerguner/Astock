# Astock

Astock 是一个 A 股历史行情数据平台，基于 FastAPI + SQLite 构建，支持从 BaoStock / 腾讯行情增量拉取数据并缓存到本地数据库。

## 功能特性

- 全市场成交额（上证 + 深证 + 创业板）增量导入与 SQLite 缓存
- 上证指数收盘价增量导入与缓存
- 大市值个股高水位成交额切片（≥300亿）导入
- 统一 REST API，支持按数据集类型触发导入
- Web 前端：牛市点位/成交额统计、大盘与个股成交额排名

## 数据源说明


| 数据         | 来源                                   | 说明                                  |
| ---------- | ------------------------------------ | ----------------------------------- |
| 指数成交额 / 点位 | BaoStock                             | `astock/sources/baostock_client.py` |
| 全市场股票代码清单  | BaoStock `query_all_stock`           | 沪深主板/中小板/创业板/科创板，排除指数、基金、B股         |
| 个股总市值快照    | 腾讯行情 `qt.gtimg.cn`                   | 无需鉴权，批量查询，用于大市值筛选                   |
| 个股历史日线成交额  | BaoStock `query_history_k_data_plus` | 替代 akshare，同一数据源，更稳定                |


> 曾评估 akshare（东方财富数据源）用于大市值快照与个股日线，实测在当前网络环境下请求经常被中断（`Connection aborted`），根因在东方财富接口侧的限流/反爬，绕过 akshare 直连同一接口依旧不稳定。现已改为 BaoStock + 腾讯行情组合方案，两者均验证稳定可用。



## 环境要求

- Python 3.10+
- Node.js 14+、pnpm 8+（前端开发）
- 可访问 BaoStock / 腾讯行情数据服务的网络环境



## 安装依赖

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

复制环境变量配置：

```bash
cp .env.example .env
```



## 启动服务

```bash
cd backend
python -m astock.main
```

默认监听 `http://0.0.0.0:8000`，可通过 `.env` 中 `FASTAPI_PORT` 修改。

### 启动前端

```bash
cd frontend
pnpm install
pnpm dev
```

前端默认通过 Vite proxy 将 `/api` 代理到 `http://localhost:8000`，访问开发地址即可使用页面：

- `/bull-market` — 牛市点位统计 + 牛市成交额统计
- `/turnover-rank` — 大盘成交额排名 + 个股成交额排名



## API 接口



### 数据导入（SSE 流式）

```bash
# 导入全部数据集（turnover → point → stock → global_assets）
curl -N -X POST "http://localhost:8000/api/v1/admin/data/import/stream?dataset=all"

# 仅导入全市场成交额
curl -N -X POST "http://localhost:8000/api/v1/admin/data/import/stream?dataset=turnover"

# 仅导入指数点位
curl -N -X POST "http://localhost:8000/api/v1/admin/data/import/stream?dataset=point"

# 仅导入个股成交额切片
curl -N -X POST "http://localhost:8000/api/v1/admin/data/import/stream?dataset=stock"
```

`done` 事件 payload 示例（单 dataset）：

```json
{
  "imported": 123,
  "total": 4567,
  "last_date": "2026-07-04",
  "status": "success",
  "elapsed": 12.34
}
```



### 分析查询

```bash
# 牛市点位统计（threshold 单位：点）
curl "http://localhost:8000/api/v1/analysis/bull-markets/point?threshold=4000"

# 牛市成交额统计（threshold 单位：元，默认 2 万亿）
curl "http://localhost:8000/api/v1/analysis/bull-markets/turnover?threshold=2000000000000"

# 大盘成交额 TopN（可选 bull_market 过滤牛市区间）
curl "http://localhost:8000/api/v1/analysis/turnover/ranking?top=20&bull_market=2024年牛市"

# 个股成交额 TopN
curl "http://localhost:8000/api/v1/analysis/stock/ranking?top=20"
```



### 交互式文档

启动后访问 [http://localhost:8000/docs](http://localhost:8000/docs) 查看 Swagger UI。

## 项目结构

```text
.
├── backend/
│   ├── astock/
│   │   ├── main.py         # FastAPI app + 本地开发启动入口
│   │   ├── config.py       # 环境变量 + 业务常量
│   │   ├── core/           # 数据库、异常、日志、装饰器
│   │   ├── models/         # SQLModel 表定义
│   │   ├── schemas/        # Pydantic 请求/响应
│   │   ├── sources/        # 外部数据源客户端
│   │   ├── services/       # 业务逻辑
│   │   └── routers/        # HTTP 路由
│   ├── db/astock.db        # SQLite 数据库
│   ├── logs/               # 应用日志
│   └── requirements.txt
└── frontend/               # Vue3 + Arco Design Pro 前端
```



## 配置说明


| 配置项                              | 默认值            | 说明                           |
| -------------------------------- | -------------- | ---------------------------- |
| `DB_PATH`                        | `db/astock.db` | SQLite 库路径（相对 `backend/` 目录） |
| `FASTAPI_PORT`                   | `8000`         | 服务端口                         |
| `START_DATE`                     | `2005-01-01`   | 历史数据起始日期                     |
| `CANDIDATE_DAYS`                 | `200`          | 个股扫描候选交易日数                   |
| `MARKET_CAP_THRESHOLD`           | `1000亿`        | 大市值过滤阈值                      |
| `STOCK_TURNOVER_SLICE_THRESHOLD` | `300亿`         | 个股切片入库阈值                     |


