# Astock 详细参考

SKILL.md 的扩展材料；改 API、前端、部署、同步缓存时按需阅读。

## 深度文档

- 外部数据源 / providers + datasets 层 / 失败行为：[external-data.md](.agents/skills/astock/references/external-data.md)

## 关键文件索引

| 用途 | 路径 |
|------|------|
| FastAPI 入口 | `backend/astock/main.py` |
| 环境变量 + 阈值 + TypedDict | `backend/astock/config.py`（`PointIndexConfig` / `GlobalAssetConfig` / …） |
| YAML 配置 | `backend/astock/config/settings.yaml` + `{bull_markets,point_indices,global_assets,market_overview}.yaml` |
| 异常与错误码 | `backend/astock/core/errors.py`、`routers/exception_handlers.py` |
| 日期/结算/涨跌纯函数 | `backend/astock/core/datetime_utils.py`（含 `today_local_date`）、`core/price_utils.py`（含 `pct_change`）、`core/trading_calendar.py` |
| 数据库 / Redis | `backend/astock/core/database.py`、`core/redis_client.py`（网关）；领域 key 在 `services/cache/keys.py` |
| SSE 进度 | `backend/astock/services/imports/progress.py` |
| SQLModel 表 | `backend/astock/models/` |
| Pydantic DTO | `backend/astock/schemas/` |
| 数据源 | `backend/astock/providers/` + `backend/astock/datasets/` |
| 导入编排 | `backend/astock/services/import_orchestrator.py`、`services/imports/`、`services/sync/status.py` |
| 导入结果类型 | `backend/astock/services/sync/results.py`（`ImportResult`、`ImportBatchResult` + 组装助手） |
| 同步 / 缓存 | `backend/astock/services/sync/{store,status,results}.py`、`services/cache/{closes,asset_prices}.py` |
| 分析查询 | `backend/astock/services/queries/`（牛市/排名/宏观/全球资产/市场概览；共享 `_common.py`） |
| 全球资产 | `backend/astock/services/imports/global_assets.py`（写）、`services/queries/global_asset.py`（读） |
| 市场概览 | `backend/astock/services/queries/market_overview/` |
| 宏观长表 / 导入 / 查询 | `backend/astock/models/macro.py`、`datasets/macro/`（共享 `common.py`：`merge_domain_sources` / `with_fallback` / `months_behind`）、`services/imports/{_macro_domain,cn_macro,us_macro}.py`、`services/queries/{cn_macro,us_macro}.py` |
| 路由 | `backend/astock/routers/{admin,analysis}.py` |
| 前端 API | `frontend/src/api/{request,analysis,admin}.ts` |
| 前端页面 | `frontend/src/views/{bull-market,turnover-rank,asset-price-levels,market-overview,cn-macro-data,us-macro-data}/` |
| 宏观图表共享 Hook | `frontend/src/hooks/use-macro-line-chart.ts` |
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

前端请求封装（`src/api/request.ts`）：`code !== 0` 弹 `Message.error(message)` 并 reject；成功直接返回业务 `data`，因此各 API 函数的 Promise 类型就是业务载荷。

**错误码**（`core/errors.py`）：`1001` 校验 / `1002` 权限 / `1003` 未找到 / `2001` 外部源 / `3001` 数据库 / `9000` 内部。HTTP 状态码通常仍为 200，靠 `code` 区分。

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
        { "market": "2007-2009", "start": "2005-06-06", "end": "2010-06-30",
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
      "sse_amount": 1.3e12, "szse_amount": 1.1e12, "turnover": 2.4e12 }
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
      "conclusion": "moderatePullback" }
  ],
  "cache_errors": ["NVDA: 拉取失败"]
}
```
`conclusion` 返回枚举 key：`nearAth`（距 ATH <5%）/ `moderatePullback`（<20%）/ `significantPullback`（<50%）/ `deepPullback`（≥50%）/ `pending`；中文标签由前端 locale 映射。仅待接入行带 `data_pending: true`。

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
          "period_start": "...", "period_end": "..." }
      ] }
  ],
  "errors": []
}
```

