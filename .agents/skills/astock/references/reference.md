# Astock 详细参考

SKILL.md 的扩展材料；改 API、前端、部署、同步缓存时按需阅读。

## 深度文档

- 外部数据源 / sources 层 / 失败行为：[external-data.md](.agents/skills/astock/references/external-data.md)

## 关键文件索引

| 用途 | 路径 |
|------|------|
| FastAPI 入口 | `backend/astock/main.py` |
| 环境变量 + 阈值 | `backend/astock/config.py` |
| YAML 配置 | `backend/astock/config/{bull_markets,global_assets,market_overview}.yaml` |
| 异常与错误码 | `backend/astock/core/exceptions.py`、`core/error_codes.py`、`core/exception_handlers.py` |
| 数据库 / Redis | `backend/astock/core/database.py`、`core/redis_client.py` |
| SQLModel 表 | `backend/astock/models/` |
| Pydantic DTO | `backend/astock/schemas/` |
| 数据源客户端 | `backend/astock/sources/` |
| 业务逻辑 | `backend/astock/services/{import,analysis,global_asset,market_overview}_service.py` |
| 路由 | `backend/astock/routers/{admin,analysis,meta}.py` |
| 前端 API | `frontend/src/api/{interceptor,analysis,admin,meta}.ts` |
| 前端页面 | `frontend/src/views/{bull-market,turnover-rank,asset-price-levels,market-overview}/` |
| 管理刷新 | `frontend/src/components/admin-refresh-button/`、`hooks/admin-data-refresh.ts` |
| 同步状态格式化 | `frontend/src/utils/sync-meta.ts` |
| 数值格式化 | `frontend/src/utils/format.ts` |
| Docker | `docker/docker-compose.yml`、`Dockerfile.*`、`nginx.conf`、`gunicorn.docker.conf.py` |

---

<a id="api-contract"></a>

## API 契约（字段级）

所有响应统一信封 `ApiResponse{ code, message, data }`（`schemas/response.py`）：

```python
class ApiResponse(BaseModel, Generic[T]):
    code: int          # 0 = 成功，非 0 = 业务错误
    message: str
    data: T | None
```

前端拦截器（`src/api/interceptor.ts`）：`code !== 0` 弹 `Message.error(message)` 并 reject；成功 `return res`，视图中 `res.data` 即业务载荷。

**错误码**（`core/error_codes.py`）：`1001` 校验 / `1002` 权限 / `1003` 未找到 / `2001` 外部源 / `3001` 数据库 / `9000` 内部。HTTP 状态码通常仍为 200，靠 `code` 区分。

### 分析路由（prefix `/api/v1/analysis`）

#### GET `/bull-markets/point`

| Query | 类型 | 默认 | 约束 |
|-------|------|------|------|
| `threshold` | float | 4000 | `> 0` |

```jsonc
// data: BullMarketStatsResponse
{
  "threshold": 4000,
  "items": [
    { "market": "2007", "start": "2005-06-06", "end": "2007-10-16",
      "description": "...", "days": 120, "max_value": 6124.04 }
  ],
  "total_days": 300
}
```
`items` 按 `end` 倒序；`max_value` 为区间内最大收盘点位。

#### GET `/bull-markets/turnover`

| Query | 类型 | 默认 | 约束 |
|-------|------|------|------|
| `threshold` | float | 2e12 | `> 0` |

结构与 point 相同；`max_value` 为区间最大合计成交额（元）。

#### GET `/turnover/ranking`

| Query | 类型 | 默认 | 约束 |
|-------|------|------|------|
| `top` | int | 20 | 1-100 |
| `bull_market` | str? | — | 牛市 name 或 `all`/`None` |

```jsonc
{
  "top": 20, "bull_market": null,
  "items": [
    { "rank": 1, "date": "2015-06-08",
      "sh_amount": 1.3e12, "sz_amount": 1.1e12, "turnover": 2.4e12 }
  ]
}
```

#### GET `/stock/ranking`

| Query | 类型 | 默认 | 约束 |
|-------|------|------|------|
| `top` | int | 20 | 1-100 |
| `bull_market` | str? | — | 同上 |

```jsonc
{
  "items": [
    { "rank": 1, "date": "2015-06-08", "code": "600519", "name": "贵州茅台", "amount": 5.6e10 }
  ]
}
```

#### GET `/asset-price-levels`

| Query | 类型 | 默认 |
|-------|------|------|
| `force_refresh` | bool | false |

```jsonc
{
  "last_synced_at": "...", "as_of": "...", "latest_trading_date": "...",
  "items": [
    { "ticker": "AAPL", "name": "苹果", "asset_type": "stock",
      "current_price": 230.5, "all_time_high": 260.1, "ath_date": "2025-12-25",
      "percentage_diff": -11.4, "ath_days": 190,
      "daily_change": 1.2, "weekly_change": -0.8,
      "conclusion": "适度回调", "data_pending": false }
  ],
  "cache_errors": ["NVDA: 拉取失败"]
}
```
`conclusion`：`接近历史高点`(|<5|) / `适度回调`(<20) / `显著回调`(<50) / `深度回调`(≥50) / `待接入`。

