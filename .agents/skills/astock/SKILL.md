---
name: astock
description: Astock A股/全球资产行情分析平台的开发约定与最佳实践。使用于在本仓库开发 FastAPI 后端数据采集/分析、Vue3+Arco 前端页面、Docker 部署时，保持架构约定与数据契约一致。
---

# Astock

本技能用于在 Astock 仓库内做开发：保持后端数据采集、增量同步、分析 API 的分层约定，前端 axios 信封解包与 Arco 表格页的统一写法，以及 Docker 部署配置一致。

## Quick Reference

* 响应信封：所有 API 统一返回 `{ code, message, data }`，`code === 0` 为成功；见下文「API 契约」，字段级详见 [reference.md — API 契约（字段级）](.agents/skills/astock/references/reference.md)。
* 外部数据源：4 类客户端在 `backend/astock/sources/`，统一返回 `SourceFetchResult`；见 [external-data.md](.agents/skills/astock/references/external-data.md)。
* 增量同步：`sync_meta` 表记录水位，`_batch_upsert` 用 `ON CONFLICT DO UPDATE`；见 [reference.md — 增量同步与缓存](.agents/skills/astock/references/reference.md)。
* 前端：`baseURL=/api/v1` 硬编码，拦截器解包信封后 `res.data` 即业务载荷；见 [reference.md — 前端开发约定](.agents/skills/astock/references/reference.md)。
* 部署：`docker/` 下三服务（redis/backend/frontend）+ nginx 反代；见 [reference.md — 部署与 Docker](.agents/skills/astock/references/reference.md)。

## 技术栈

- 后端：FastAPI + Uvicorn(开发)/Gunicorn(生产) + SQLModel(SQLite) + Redis + Pandas；数据源 `baostock`/`akshare`/腾讯行情(httpx)。
- 前端：Vue3 + Vite + TypeScript + Arco Design Vue (`@arco-design/web-vue`)。
- 部署：Docker Compose（redis + backend + frontend）+ Nginx 反代。

## 项目结构