#### GET `/us-macro`

| Query | 类型 | 默认 | 约束 |
|-------|------|------|------|
| `start` | str | `US_MACRO_START_PERIOD`（默认 `2020-06`） | 长度恰为 7；应传 `YYYY-MM` |

```jsonc
{
  "start": "2020-06",
  "latest_period": "2026-06",
  "last_synced_at": "2026-07-15T10:00:00+08:00",
  "points": [
    {
      "period": "2020-06",
      "cpi_yoy": 0.6,
      "fed_rate_upper": 0.25
    }
  ]
}
```

- `points` 按月份升序；缺失指标为 `null`。
- 只读 `macro_value`，页面查询不访问外部源。
- 为避免图表尾部出现只有利率、尚无 CPI 的月份，返回值会丢弃晚于最新 CPI 月份的纯利率点；`latest_period` 优先取最新 CPI 月份。

#### GET `/cn-macro`

| Query | 类型 | 默认 | 约束 |
|-------|------|------|------|
| `start` | str | `CN_MACRO_START_PERIOD` | 长度恰为 7；应传 `YYYY-MM` |

`CN_MACRO_START_PERIOD` 在 `settings.yaml` 留空时，进程启动时动态计算为北京时间当前月份往前 60 个月。

```jsonc
{
  "start": "2021-07",
  "latest_period": "2026-06",
  "last_synced_at": "2026-07-15T10:00:00+08:00",
  "points": [
    {
      "period": "2021-07",
      "cpi_yoy": 1.0,
      "ppi_yoy": 9.0,
      "pmi_manufacturing": 50.4,
      "pmi_non_manufacturing": 53.3,
      "consumer_confidence": 117.8
    }
  ]
}
```

`points` 按月份升序，任一子指标缺失时保留该月份并将对应字段置为 `null`；`latest_period` 取最后一个至少含一项有效指标的月份。

### Admin 路由（prefix `/api/v1/admin`）

#### POST `/data/import/stream`

| Query | 类型 | 默认 | 取值 |
|-------|------|------|------|
| `dataset` | str | `all` | `turnover`/`point`/`stock`/`global_assets`/`us_macro`/`cn_macro`/`all` |

返回 `text/event-stream`。事件类型：

| event | 说明 |
|-------|------|
| `progress` | 阶段进度（`phase`/`current`/`total`/`imported`/`elapsed`） |
| `done` | 导入完成；载荷为 `ImportResult.to_dict()`（单 dataset）或 `ImportBatchResult.to_dict()`（`all`：各阶段 dict + 顶层 `status`） |
| `error` | 致命错误 |
| `ping` | 保活（个股阶段每 100 只） |

后端内部全程使用 `ImportResult` dataclass（定义于 `services/sync/results.py`）；仅 SSE 序列化边界调用 `.to_dict()`。`ProgressReporter.phase_done` 只收 `ImportResult`，`done` 收实现 `to_dict()` 的对象（`ImportResult` / `ImportBatchResult`）。

前端通过 `refreshAllDataStream()`（`admin.ts`）消费，`useAdminDataRefresh` 按 `turnover → point → stock → global_assets → us_macro → cn_macro` 驱动六阶段进度弹窗。全部阶段在后端主流程串行执行；前三段共享 baostock session。

#### GET `/data/sync-status`

```jsonc
{
  "turnover":  { "last_synced_date": "...", "last_synced_at": "...", "status": "success" },
  "point":     { ... },
  "stock":     { ... },
  "global_assets": { ... },
  "us_macro":  { ... },
  "cn_macro":  { ... }
}
```

### `bull_market` 参数取值