#### GET `/market-overview`

| Query | 类型 | 默认 |
|-------|------|------|
| `force_refresh` | bool | false |

```jsonc
{
  "as_of": "...", "latest_trading_date": "...",
  "categories": [
    { "key": "us_stock", "name": "美股指数",
      "items": [
        { "key": "dow", "name": "道琼斯", "code": ".DJI",
          "current_price": 43000, "daily_change": 0.3, "weekly_change": 1.1,
          "period_start": "...", "period_end": "...", "error": null }
      ] }
  ],
  "errors": []
}
```

### Admin 路由（prefix `/api/v1/admin`）

#### POST `/data/import`

| Query | 类型 | 默认 | 取值 |
|-------|------|------|------|
| `dataset` | str | `all` | `turnover`/`point`/`stock`/`global_assets`/`all` |

单数据集响应 `data`：
```jsonc
{
  "imported": 123, "total": 4567, "last_date": "...",
  "last_synced_at": "...", "status": "success",
  "source_errors": {}, "elapsed": 12.34
}
```
`all` 时 `data` 为 `{turnover, point, stock, global_assets, status}` 逐项聚合。

#### GET `/data/sync-status`

```jsonc
{
  "turnover":  { "last_synced_date": "...", "last_synced_at": "...", "status": "success" },
  "point":     { ... },
  "stock":     { ... },
  "global_assets": { ... }
}
```

### `bull_market` 参数取值

- 牛市 `name`（如 `2024`）：只统计该区间
- `all` 或缺省：全区间
- 未知值 → `AppError`（`analysis_service._get_bull_market_period`）

---

<a id="sync-cache"></a>

## 增量同步与缓存

### sync_meta 水位表

主键 `table_name`，记录每个数据集同步水位：

| 字段 | 说明 |
|------|------|
| `last_synced_date` | 增量起点（下次从此日期之后拉取） |
| `last_synced_at` | 最近同步时间戳 |
| `last_status` | `success` / `partial_failure` / `failed` |
| `last_error` | 最近错误信息 |

增量起点 `get_sync_start_date`：读 `sync_meta.last_synced_date`，缺省 `START_DATE="2005-01-01"`。

### 批量 upsert

`import_service._batch_upsert`：SQLite `ON CONFLICT DO UPDATE`，批量 500（`BATCH_SIZE`）。

- `per_batch`：每批提交（默认）
- `single`：单条提交（调试）

`point` / `turnover` 走 `_import_simple_dataset`：baostock 拉取 → upsert → 更新 sync_meta。

### stock 数据集（最复杂）

1. 以 turnover 表最新日期为 `as_of_date`
2. `fetch_all_stock_codes` → `tencent.fetch_market_caps` → 过滤 `market_cap > MARKET_CAP_THRESHOLD`
3. ProcessPool（4 worker）并发拉个股 `date, amount` 历史
4. 仅保留 `amount >= STOCK_TURNOVER_SLICE_THRESHOLD`（300 亿/日）切片
5. 每 5000 条 flush upsert

### global_assets 数据集

`global_asset_service.refresh_asset_highs`：今日已成功则跳过；akshare 串行拉 ATH → upsert `asset_high` → 写 Redis。

### Redis 缓存

| 用途 | TTL | Key |
|------|-----|-----|
| 全球资产最近收盘价 | `ASSET_PRICE_CACHE_TTL=86400` | 按 ticker |
| 市场概览成功结果 | TTL 内复用 | 按类目 key |
| 失败标记 | `MARKET_OVERVIEW_FAILURE_TTL=300` / `REDIS_RETRY_COOLDOWN=60` | 失败项 |

### 新增数据集约定

1. `ImportDataset` 枚举（`schemas/imports.py`）加值
2. `import_service.import_dataset` 加分支
3. `get_sync_status` 加返回项
4. 需要缓存时在 Redis 层定义 Key/TTL，遵循「成功复用 + 失败冷却」
5. 同步状态写回 `sync_meta`

外部源细节见 [external-data.md](.agents/skills/astock/references/external-data.md)。

---

<a id="frontend"></a>

## 前端开发约定

### 技术栈与入口

- Vue3 + Vite + TypeScript + Arco Design Pro Vue
- 构建：`frontend/config/vite.config.{base,dev}.ts`；主题 `src/config/settings.json`

### API 层

- `axios.defaults.baseURL = '/api/v1'`（**硬编码**，未读 `VITE_API_BASE_URL`）
- `src/api/analysis.ts`：分析接口 + TS interface
- `src/api/admin.ts`：`refreshAllDataApi()`(5min 超时)、`refreshGlobalAssetsApi()`、`fetchSyncStatusApi()`

### 路由（`router/routes/modules/main.ts`）

`/` → `/bull-market`，4 子页面，`requiresAuth: false`：

