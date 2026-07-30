---
name: astock
description: Astock A股、全球资产与中美宏观数据平台的开发约定与最佳实践。用于在本仓库开发 FastAPI 数据采集/分析、月频宏观导入、Vue3+Arco+ECharts 页面或 Docker 部署时，保持架构约定与数据契约一致。
---

# Astock

本技能用于在 Astock 仓库内做开发：保持后端数据采集、日频/月频同步、分析 API 的分层约定，前端 axios 信封解包、Arco 页面与 ECharts 宏观图表的统一写法，以及 Docker 部署配置一致。

## Quick Reference

* 响应信封：所有 API 统一返回 `{ code, message, data }`，`code === 0` 为成功；见下文「API 契约」，字段级详见 [reference.md — API 契约（字段级）](.agents/skills/astock/references/reference.md)。
* 外部数据：`providers/`（供应商适配）→ `datasets/`（稳定数据契约），统一返回 `FetchResult`；见 [external-data.md](.agents/skills/astock/references/external-data.md)。
* 增量同步：`sync_meta` 表记录水位，`sync_store.batch_upsert` 用 `ON CONFLICT DO UPDATE`；见 [reference.md — 增量同步与缓存](.agents/skills/astock/references/reference.md)。
* 宏观数据：中美月度指标统一写入 `macro_value(region, period, metric)` 长表；水位按最新 CPI 月份推进，发布日期窗口由 `settings.yaml` 控制。
* 前端：`baseURL=/api/v1` 硬编码，`request.ts` 拦截器把信封直接解包为业务 `data`；API 函数返回值不再带 AxiosResponse。
* 部署：`docker/` 下三服务（redis/backend/frontend）+ nginx 反代；见 [reference.md — 部署与 Docker](.agents/skills/astock/references/reference.md)。

## 技术栈

- 后端：FastAPI + Uvicorn(开发)/Gunicorn(生产) + SQLModel(SQLite) + Redis + Pandas；数据源 `baostock`、`akshare`、BLS、FRED、美联储官网、新浪与东财。
- 前端：Vue3 + Vite + TypeScript + Arco Design Vue (`@arco-design/web-vue`) + ECharts 6（宏观折线图按需注册）。
- 部署：Docker Compose（redis + backend + frontend）+ Nginx 反代。

## 项目结构