- 牛市 `name`（如 `2024`）：只统计该区间
- `all` 或缺省：全区间
- 未知值 → `AppError`（`code=1001`，`services/queries/_common.get_bull_market_period`）；路由层不再 `try/except ValueError`

服务层业务失败统一抛 `AppError` / `ExternalSourceAppError`（如全球资产空表、导入 FAILED），由 `routers/exception_handlers` 转成信封响应。

---

<a id="sync-cache"></a>

## 增量同步与缓存

### sync_meta 水位表

主键 `table_name`，记录每个数据集同步水位：

| 字段 | 说明 |
|------|------|
| `last_synced_date` | 数据集水位；日频为最后交易日，宏观为最新 CPI 月份 |
| `last_synced_at` | 最近同步时间戳 |
| `last_status` | `success` / `partial_failure` / `failed` |
| `last_error` | 最近错误信息 |

日频增量起点 `get_sync_start_date`：读 `sync_meta.last_synced_date` 的**次日**（`+1` 日历日，避免重复 upsert 已同步日）；缺省 `START_DATE="2005-01-01"`。`should_skip_daily_sync` 仅在上次状态为 `success` 且水位已覆盖 `last_settled_date("cn")` 时跳过。

### 批量 upsert

`services/sync/store.batch_upsert`：SQLite `ON CONFLICT DO UPDATE`，默认按 `DEFAULT_UPSERT_BATCH_SIZE=500` 分批执行，全部批次完成后统一 commit，异常时 rollback。

`turnover` / 单指数 `point` 走 `imports/pipeline.run_daily_import`；`point` 外层按 `point_indices.yaml` 循环多指数（baostock + akshare 科创50）。

### stock 数据集

实现于 `services/imports/stock.py`：

1. 以 turnover 表最新日期为 `as_of_date`；缺口日取 turnover 中 `(last_synced, as_of]`
2. 缺口整段共用一次 `baostock_session`；`query_all_stock(as_of)` 名称拉一次复用
3. 逐日 `query_daily_history_k_AStock`（≥0.9.3）→ 当日 amount TopN（`STOCK_SLICE_TOP_N`，默认 20）→ upsert
4. 全部缺口日成功才推进 `sync_meta`；SSE 按日上报进度

### global_assets 数据集

`services/imports/global_assets.py`：`refresh_asset_highs` 在上次状态成功、`asset_high` 非空且水位同时覆盖中美最近结算日时跳过；否则 akshare 串行拉 ATH → upsert `asset_high` → 写 Redis（`services/cache/asset_prices`）。

### macro 月频数据集

中美宏观共用 `services/imports/_macro_domain.run_macro_import`，统一写入 `macro_value` 长表：

| 项 | 说明 |
|----|------|
| 主键 | `(region, period, metric)`；`region=cn/us`，`period=YYYY-MM` |
| 水位 | `sync_meta.cn_macro` / `sync_meta.us_macro`，`last_synced_date` 存最新有效 CPI 月份（`WATERMARK_METRIC="cpi_yoy"`） |
| 发布时间窗 | `expected_macro_period` 按北京时间计算：每月 `refresh_day` 之前期望上上月，含当日之后期望上月 |
| 默认刷新日 | `settings.yaml` 的 `cn_macro_refresh_day` / `us_macro_refresh_day`，均默认 15 |
| 跳过 | 上次状态为 `success`、对应 region 已有数据且水位覆盖期望月份 |
| 写入 | 全量抓取后 SQLite upsert；不是按水位裁剪的增量请求，主键保证幂等 |
| 水位不足 | 抓取有数据但最新 CPI 早于期望月份时，状态强制为 `partial_failure` 并保留源端滞后错误 |
| 无有效记录 | 不清空旧表、不推进旧水位；写 `failed` 与错误摘要 |
| 返回类型 | `run_macro_import` → `ImportResult`（与日频 `run_daily_import` 一致） |