```text
.
├── backend/
│   ├── astock/
│   │   ├── main.py            # FastAPI app + 本地开发入口（uvicorn reload）
│   │   ├── config.py          # 环境变量 + 业务常量（阈值）
│   │   ├── config/            # YAML 配置（牛市区间/全球资产/市场概览类目）
│   │   ├── core/              # database、exceptions、logging、redis、deps
│   │   ├── models/            # SQLModel 表定义
│   │   ├── schemas/           # Pydantic 请求/响应
│   │   ├── sources/           # 外部数据源客户端
│   │   ├── services/          # 业务逻辑（导入/分析/资产/市场概览）
│   │   └── routers/           # admin / analysis / meta 三组路由
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
│   │   │   ├── interceptor.ts # baseURL=/api/v1 + ApiResponse 信封解包
│   │   │   ├── analysis.ts    # 分析接口 + TS interface
│   │   │   ├── admin.ts       # 数据导入 / sync-status
│   │   │   └── meta.ts        # 牛市区间下拉元数据
│   │   ├── views/             # 业务页面（均为 a-table，无图表库）
│   │   │   ├── bull-market/         # 牛市点位 + 成交额双维度总览
│   │   │   ├── turnover-rank/       # 大盘 / 个股成交额 TopN 并排
│   │   │   ├── asset-price-levels/  # 全球资产价格水位
│   │   │   └── market-overview/     # 全球市场概览（6 类 13 项）
│   │   ├── router/
│   │   │   ├── index.ts
│   │   │   ├── guard/               # 路由守卫
│   │   │   └── routes/
│   │   │       ├── base.ts          # DEFAULT_LAYOUT
│   │   │       └── modules/main.ts  # 4 子路由，/ → /bull-market
│   │   ├── components/
│   │   │   ├── navbar/              # 顶栏（含 admin-refresh-button）
│   │   │   ├── menu/、breadcrumb/、tab-bar/、footer/  # Pro 布局组件
│   │   │   └── admin-refresh-button/  # 密码门 + 全量导入触发
│   │   ├── hooks/
│   │   │   ├── admin-data-refresh.ts  # 导入结果 Notification
│   │   │   └── loading.ts、request.ts、themes.ts 等
│   │   ├── utils/
│   │   │   ├── format.ts      # formatAmount / formatPoint / formatPeriod
│   │   │   └── sync-meta.ts   # 卡片 extra 同步状态文案
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
| `sources/` | 单一外部数据源拉取，返回 `SourceFetchResult` | 不写库、不做业务计算；每个源一个文件 |
| `services/` | 业务逻辑（导入编排、分析统计） | 编排数据源 → 读写模型；抛 `AppError`/`ExternalSourceAppError` |
| `routers/` | HTTP 入口，薄层转发到 service | 查询参数校验在路由层；不直接访问 sources |
| `models/` | SQLModel 表定义 | 主键显式声明，时间戳字段用 `str` 存 `cached_at` |
| `schemas/` | Pydantic 请求/响应 DTO | 响应统一走 `ApiResponse[T]` 信封 |

## 业务域（已实现）

| 域 | 关键文件 | 说明 |
|----|----------|------|
| 牛市统计 | `analysis_service` + `bull_markets.yaml` | 点位/成交额达标天数与极值 |
| 成交额排名 | `analysis_service` | 大盘 TopN + 个股高水位切片 TopN |
| 全球资产价格水位 | `global_asset_service` + `global_assets.yaml` | ATH 与当前价对比、结论标签 |
| 全球市场概览 | `market_overview_service` + `market_overview.yaml` | 6 类 13 项实时概览 |
| 数据导入 | `import_service` | 增量 upsert + sync_meta 水位 |
| 管理刷新 | 前端 `admin-refresh-button` | 密码门（`VITE_ADMIN_REFRESH_PASSWORD`），后端无鉴权 |

## 配置驱动

三类可变面由 YAML 驱动，是参数化的天然切点（修改业务范围时改 YAML 而非代码）：

- `backend/astock/config/bull_markets.yaml` — 牛市区间定义（名/起止/描述）
- `backend/astock/config/global_assets.yaml` — 全球资产清单（美股 ticker + 贵金属代码）
- `backend/astock/config/market_overview.yaml` — 市场概览类目（6 类共 13 项）

业务阈值常量在 `backend/astock/config.py`：`THRESHOLD_POINT=4000`、`TURNOVER_THRESHOLD=2e12`(2万亿)、`MARKET_CAP_THRESHOLD=1e11`(1000亿)、`STOCK_TURNOVER_SLICE_THRESHOLD=3e10`(300亿/日)、`START_DATE="2005-01-01"`。

## 修改导航（最常改哪里）

| 目标 | 改动位置 |
|------|----------|
| 新 API | `routers/` → `schemas/` → `services/` → `frontend/src/api/` → `views/` |
| 新外部数据源 | `sources/<name>_client.py` → 对应 service；先读 [external-data.md](.agents/skills/astock/references/external-data.md) |
| 新数据集导入 | `schemas/imports.py` `ImportDataset` → `import_service` → `get_sync_status` |
| 分析逻辑/阈值 | `analysis_service.py` + `config.py` / YAML → 前端页面筛选默认值 |
| 全球资产/概览项 | `config/global_assets.yaml` 或 `market_overview.yaml` → 对应 service |
| 数据库表 | `models/` → `import_service._batch_upsert` → sync_meta |
| 新前端页 | `router/routes/modules/main.ts` + `views/` + locale |
| 缓存/TTL | `config.py` 环境变量 + `core/redis_client.py` + 对应 service |
| 部署/静态 404 | 改前端后须 **重建 frontend 镜像**；见 `docker/nginx.conf` |

## 快速决策树（先定位再改）

- **症状：接口返回 code≠0**
  - 先看：`core/exception_handlers.py`、对应 service 抛的 `AppError` / `ExternalSourceAppError`
  - 再看：Swagger `/docs` 请求参数是否与 schema 一致
- **症状：导入慢/失败/partial_failure**
  - 先看：`GET /admin/data/sync-status` 与 `source_errors`
  - 再看：[external-data.md](.agents/skills/astock/references/external-data.md) 对应源的重试/并发约束
  - 网络：baostock/腾讯需稳定网络；akshare 在 macOS 须串行
- **症状：全球资产/概览数据 stale 或不刷新**
  - 先看：Redis TTL 与 `force_refresh` 语义（成功缓存 TTL 内复用）
  - 再看：`global_asset_service` / `market_overview_service` 失败标记冷却
- **症状：改了前端但线上没变化**
  - 先做：`docker compose build frontend && docker compose up -d frontend`
- **症状：新增字段前端拿不到**
  - 先看：后端 Pydantic schema → `frontend/src/api/*.ts` interface → 页面列定义

## API 契约

所有响应统一信封 `ApiResponse{ code:int(0=成功), message:str, data:T|null }`（`backend/astock/schemas/response.py`）。

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/analysis/bull-markets/point?threshold=` | 牛市点位达标统计 |
| GET | `/api/v1/analysis/bull-markets/turnover?threshold=` | 牛市成交额达标统计 |
| GET | `/api/v1/analysis/turnover/ranking?top=&bull_market=` | 大盘成交额 TopN |
| GET | `/api/v1/analysis/stock/ranking?top=&bull_market=` | 个股成交额 TopN |
| GET | `/api/v1/analysis/asset-price-levels?force_refresh=` | 全球资产价格水位 |
| GET | `/api/v1/analysis/market-overview?force_refresh=` | 全球市场概览 |
| POST | `/api/v1/admin/data/import?dataset=` | 触发数据导入 |
| GET | `/api/v1/admin/data/sync-status` | 同步状态查询 |

字段级契约见 [reference.md — API 契约（字段级）](.agents/skills/astock/references/reference.md)。

## 数据库表

| 表 | 主键 | 说明 |
|----|------|------|
| `point` | `date` | 上证收盘价 |
| `turnover` | `date` | 三市成交额 + 合计 |
| `stock_turnover` | `(date, code)` | 大市值个股高水位成交额切片 |
| `asset_high` | `ticker` | 全球资产历史最高点 |
| `sync_meta` | `table_name` | 增量同步水位与状态 |

## 开发常见操作

```bash
# 启动后端（开发，uvicorn reload）
cd backend && python -m astock.main          # 默认 :8000

# 启动前端（dev server 代理 /api → :8000）
cd frontend && pnpm dev

# 导入全部数据集
curl -X POST "http://localhost:8000/api/v1/admin/data/import?dataset=all"

# Swagger UI
# http://localhost:8000/docs
```

## 提交前自检清单

- 是否新增/修改 API：`routers/`、`schemas/`、`frontend/src/api/` 是否同步
- 是否修改模型：`import_service` upsert 与 `get_sync_status` 是否覆盖
- 是否修改外部源：sources 是否仍只拉取不写库；失败行为是否符合 `SourceFetchResult` 约定
- 是否修改 YAML 配置：重启 backend 后导入/展示是否正确
- 是否修改前端路由或静态资源：是否验证 Docker frontend 重建流程

## 深度参考（按需阅读）

| 场景 | 文档 |
|------|------|
| API 字段 / 前端 / 部署 / 同步缓存 / 排障 | [reference.md](.agents/skills/astock/references/reference.md) |
| 外部数据源 / sources 层 / 调用路径 / 失败行为 | [external-data.md](.agents/skills/astock/references/external-data.md) |
