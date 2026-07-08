# Astock 详细参考

SKILL.md 的扩展材料；改 API、前端、部署、同步缓存时按需阅读。

## 深度文档

- 外部数据源 / sources 层 / 失败行为：[external-data.md](.agents/skills/astock/references/external-data.md)

## 关键文件索引

| 用途 | 路径 |
|------|------|
| FastAPI 入口 | `backend/astock/main.py` |
| 环境变量 + 阈值 | `backend/astock/config.py` |
| YAML 配置 | `backend/astock/config/{bull_markets,point_indices,global_assets,market_overview}.yaml` |
| 异常与错误码 | `backend/astock/core/exceptions.py`、`core/error_codes.py`、`core/exception_handlers.py` |
| 数据库 / Redis | `backend/astock/core/database.py`、`core/redis_client.py` |
| SSE 进度 | `backend/astock/core/progress.py` |
| SQLModel 表 | `backend/astock/models/` |
| Pydantic DTO | `backend/astock/schemas/` |
| 数据源 | `backend/astock/sources/{baostock,market_overview}/`、`akshare_client.py`、`tencent_client.py` |
| 导入编排 | `backend/astock/services/import_orchestrator.py`、`services/imports/`、`sync_status_service.py` |
| 分析查询 | `backend/astock/services/queries/` |
| 全球资产 | `backend/astock/services/global_asset/` |
| 市场概览 | `backend/astock/services/market_overview_service.py` |
| 路由 | `backend/astock/routers/{admin,analysis,meta}.py` |
| 前端 API | `frontend/src/api/{interceptor,analysis,admin,meta}.ts` |
| 前端页面 | `frontend/src/views/{bull-market,turnover-rank,asset-price-levels,market-overview}/` |
| 管理刷新 | `admin-refresh-button/`、`refresh-progress-modal/`、`hooks/admin-data-refresh.ts` |
| SSE / 页面联动 | `frontend/src/utils/{sse-stream,data-refresh}.ts` |
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

多指数阈值，各 Query 默认取自 `point_indices.yaml`：

| Query | 类型 | 默认 | 约束 |
|-------|------|------|------|
| `threshold_000001` | float | 4000 | `> 0` |
| `threshold_000300` | float | 4500 | `> 0` |
| `threshold_399006` | float | 2500 | `> 0` |
| `threshold_000688` | float | 1200 | `> 0` |

```jsonc
// data: MultiIndexPointStatsResponse
{
  "indices": [
    {
      "index_code": "000001",
      "index_name": "上证指数",
      "threshold": 4000,
      "items": [
        { "market": "2007", "start": "2005-06-06", "end": "2007-10-16",
          "description": "...", "days": 120, "max_value": 6124.04, "not_available": false }
      ],
      "total_days": 300
    }
  ]
}
```
`items` 按 `end` 倒序；指数历史不足时 `not_available=true`。

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

#### POST `/data/import/stream`

| Query | 类型 | 默认 | 取值 |
|-------|------|------|------|
| `dataset` | str | `all` | `turnover`/`point`/`stock`/`global_assets`/`all` |

返回 `text/event-stream`。事件类型：

| event | 说明 |
|-------|------|
| `progress` | 阶段进度（`phase`/`current`/`total`/`imported`/`elapsed`） |
| `done` | 导入完成；单 dataset 为 `ImportResultItem` 形字段，`all` 为 `{turnover, point, stock, global_assets, status}` |
| `error` | 致命错误 |
| `ping` | 保活（个股阶段每 100 只） |

前端通过 `refreshAllDataStream()`（`admin.ts`）消费，`useAdminDataRefresh` 驱动四阶段进度弹窗。

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
- 未知值 → `AppError`（`services/queries/_common.get_bull_market_period`）

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

`sync_store.batch_upsert`：SQLite `ON CONFLICT DO UPDATE`，批量 500（`BATCH_SIZE`）。

- `per_batch`：每批提交（默认）
- `single`：单条提交（调试）