宏观域允许子源部分成功：成功记录仍写库，整体状态由 `FetchResult.ok` 和写入条数判为 `success` / `partial_failure` / `failed`。读路径用 `queries/_common.load_macro_rows` + `pivot_macro_rows`；US 查询额外截断晚于最新 CPI 的纯利率月。

### Redis 缓存

| 用途 | TTL | Key |
|------|-----|-----|
| 全球资产最近收盘价 | `ASSET_PRICE_CACHE_TTL=86400` | 按 ticker |
| 市场概览成功结果 | TTL 内复用 | 按类目 key |
| 失败标记 | `MARKET_OVERVIEW_FAILURE_TTL=300` / `REDIS_RETRY_COOLDOWN=60` | 失败项 |

### 新增数据集约定

1. `ImportDataset` 枚举（`schemas/imports.py`）加值
2. `services/imports/` 新增 importer + `import_orchestrator` 加分支
3. `services/sync/status.py` 加返回项
4. 前端 `api/admin.ts`、`hooks/admin-data-refresh.types.ts` 的阶段联合类型、顺序、初始状态及 locale 同步
5. 需要缓存时在 Redis 层定义 Key/TTL，遵循「成功复用 + 失败冷却」
6. 同步状态写回 `sync_meta`；importer 返回 `ImportResult`，全量聚合用 `ImportBatchResult`；仅 SSE/`done` 边界 `.to_dict()`

外部源细节见 [external-data.md](.agents/skills/astock/references/external-data.md)。

---

<a id="frontend"></a>

## 前端开发约定

### 技术栈与入口

- Vue3 + Vite + TypeScript + Arco Design Pro Vue
- 构建：`frontend/config/vite.config.{base,dev}.ts`；主题 `src/config/settings.json`

### API 层

- `axios.create({ baseURL: '/api/v1' })`（**硬编码**，未读 `VITE_API_BASE_URL`）
- `src/api/analysis.ts`：分析接口 + TS interface（含中美宏观）
- `src/api/admin.ts`：`refreshAllDataStream()`（SSE）、`fetchSyncStatusApi()`

### 路由（`router/routes/modules/main.ts`）

`/` → `/bull-market`，6 子页面，`requiresAuth: false`：

| 路径 | 视图 | 菜单 icon |
|------|------|-----------|
| `/bull-market` | `views/bull-market/` | bar-chart |
| `/turnover-rank` | `views/turnover-rank/` | sort |
| `/asset-price-levels` | `views/asset-price-levels/` | fire |
| `/market-overview` | `views/market-overview/` | apps |
| `/cn-macro-data` | `views/cn-macro-data/` | bar-chart |
| `/us-macro-data` | `views/us-macro-data/` | public |

### 页面写法

行情页主要使用 Arco `a-table`；宏观页使用 ECharts 6 折线图。通用：卡片 extra 通过 `formatSyncMeta` 或 `formatLatestDateMeta` 显示最新数据月份；管理员刷新完成并关闭进度弹窗后，经 `data-refresh` 事件触发当前页面 reload。

- **bull-market**：四指数独立阈值，合并单表展示；`data-refresh` 事件触发 reload
- **turnover-rank**：两列并排大盘/个股排名，`DEFAULT_TOP=20`
- **asset-price-levels**：贵金属分隔行；`FOCUSED_TICKERS` 打 Tag；按 `percentage_diff` 排序
- **market-overview**：类目分隔行 + 聚合 periodText；失败项「数据获取失败」
- **cn-macro-data**：一张 CPI/PPI 同比主图 + PMI、消费者信心两张并排子图；PMI 含 50 荣枯线，720px 以下改为纵向
- **us-macro-data**：CPI 同比 + 联邦基金目标利率上限单图；利率为 `step: end` 阶梯线

### 宏观 ECharts 约定