```text
.
├── backend/
│   ├── astock/
│   │   ├── main.py            # FastAPI app + 本地开发入口（uvicorn reload）
│   │   ├── config.py          # 环境变量 + 业务常量（阈值）
│   │   ├── config/            # YAML 配置（业务参数/牛市区间/全球资产/市场概览类目）
│   │   ├── core/              # database、exceptions、logging、redis、deps、progress（SSE）
│   │   ├── models/            # SQLModel 表定义
│   │   ├── schemas/           # Pydantic 请求/响应
│   │   ├── providers/         # 外部供应商适配（baostock/akshare/BLS/FRED/东财/新浪）
│   │   ├── datasets/          # 稳定数据契约与多源编排（indices/turnover/stocks/macro/…）
│   │   ├── services/          # 业务逻辑（imports/、queries/、global_asset/、market_overview/、编排层）
│   │   └── routers/           # admin / analysis 两组路由
│   ├── requirements.txt
│   └── .env.example
├── frontend/                  # Vue3 + Arco Design Pro（package.json v1.0.0）
│   ├── config/                # Vite 构建
│   │   ├── vite.config.base.ts   # vue/jsx/svg、@ 别名、less
│   │   ├── vite.config.dev.ts    # dev server + /api → :8000 代理
│   │   ├── vite.config.prod.ts
│   │   └── plugin/               # arco 按需、压缩、visualizer 等
│   ├── src/
│   │   ├── main.ts            # 应用入口
│   │   ├── App.vue
│   │   ├── api/               # HTTP 层（新增接口在此登记）
│   │   │   ├── request.ts     # baseURL=/api/v1 + ApiResponse 信封解包
│   │   │   ├── analysis.ts    # 分析接口 + TS interface
│   │   │   └── admin.ts       # SSE 流式导入 / sync-status
│   │   ├── views/             # 业务页面（行情表格 + 中美宏观 ECharts）
│   │   │   ├── bull-market/         # 牛市点位 + 成交额双维度总览
│   │   │   ├── turnover-rank/       # 大盘 / 个股成交额 TopN 并排
│   │   │   ├── asset-price-levels/  # 全球资产价格水位
│   │   │   ├── market-overview/     # 全球市场概览（6 类 18 项）
│   │   │   ├── cn-macro-data/       # 中国 CPI/PPI、PMI、消费者信心
│   │   │   └── us-macro-data/       # 美国 CPI 与联邦基金目标利率上限
│   │   ├── router/
│   │   │   ├── index.ts
│   │   │   ├── guard/               # 路由守卫
│   │   │   └── routes/
│   │   │       ├── base.ts          # DEFAULT_LAYOUT
│   │   │       └── modules/main.ts  # 6 子路由，/ → /bull-market
│   │   ├── components/
│   │   │   ├── navbar/              # 顶栏（含 admin-refresh-button）
│   │   │   ├── menu/、breadcrumb/、tab-bar/、footer/  # Pro 布局组件
│   │   │   └── admin-refresh-button/  # 密码门 + SSE 全量刷新 + 进度弹窗
│   │   ├── hooks/
│   │   │   ├── admin-data-refresh.ts  # 流式导入状态机 + 完成后通知
│   │   │   ├── use-macro-line-chart.ts # ECharts 生命周期/暗色/resize
│   │   │   └── loading.ts、request.ts、themes.ts 等
│   │   ├── utils/
│   │   │   ├── format.ts      # formatAmount / formatPoint / formatPeriod
│   │   │   ├── sync-meta.ts   # 卡片 extra 同步状态文案
│   │   │   ├── sse-stream.ts  # 通用 SSE POST 解析
│   │   │   └── data-refresh.ts # mitt 事件总线，刷新后各页 reload
│   │   ├── layout/            # default-layout.vue、page-layout.vue
│   │   ├── store/modules/     # app / user / tab-bar（Pro 脚手架状态）
│   │   ├── locale/            # zh-CN / en-US 菜单与设置文案
│   │   ├── config/settings.json   # 主题色、menuWidth、navbar 开关
│   │   └── assets/style/      # global.less、breakpoint.less
│   ├── .env.development       # VITE_ADMIN_REFRESH_PASSWORD 等
│   ├── .env.production
│   ├── index.html
│   └── package.json           # pnpm；husky + commitlint
└── docker/                    # compose / Dockerfile / nginx.conf
```

## 分层约定

| 层 | 职责 | 约定 |
|----|------|------|
| `providers/` | 外部供应商 SDK/HTTP 适配，返回原始或中性数据 | 不依赖 `datasets/`、`models/`、`services/`；不构造业务记录形状 |
| `datasets/` | 稳定数据契约、多源选择与标准化，返回 `FetchResult` | 不写库、不依赖 `services/`；扁平文件优先，复杂域再建子包 |
| `services/` | 业务逻辑（导入编排、分析统计） | `imports/` 写路径、`queries/` 读路径；通过 `datasets/` 取数，不感知具体供应商 |
| `routers/` | HTTP 入口，薄层转发到 service | 查询参数校验在路由层；不直接访问 providers/datasets |
| `models/` | SQLModel 表定义 | 主键显式声明，时间戳字段用 `str` 存 `cached_at` |
| `schemas/` | Pydantic 请求/响应 DTO | 响应统一走 `ApiResponse[T]` 信封 |

## 业务域（已实现）

| 域 | 关键文件 | 说明 |
|----|----------|------|
| 牛市统计 | `services/queries/` + `bull_markets.yaml` | 多指数点位 + 成交额达标天数与极值 |
| 成交额排名 | `services/queries/rankings.py` | 大盘 TopN + 个股高水位切片 TopN |
| 全球资产价格水位 | `services/global_asset/` + `global_assets.yaml` | ATH 与当前价对比、结论标签 |
| 全球市场概览 | `services/market_overview/` + `market_overview.yaml` | 6 类 18 项最近已结算日线概览（非实时） |
| 中国宏观 | `datasets/macro/china.py` + `imports/cn_macro.py` + `queries/cn_macro.py` | CPI/PPI 同比、制造业/非制造业 PMI、消费者信心（月频） |
| 美国宏观 | `datasets/macro/us_cpi.py` + `us_rates.py` + `imports/us_macro.py` | CPI 同比、联邦基金目标利率上限（月频，主备源） |
| 数据导入 | `services/imports/`（`pipeline` + `stock/`）+ `import_orchestrator` | 增量 upsert + sync_meta 水位 |
| 管理刷新 | 前端 `admin-refresh-button` + SSE | 6 阶段刷新；密码门（`VITE_ADMIN_REFRESH_PASSWORD`），后端无鉴权 |

