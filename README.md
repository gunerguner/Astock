# Astock

Astock 是一个 A 股历史行情数据平台，基于 FastAPI + SQLite 构建，支持从 BaoStock / 腾讯行情增量拉取数据并缓存到本地数据库。

## 功能特性

- 全市场成交额（上证 + 深证 + 创业板）增量导入与 SQLite 缓存
- 上证指数收盘价增量导入与缓存
- 大市值个股高水位成交额切片（≥300亿）导入
- 统一 REST API，支持按数据集类型触发导入

## 数据源说明

| 数据 | 来源 | 说明 |
| --- | --- | --- |
| 指数成交额 / 点位 | BaoStock | `astock/sources/baostock_client.py` |
| 全市场股票代码清单 | BaoStock `query_all_stock` | 沪深主板/中小板/创业板/科创板，排除指数、基金、B股 |
| 个股总市值快照 | 腾讯行情 `qt.gtimg.cn` | 无需鉴权，批量查询，用于大市值筛选 |
| 个股历史日线成交额 | BaoStock `query_history_k_data_plus` | 替代 akshare，同一数据源，更稳定 |

> 曾评估 akshare（东方财富数据源）用于大市值快照与个股日线，实测在当前网络环境下请求经常被中断（`Connection aborted`），根因在东方财富接口侧的限流/反爬，绕过 akshare 直连同一接口依旧不稳定。现已改为 BaoStock + 腾讯行情组合方案，两者均验证稳定可用。

## 环境要求

- Python 3.10+
- 可访问 BaoStock / 腾讯行情数据服务的网络环境

## 安装依赖

```bash
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
python main.py
```

默认监听 `http://0.0.0.0:8000`，可通过 `.env` 中 `FASTAPI_PORT` 修改。

## API 接口

### 数据导入

```bash
# 导入全部数据集（turnover → point → stock）
curl -X POST "http://localhost:8000/api/v1/admin/data/import?dataset=all"

# 仅导入全市场成交额
curl -X POST "http://localhost:8000/api/v1/admin/data/import?dataset=turnover"

# 仅导入上证点位
curl -X POST "http://localhost:8000/api/v1/admin/data/import?dataset=point"

# 仅导入个股成交额切片
curl -X POST "http://localhost:8000/api/v1/admin/data/import?dataset=stock"
```

响应格式：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "imported": 123,
    "total": 4567,
    "last_date": "2026-07-04",
    "status": "success",
    "elapsed": 12.34
  }
}
```

### 交互式文档

启动后访问 [http://localhost:8000/docs](http://localhost:8000/docs) 查看 Swagger UI。

## 项目结构

```text
.
├── main.py                 # uvicorn 启动入口
├── astock/
│   ├── main.py             # FastAPI app
│   ├── config.py           # 环境变量 + 业务常量
│   ├── core/               # 数据库、异常、日志、装饰器
│   ├── models/             # SQLModel 表定义
│   ├── schemas/            # Pydantic 请求/响应
│   ├── sources/            # 外部数据源客户端
│   ├── services/           # 业务逻辑
│   ├── routers/            # HTTP 路由
│   └── common/             # 类型定义
├── cache/astock.db         # SQLite 缓存库
├── db.md                   # 技术方案文档
└── requirements.txt
```

## 配置说明

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| `DB_PATH` | `cache/astock.db` | SQLite 库路径 |
| `FASTAPI_PORT` | `8000` | 服务端口 |
| `START_DATE` | `2005-01-01` | 历史数据起始日期 |
| `CANDIDATE_DAYS` | `200` | 个股扫描候选交易日数 |
| `MARKET_CAP_THRESHOLD` | `1000亿` | 大市值过滤阈值 |
| `STOCK_TURNOVER_SLICE_THRESHOLD` | `300亿` | 个股切片入库阈值 |

## 注意事项

- SQLite 库文件 `cache/astock.db` 提交到 git，团队 clone 后增量更新即可
- WAL 模式产生的 `-wal` / `-shm` 文件已加入 `.gitignore`
- 个股导入（`dataset=stock`）需逐只拉取日线，可能耗时数分钟