`turnover` 走 `imports/turnover_importer`；`point` 按 `point_indices.yaml` 循环多指数导入（baostock + akshare 科创50）。

### stock 数据集（最复杂）

实现于 `services/imports/stock_importer.py`（`StockImportContext`）：

1. 以 turnover 表最新日期为 `as_of_date`
2. `fetch_all_stock_codes` → `tencent.fetch_market_caps` → 过滤 `market_cap > MARKET_CAP_THRESHOLD`
3. ProcessPool（4 worker，`configure_worker_socket` 初始化）并发拉个股 `date, amount` 历史
4. 仅保留 `amount >= STOCK_TURNOVER_SLICE_THRESHOLD`（300 亿/日）切片
5. 每 5000 条 flush upsert；SSE 每 20 只上报进度

### global_assets 数据集

`services/global_asset/refresh.py`：`refresh_asset_highs` 今日已成功则跳过；akshare 串行拉 ATH → upsert `asset_high` → 写 Redis。

### Redis 缓存

| 用途 | TTL | Key |
|------|-----|-----|
| 全球资产最近收盘价 | `ASSET_PRICE_CACHE_TTL=86400` | 按 ticker |
| 市场概览成功结果 | TTL 内复用 | 按类目 key |
| 失败标记 | `MARKET_OVERVIEW_FAILURE_TTL=300` / `REDIS_RETRY_COOLDOWN=60` | 失败项 |

### 新增数据集约定

1. `ImportDataset` 枚举（`schemas/imports.py`）加值
2. `services/imports/` 新增 importer + `import_orchestrator` 加分支
3. `sync_status_service` 加返回项
4. 需要缓存时在 Redis 层定义 Key/TTL，遵循「成功复用 + 失败冷却」
5. 同步状态写回 `sync_meta`；导入结果内部用 `ImportResult` dataclass，对外 `to_dict()`

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
- `src/api/admin.ts`：`refreshAllDataStream()`（SSE）、`fetchSyncStatusApi()`

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

- **bull-market**：四指数独立阈值，合并单表展示；`data-refresh` 事件触发 reload
- **turnover-rank**：两列并排大盘/个股排名，`DEFAULT_TOP=20`
- **asset-price-levels**：贵金属分隔行；`FOCUSED_TICKERS` 打 Tag；按 `percentage_diff` 排序
- **market-overview**：类目分隔行 + 聚合 periodText；失败项「数据获取失败」

### 管理刷新

- 导航栏 `admin-refresh-button`：前端密码门（`VITE_ADMIN_REFRESH_PASSWORD`），**后端无鉴权**
- 开发默认密码见 `.env.development`；生产经 Docker 构建期注入
- `useAdminDataRefresh` + `refresh-progress-modal`：SSE 四阶段进度弹窗；完成后 `emitDataRefresh` 通知各页 reload

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
| `sources/*` | 对应 `services/imports/` / `global_asset/` / `market_overview_service`；[external-data.md](.agents/skills/astock/references/external-data.md) |
| `models/` | `sync_store.batch_upsert`、`sync_status_service` |
| `schemas/` | 前端 `src/api/*.ts` interface、Swagger |
| `config/*.yaml` | 重启 backend；前端下拉/展示项可能变化 |
| `services/queries/` | 前端对应页面阈值/列 |
| 新增 API | `routers/` → `schemas/` → `frontend/src/api/` → `views/` |
| 新增前端页 | `router/routes/modules/main.ts` + locale |
| `docker/nginx.conf` | frontend 重建、proxy 超时（SSE 长连接） |

## 常用排障命令

```bash
# 后端开发
cd backend && python -m astock.main

# SSE 流式导入
curl -N -X POST "http://localhost:8000/api/v1/admin/data/import/stream?dataset=all"

# 同步状态
curl "http://localhost:8000/api/v1/admin/data/sync-status"

# Docker 状态
docker compose -f docker/docker-compose.yml ps

# 改前端后重建
docker compose -f docker/docker-compose.yml build frontend && docker compose -f docker/docker-compose.yml up -d frontend
```