## 配置驱动

四类业务清单由领域 YAML 驱动；通用业务参数在 `settings.yaml`：

- `backend/astock/config/bull_markets.yaml` — 牛市区间定义（名/起止/描述）
- `backend/astock/config/point_indices.yaml` — 牛市点位指数清单（上证/沪深300/创业板/科创50）及默认阈值
- `backend/astock/config/global_assets.yaml` — 全球资产清单（美股 ticker + 贵金属代码）
- `backend/astock/config/market_overview.yaml` — 市场概览类目（6 类共 18 项）
- `backend/astock/config/settings.yaml` — 通用阈值、批量参数及中美宏观刷新日/默认起始月份

业务常量由 `backend/astock/config.py` 读取：`TURNOVER_THRESHOLD=2e12`（2 万亿）、`STOCK_SLICE_TOP_N=20`、`START_DATE="2005-01-01"`。宏观默认 `refresh_day=15`；美国查询从 `2020-06` 开始，中国查询起点为空时动态取当前月往前 60 个月。各指数默认阈值见 `point_indices.yaml`。

## 修改导航（最常改哪里）

| 目标 | 改动位置 |
|------|----------|
| 新 API | `routers/` → `schemas/` → `services/` → `frontend/src/api/` → `views/` |
| 新外部数据源 | `providers/<vendor>/` + `datasets/<contract>.py` → 对应 service；先读 [external-data.md](.agents/skills/astock/references/external-data.md) |
| 新数据集导入 | `schemas/imports.py` `ImportDataset` → `services/imports/` → `import_orchestrator` → `sync_status_service` → 前端 `admin.ts` / `admin-data-refresh.types.ts` |
| 新宏观指标 | `models/macro.py` 指标常量 → `providers/` → `datasets/macro/` → importer/query schema → 前端 API/图表 |
| 宏观刷新窗口/默认区间 | `config/settings.yaml` → `config.py`；不要把起始月份或发布日期写死在 service |
| 分析逻辑/阈值 | `services/queries/` + `config.py` / YAML → 前端页面筛选默认值 |
| 全球资产/概览项 | `config/global_assets.yaml` 或 `market_overview.yaml` → `global_asset/` 或 `market_overview/` |
| 数据库表 | `models/` → `sync_store.batch_upsert` → `sync_status_service` |
| 新前端页 | `router/routes/modules/main.ts` + `views/` + locale |
| 新宏观图表 | 页面专用 `use-*-macro-chart.ts` + 共享 `hooks/use-macro-line-chart.ts`；ECharts 组件按需注册 |
| 缓存/TTL | `config.py` 环境变量 + `core/redis_client.py` + 对应 service |
| 部署/静态 404 | 改前端后须 **重建 frontend 镜像**；见 `docker/nginx.conf` |

## 快速决策树（先定位再改）

- **症状：接口返回 code≠0**
  - 先看：`core/exception_handlers.py`、对应 service 抛的 `AppError` / `ExternalSourceAppError`
  - 再看：Swagger `/docs` 请求参数是否与 schema 一致
- **症状：导入慢/失败/partial_failure**
  - 先看：`GET /admin/data/sync-status` 与 `source_errors`
  - 再看：[external-data.md](.agents/skills/astock/references/external-data.md) 对应源的重试/并发约束
  - 网络：baostock 需稳定网络；akshare 在 macOS 须串行；市场概览外网在 Linux 可小并发（darwin 仍串行）
- **症状：宏观页无数据或停在旧月份**
  - 先看：`GET /admin/data/sync-status` 的 `us_macro` / `cn_macro` 状态与 `last_synced_date`
  - 再看：当日是否已过 `settings.yaml` 的 `*_macro_refresh_day`；此前期望水位为上上月，此后为上月
  - 美国：CPI 看东财→BLS，利率看 FRED→Fed 官网；中国：四个 akshare 东财子源允许部分成功
  - 查询页只读 SQLite，不会打开页面即触网；需执行管理员刷新或单独导入宏观 dataset