| 路径 | 视图 | 菜单 icon |
|------|------|-----------|
| `/bull-market` | `views/bull-market/` | bar-chart |
| `/turnover-rank` | `views/turnover-rank/` | sort |
| `/asset-price-levels` | `views/asset-price-levels/` | fire |
| `/market-overview` | `views/market-overview/` | apps |

### 页面写法

**全部 Arco `a-table`**，无图表库。通用：顶部筛选 + 卡片 extra 显示 sync 状态（`formatSyncMeta`）；涨跌色正 `#00b42a` / 负 `#f53f3f`；工具 `@/utils/format`。

- **bull-market**：双阈值输入，并发请求 point + turnover 合并单表
- **turnover-rank**：两列并排大盘/个股排名，`DEFAULT_TOP=20`
- **asset-price-levels**：贵金属分隔行；`FOCUSED_TICKERS` 打 Tag；按 `percentage_diff` 排序
- **market-overview**：类目分隔行 + 聚合 periodText；失败项「数据获取失败」

### 管理刷新

- 导航栏 `admin-refresh-button`：前端密码门（`VITE_ADMIN_REFRESH_PASSWORD`），**后端无鉴权**
- 开发默认密码见 `.env.development`；生产经 Docker 构建期注入
- `useAdminDataRefresh` hook 处理 success / partial_failure / failed 通知

### 环境变量

- `.env.development`：`VITE_API_BASE_URL=`(空)、`VITE_ADMIN_REFRESH_PASSWORD`
- `.env.production`：`VITE_ADMIN_REFRESH_PASSWORD=`(空)
- 生产 API 依赖 nginx 反代 `/api`，非运行时注入

### 代码规范

ESLint(airbnb-base) + Prettier + Stylelint；husky + commitlint；组件按需 `unplugin-vue-components`。

---

<a id="deployment"></a>

## 部署与 Docker

### 服务编排（`docker/docker-compose.yml`）

| 服务 | 说明 |
|------|------|
| redis | `redis:7-alpine`，healthcheck，卷 `redis_data` |
| backend | `python:3.13-slim`，gunicorn，端口 `${BACKEND_PUBLISH_PORT:-8002}:8000` |
| frontend | node 22 构建 + nginx:stable-alpine，端口 `${FRONTEND_PUBLISH_PORT:-8082}:8080` |

backend 挂载 `${SQLITE_HOST_DIR:-./sqlite-data}:/app/data` + `log_data:/var/log/astock`。

### nginx.conf

- `/api` → `backend:8000`，`proxy_read_timeout 300s`（导入耗时长）
- `/` → SPA `try_files`

### 配置项速查

| 配置 | 默认 | 说明 |
|------|------|------|
| `DB_PATH` | `db/astock.db`(dev) / `/app/data/astock.db`(prod) | SQLite |
| `REDIS_URL` | `redis://redis:6379/0`(prod) | Redis |
| `START_DATE` | 2005-01-01 | 历史起始 |
| `GUNICORN_WORKERS/TIMEOUT` | — | 生产 worker |

### 部署约定

1. 业务范围改 YAML + `config.py` 阈值，不动镜像
2. 前端敏感变量构建期注入，不入仓
3. SQLite 卷必须持久化
4. 改前端须 **重建 frontend 镜像**（仅 backend 重建不更新页面）

### Dev vs Prod

| 项 | 开发 | 生产（Docker） |
|----|------|----------------|
| 后端 | uvicorn reload `:8000` | gunicorn |
| 前端 | Vite dev proxy `/api` | nginx 反代 |
| API baseURL | `/api/v1` 硬编码 | 同源 nginx |

---

## 变更影响面速查

| 你改了什么 | 还要联动检查 |
|-----------|----------------|
| `sources/*` | 对应 `import_service` / `global_asset_service` / `market_overview_service`；[external-data.md](.agents/skills/astock/references/external-data.md) |
| `models/` | `import_service._batch_upsert`、sync_meta、`get_sync_status` |
| `schemas/` | 前端 `src/api/*.ts` interface、Swagger |
| `config/*.yaml` | 重启 backend；前端下拉/展示项可能变化 |
| `analysis_service` | 前端对应页面阈值/列 |
| 新增 API | `routers/` → `schemas/` → `frontend/src/api/` → `views/` |
| 新增前端页 | `router/routes/modules/main.ts` + locale |
| `docker/nginx.conf` | frontend 重建、proxy 超时 |

## 常用排障命令

```bash
# 后端开发
cd backend && python -m astock.main

# 导入全部数据
curl -X POST "http://localhost:8000/api/v1/admin/data/import?dataset=all"

# 同步状态
curl "http://localhost:8000/api/v1/admin/data/sync-status"

# Docker 状态
docker compose -f docker/docker-compose.yml ps

# 改前端后重建
docker compose -f docker/docker-compose.yml build frontend && docker compose -f docker/docker-compose.yml up -d frontend
```