- `echarts/core` 按需注册 `LineChart`、Grid/Legend/Tooltip；中国 PMI 额外注册 `MarkLineComponent`；渲染器为 `CanvasRenderer`。
- 共享 `useMacroLineChart` 只负责初始化、重绘、暗色主题、`ResizeObserver` 和卸载销毁；series、tooltip、配色放在页面专用 `use-*-macro-chart.ts`。
- 数据序列保留 `null`，一般 `connectNulls=false`，不伪造缺失宏观数据；美国利率因政策利率离散调整允许 `connectNulls=true`。
- 图表必须跟随 `locale` 和 `body[arco-theme]` 重建 option；无有效指标时销毁实例并展示空态。
- 页面请求统一使用 `useAsyncRequest` + `usePageRefresh`，既负责首次加载，也响应管理员全量刷新后的事件。

### 管理刷新

- 导航栏 `admin-refresh-button`：前端密码门（`VITE_ADMIN_REFRESH_PASSWORD`），**后端无鉴权**
- 开发默认密码见 `.env.development`；生产经 Docker 构建期注入
- `useAdminDataRefresh` + `refresh-progress-modal`：SSE 六阶段进度弹窗；完成并关闭后 `emitDataRefresh` 通知各页 reload

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
| `US_MACRO_REFRESH_DAY` / `CN_MACRO_REFRESH_DAY` | 15 | 每月含该日后，宏观期望水位从上上月切到上月 |
| `US_MACRO_START_PERIOD` | `2020-06` | 美国宏观 API/页面默认起始月份 |
| `CN_MACRO_START_PERIOD` | 动态前推 60 个月 | 中国宏观 API 默认起始月份；可由 YAML 固定 |
| `GUNICORN_WORKERS/TIMEOUT` | — | 生产 worker；后端为 **sync** 路由 + 阻塞 IO，依赖多 worker，不走全量 async |

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
| `providers/*` / `datasets/*` | 对应 `services/imports/` / `queries/`（含 global_asset / market_overview）；[external-data.md](.agents/skills/astock/references/external-data.md) |
| `models/` | `sync/store.batch_upsert`、`sync/status` |
| `schemas/` | 前端 `src/api/*.ts` interface、Swagger |
| `config/*.yaml` | 重启 backend；前端下拉/展示项可能变化 |
| `services/queries/` | 前端对应页面阈值/列 |
| `models/macro.py` 指标常量 | `datasets/macro/` 标准化、查询 pivot、Pydantic/TS 字段、ECharts series |
| 宏观 `refresh_day` / 起始月 | `settings.yaml` → `config.py` → importer/API/前端默认参数 |
| 新增 API | `routers/` → `schemas/` → `frontend/src/api/` → `views/` |
| 新增前端页 | `router/routes/modules/main.ts` + locale |
| 新增导入阶段 | `ImportDataset`、orchestrator、sync status、前端阶段类型/顺序/文案 |
| `docker/nginx.conf` | frontend 重建、proxy 超时（SSE 长连接） |

## 常用排障命令

```bash
# 后端开发
cd backend && python -m astock.main

# SSE 流式导入
curl -N -X POST "http://localhost:8000/api/v1/admin/data/import/stream?dataset=all"

# 单独刷新宏观
curl -N -X POST "http://localhost:8000/api/v1/admin/data/import/stream?dataset=us_macro"
curl -N -X POST "http://localhost:8000/api/v1/admin/data/import/stream?dataset=cn_macro"

# 查询宏观月度序列
curl "http://localhost:8000/api/v1/analysis/us-macro?start=2020-06"
curl "http://localhost:8000/api/v1/analysis/cn-macro?start=2021-07"

# 同步状态
curl "http://localhost:8000/api/v1/admin/data/sync-status"

# Docker 状态
docker compose -f docker/docker-compose.yml ps

# 改前端后重建
docker compose -f docker/docker-compose.yml build frontend && docker compose -f docker/docker-compose.yml up -d frontend
```