- **症状：全球资产/概览数据 stale 或不刷新**
  - 先看：`ensure_closes` 是否 `closes_cover_settled`（缓存须覆盖 `last_settled_date`）；`force_refresh` 应全部重拉
  - 再看：`services/global_asset/` / `services/market_overview/` 失败标记冷却；本地 Redis 是否仍是旧序列
- **症状：改了前端但线上没变化**
  - 先做：`docker compose build frontend && docker compose up -d frontend`
- **症状：新增字段前端拿不到**
  - 先看：后端 Pydantic schema → `frontend/src/api/*.ts` interface → 页面列定义

## API 契约

所有响应统一信封 `ApiResponse{ code:int(0=成功), message:str, data:T|null }`（`backend/astock/schemas/response.py`）。

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/analysis/bull-markets/point?threshold_000001=&threshold_000300=&...` | 多指数牛市点位达标统计 |
| GET | `/api/v1/analysis/bull-markets/turnover?threshold=` | 牛市成交额达标统计 |
| GET | `/api/v1/analysis/turnover/ranking?top=&bull_market=` | 大盘成交额 TopN |
| GET | `/api/v1/analysis/stock/ranking?top=&bull_market=` | 个股成交额 TopN |
| GET | `/api/v1/analysis/asset-price-levels?force_refresh=` | 全球资产价格水位 |
| GET | `/api/v1/analysis/market-overview?force_refresh=` | 全球市场概览 |
| GET | `/api/v1/analysis/cn-macro?start=YYYY-MM` | 中国宏观月度序列（5 指标） |
| GET | `/api/v1/analysis/us-macro?start=YYYY-MM` | 美国宏观月度序列（CPI + 利率） |
| POST | `/api/v1/admin/data/import/stream?dataset=` | SSE 流式数据导入 |
| GET | `/api/v1/admin/data/sync-status` | 同步状态查询 |

字段级契约见 [reference.md — API 契约（字段级）](.agents/skills/astock/references/reference.md)。

## 数据库表

| 表 | 主键 | 说明 |
|----|------|------|
| `point` | `(date, index_code)` | 多指数收盘价（上证/沪深300/创业板/科创50） |
| `turnover` | `date` | 三市成交额 + 合计 |
| `stock_turnover` | `(date, code)` | 大市值个股高水位成交额切片 |
| `asset_high` | `ticker` | 全球资产历史最高点 |
| `macro_value` | `(region, period, metric)` | 中美宏观月度长表；`region=cn/us`、`period=YYYY-MM` |
| `sync_meta` | `table_name` | 增量同步水位与状态（点位按 `point_{code}` 分项） |

## 开发常见操作

```bash
# 启动后端（开发，uvicorn reload）
cd backend && python -m astock.main          # 默认 :8000

# 启动前端（dev server 代理 /api → :8000）
cd frontend && pnpm dev

# SSE 流式导入全部数据集（6 阶段）
curl -N -X POST "http://localhost:8000/api/v1/admin/data/import/stream?dataset=all"

# 单独刷新中美宏观
curl -N -X POST "http://localhost:8000/api/v1/admin/data/import/stream?dataset=cn_macro"
curl -N -X POST "http://localhost:8000/api/v1/admin/data/import/stream?dataset=us_macro"

# Swagger UI
# http://localhost:8000/docs
```

## 提交前自检清单

- 是否新增/修改 API：`routers/`、`schemas/`、`frontend/src/api/` 是否同步
- 是否修改模型：`sync_store.batch_upsert` 与 `sync_status_service` 是否覆盖
- 是否修改外部源：providers 是否只做外部访问；datasets 是否仍只标准化不写库；失败行为是否符合 `FetchResult` 约定
- 是否修改宏观指标：`models/macro.py`、长表写入、查询 pivot、Pydantic/TS 类型、图表 series 是否全部联动
- 是否修改导入阶段：后端枚举/编排/同步状态与前端 6 阶段进度类型、文案是否同步
- 是否修改 YAML 配置：重启 backend 后导入/展示是否正确
- 是否修改前端路由或静态资源：是否验证 Docker frontend 重建流程

## 深度参考（按需阅读）

| 场景 | 文档 |
|------|------|
| API 字段 / 前端 / 部署 / 同步缓存 / 排障 | [reference.md](.agents/skills/astock/references/reference.md) |
| 外部数据源 / providers + datasets 层 / 调用路径 / 失败行为 | [external-data.md](.agents/skills/astock/references/external-data.md) |
