# services / sources 代码拆分与重构方案

> 范围：`backend/astock/services/` 与 `backend/astock/sources/`
> 目标：拆分超大文件、理清分层、引入类型契约，降低维护与测试成本。

---

## 一、现状诊断

### 1.1 文件规模分布（共 2548 行 / 12 文件）

| 文件 | 行数 | 占比 | 评级 |
|---|---|---|---|
| `services/import_service.py` | 738 | 29% | 超大 |
| `sources/market_overview_client.py` | 365 | 14% | 偏大 |
| `services/global_asset_service.py` | 316 | 12% | 偏大 |
| `sources/baostock_client.py` | 313 | 12% | 偏大 |
| `services/analysis_service.py` | 245 | 10% | 可接受 |
| `services/market_overview_service.py` | 194 | 8% | 可接受 |
| `sources/akshare_client.py` | 113 | 4% | OK |
| `services/sync_store.py` | 93 | 4% | OK |
| `services/price_utils.py` | 73 | 3% | OK |
| `sources/tencent_client.py` | 69 | 3% | OK |
| `sources/fetch_result.py` | 29 | 1% | OK |

**前 4 个文件合计 1732 行，占 68%。** 拆分收益集中在这 4 个文件。

### 1.2 核心问题

#### 问题 A：`import_service.py` 是 God Module（738 行）

一个文件同时承担 5 类职责：

1. **4 套数据集导入器**：`import_turnover` / `import_point` / `import_stock` / `import_global_assets`
2. **个股 ProcessPool 编排**：`_baostock_worker_init` / `_fetch_stock_amount_worker` / `_import_stock_gen`（含嵌套闭包 `flush_buffer` / `emit_stock_progress`）
3. **SSE 流式编排**：`import_dataset_stream` / `_stream_run_phase` / `_stream_stock_phase`
4. **同步状态查询**：`get_sync_status` / `_get_point_sync_status` / `_aggregate_status`
5. **结果构建工具**：`_build_result` / `_resolve_status` / `_prepare_records_for_upsert` / `_filter_required_records`

其中 `_import_stock_gen` 是一个带 `yield` 的生成器，内部混合了：DB 增量判断 → 代码清单拉取 → 市值快照 → 进程池提交 → 缓冲区落库 → 进度上报 → SSE bridge drain，**单函数 200 行，6 层嵌套闭包**，是全仓最难测试和修改的点。

#### 问题 B：`market_overview_client.py` 塞了 7 个抓取器（365 行）

`_fetch_usd_index_history` / `_fetch_usd_index_spot` / `_fetch_usd_index` / `_fetch_us_index_sina` / `_fetch_cn_index` / `_fetch_foreign_futures` / `_fetch_boc_forex` / `_fetch_us_bond_rates` 全部平铺在一个文件，每个抓取器 30-50 行但相互独立，唯一共享的是 `_retry_call` 和 `_tail_closes`。东财 HTTP 的 headers/secid 参数也硬编码在函数体内。

#### 问题 C：`baostock_client.py` API 风格不一致（313 行）

- `BaostockClient` 类只含 `fetch_point` / `fetch_turnover` 两个方法
- `fetch_all_stock_codes` / `fetch_stock_amount_history` 是模块级函数
- 会话管理（`baostock_session`）、错误助手（`_login_failure` / `_query_failure` / `_read_failure` / `_safe_baostock_call`）、抓取实现混在一起
- `import_service.py` 同时 import 了 `BaostockClient`（实例化为 `baostock_client`）和模块函数，调用方需要知道"哪个是类方法、哪个是函数"

#### 问题 D：`global_asset_service.py` 读写路径混杂（316 行）

`refresh_asset_highs`（写入：拉 akshare → 写 Redis → upsert DB → 更新 sync_meta）与 `get_price_levels`（读取：查 DB → 读 Redis 缓存 → 计算涨跌 → 返回响应）放在同一文件。两者的依赖图几乎不重叠，但共享了 `_write_price_cache` / `_read_price_cache` / `_backfill_from_akshare` 等缓存助手。

#### 问题 E：导入结果用 `dict[str, Any]` 隐式契约

`_build_result` 返回 dict，调用方靠字符串 key（`"imported"` / `"total"` / `"last_date"` / `"status"` / `"source_errors"` / `"last_synced_at"` / `"elapsed"`）取值，类型不可校验、拼写无保护，且 `import_dataset` 的 `all` 分支返回的嵌套 dict 结构与其他分支不同，是隐式的多态契约。

---

## 二、设计原则

1. **按数据域拆分，不按技术层拆分** —— `turnover` / `point` / `stock` / `global_assets` 各自独立，比"controller/service/dao"三段式更贴合本仓实际。
2. **读写分离** —— 导入（写）与查询（读）拆到不同文件，依赖更清晰。
3. **编排与业务分离** —— SSE/进度编排独立成 orchestrator，业务函数保持纯函数可测。
4. **类型契约显式化** —— 用 dataclass 替代 `dict[str, Any]` 作为导入结果。
5. **保守迁移** —— 保持对外公开 API（router 调用的函数签名）不变，内部重组通过 `__init__.py` re-export 保持向后兼容。
6. **不过度拆分** —— 单文件 < 200 行为目标，但不为追求小文件而拆出 30 行的碎片文件。

---

## 三、目标结构

```
backend/astock/
├── services/
│   ├── __init__.py
│   ├── price_utils.py                  # 保留不动
│   ├── sync_store.py                   # 保留不动
│   ├── import_results.py               # 新增：ImportResult dataclass
│   ├── import_orchestrator.py          # 新增：import_dataset / import_dataset_stream
│   ├── sync_status_service.py          # 新增：get_sync_status（从 import_service 拆出）
│   ├── imports/
│   │   ├── __init__.py                 # re-export 4 个 import_* 函数
│   │   ├── _common.py                  # _resolve_status / _build_result / _prepare_records_for_upsert / _filter_required_records
│   │   ├── turnover_importer.py        # import_turnover
│   │   ├── point_importer.py           # import_point
│   │   ├── stock_importer.py           # import_stock + _import_stock_gen + worker
│   │   └── global_asset_importer.py    # import_global_assets（薄封装）
│   ├── queries/
│   │   ├── __init__.py                 # re-export 查询函数
│   │   ├── bull_market_stats.py        # build_bull_market_stats + point/turnover stats
│   │   └── rankings.py                 # turnover_ranking + stock_ranking
│   ├── global_asset/
│   │   ├── __init__.py                 # re-export refresh_asset_highs / get_price_levels
│   │   ├── _cache.py                   # _write_price_cache / _read_price_cache / _backfill_from_akshare
│   │   ├── refresh.py                  # refresh_asset_highs（写路径）
│   │   └── query.py                    # get_price_levels（读路径）
│   └── market_overview_service.py      # 保留（194 行可接受）
└── sources/
    ├── __init__.py
    ├── fetch_result.py                 # 保留不动
    ├── akshare_client.py               # 保留不动
    ├── tencent_client.py               # 保留不动
    ├── baostock/
    │   ├── __init__.py                 # re-export 公开 API
    │   ├── session.py                  # baostock_session / _login_failure / _query_failure / _read_failure / _safe_baostock_call / BaostockRecvTimeoutError
    │   ├── point_source.py             # BaostockClient.fetch_point
    │   ├── turnover_source.py          # BaostockClient.fetch_turnover
    │   └── stock_source.py             # fetch_all_stock_codes / fetch_stock_amount_history
    └── market_overview/
        ├── __init__.py                 # re-export fetch_all_items / fetch_item_closes
        ├── _common.py                  # _retry_call / _tail_closes / _merge_close_dicts / 东财 headers
        ├── usd_index.py                # _fetch_usd_index_history / _spot / _fetch_usd_index
        ├── global_index.py             # _fetch_global_index / _fetch_us_index_sina
        ├── cn_index.py                 # _fetch_cn_index
        ├── foreign_futures.py          # _fetch_foreign_futures
        ├── boc_forex.py                # _fetch_boc_forex
        └── us_bond.py                  # _fetch_us_bond_rates
```

**拆分前后对比：**

| 维度 | 现状 | 目标 |
|---|---|---|
| services 文件数 | 7（含 2 空） | 15 |
| sources 文件数 | 6（含 1 空） | 13 |
| 最大文件行数 | 738 | ~200（stock_importer） |
| >300 行文件数 | 4 | 0 |
| `dict[str, Any]` 结果契约 | 全程隐式 | `ImportResult` dataclass |

---

## 四、详细拆分方案

### 4.1 `import_service.py` → 拆为 6 个文件

#### (1) `services/import_results.py`（新增，~40 行）

引入类型化结果，替代 `dict[str, Any]`：

```python
from dataclasses import dataclass, field
from astock.core.sync_status import SyncStatus

@dataclass
class ImportResult:
    imported: int
    total: int
    last_date: str | None
    last_synced_at: str | None
    status: SyncStatus
    source_errors: dict[str, str | None] | None = None
    elapsed: float | None = None

    def to_dict(self) -> dict:
        """过渡期兼容 router 直接返回 dict 的场景。"""
        ...
```

#### (2) `services/imports/_common.py`（~70 行）

迁移：`_is_missing_value` / `_filter_required_records` / `_prepare_records_for_upsert` / `_REQUIRED_FIELDS` / `_resolve_status` / `_aggregate_status`。

#### (3) `services/imports/turnover_importer.py`（~50 行）

迁移：`import_turnover` + `_import_simple_dataset`（通用模板，放 `_common` 或本文件，取决于是否被 point 复用 → point 用了自己的循环，所以 `_import_simple_dataset` 仅 turnover 用，放本文件）。

#### (4) `services/imports/point_importer.py`（~80 行）

迁移：`import_point`。

#### (5) `services/imports/stock_importer.py`（~200 行，最大）

迁移：`import_stock` / `_import_stock_gen` / `_baostock_worker_init` / `_fetch_stock_amount_worker` / `STOCK_UPSERT_FLUSH_SIZE`。

**重构 `_import_stock_gen`**：把嵌套闭包 `flush_buffer` / `emit_stock_progress` 提升为模块级函数或类方法，降低嵌套层级。考虑引入 `StockImportContext` dataclass 持有 `db` / `record_buffer` / `imported` / `on_progress` / `bridge` 状态，使生成器主体变成线性的 5 步流程：

```python
def _import_stock_gen(db, *, on_progress=None, bridge=None):
    ctx = _init_stock_context(db)          # 1. 增量判断 + 代码清单 + 市值快照
    if ctx.is_skipped:
        return ctx.build_skip_result()
    for i, result in _iter_stock_history(ctx):  # 2. 进程池迭代
        _accumulate(ctx, result)            # 3. 过滤 + 缓冲
        _maybe_flush(ctx)                   # 4. 达到阈值落库
        _maybe_report(ctx, i)               # 5. 进度上报 + SSE drain
    _final_flush(ctx)                       # 6. 收尾
    return ctx.build_result()
```

#### (6) `services/imports/global_asset_importer.py`（~30 行）

迁移：`import_global_assets`（薄封装 `refresh_asset_highs` + 计时 + 日志）。

#### (7) `services/sync_status_service.py`（~60 行）

迁移：`get_sync_status` / `_get_point_sync_status` / `_SYNC_STATUS_TABLES`。

#### (8) `services/import_orchestrator.py`（~120 行）

迁移：`import_dataset` / `import_dataset_stream` / `_stream_run_phase` / `_stream_stock_phase` + `run_phase` 助手。

这是唯一同时引用 4 个 importer 的文件，依赖方向清晰：orchestrator → imports/*。

#### (9) `services/imports/__init__.py`

```python
from astock.services.imports.turnover_importer import import_turnover
from astock.services.imports.point_importer import import_point
from astock.services.imports.stock_importer import import_stock
from astock.services.imports.global_asset_importer import import_global_assets

__all__ = ["import_turnover", "import_point", "import_stock", "import_global_assets"]
```

**router 改动**：`routers/admin.py` 的 import 路径从 `astock.services.import_service` 改为 `astock.services.import_orchestrator`（`import_dataset` / `import_dataset_stream`）和 `astock.services.sync_status_service`（`get_sync_status`）。**函数签名不变。**

---

### 4.2 `global_asset_service.py` → 拆为 `global_asset/` 包（3 文件）

#### (1) `services/global_asset/_cache.py`（~80 行）

迁移：`_write_price_cache` / `_read_price_cache` / `_backfill_from_akshare` / `_conclusion` / `_CONCLUSIONS` / `_pending_item`。

读写路径共享的纯函数集中此处。

#### (2) `services/global_asset/refresh.py`（~100 行）

迁移：`refresh_asset_highs`。只依赖 `_cache` + `sync_store` + `akshare_client` + `price_utils`。

#### (3) `services/global_asset/query.py`（~130 行）

迁移：`get_price_levels`。只依赖 `_cache` + `sync_store` + `price_utils`。

#### (4) `services/global_asset/__init__.py`

```python
from astock.services.global_asset.refresh import refresh_asset_highs
from astock.services.global_asset.query import get_price_levels
```

**注意**：`imports/global_asset_importer.py` 的 import 路径从 `astock.services.global_asset_service` 改为 `astock.services.global_asset.refresh`。

---

### 4.3 `baostock_client.py` → 拆为 `baostock/` 包（4 文件）

#### (1) `sources/baostock/session.py`（~80 行）

迁移：`baostock_session` / `BaostockRecvTimeoutError` / `_SOCKET_TIMEOUT_SECONDS` / `_collect_rows` / `_login_failure` / `_query_failure` / `_read_failure` / `_safe_baostock_call`。

#### (2) `sources/baostock/point_source.py`（~70 行）

迁移：`BaostockClient.fetch_point`。**保持为类方法**（`BaostockClient` 现仅含 point/turnover，拆分后每个 source 文件各自定义小 class 或改为函数）。

**统一 API 决策**：建议全部改为模块级函数（`fetch_point` / `fetch_turnover`），消除"类里 2 个方法 + 模块 2 个函数"的割裂。`import_service` 里的 `baostock_client = BaostockClient()` 实例化 + `baostock_client.fetch_turnover()` 调用改为 `fetch_turnover(...)`。`BaostockClient` 类本身无状态（无 `__init__` 参数），类包装纯属多余。

#### (3) `sources/baostock/turnover_source.py`（~90 行）

迁移：`BaostockClient.fetch_turnover` → 改为 `fetch_turnover(start_date)` 函数。

#### (4) `sources/baostock/stock_source.py`（~80 行）

迁移：`fetch_all_stock_codes` / `fetch_stock_amount_history` / `_to_baostock_code` / `_CODE_RE`。

#### (5) `sources/baostock/__init__.py`

```python
from astock.sources.baostock.point_source import fetch_point
from astock.sources.baostock.turnover_source import fetch_turnover
from astock.sources.baostock.stock_source import (
    fetch_all_stock_codes,
    fetch_stock_amount_history,
)
from astock.sources.baostock.session import _SOCKET_TIMEOUT_SECONDS  # worker_init 需要

__all__ = ["fetch_point", "fetch_turnover", "fetch_all_stock_codes",
           "fetch_stock_amount_history", "_SOCKET_TIMEOUT_SECONDS"]
```

**注意**：`_SOCKET_TIMEOUT_SECONDS` 是带下划线前缀的"私有"常量，但 `import_service._baostock_worker_init` 跨模块引用了它。拆分后保留 re-export（过渡），或将其移入 `session.py` 的公开 API `configure_worker_socket()` 函数，让 worker_init 调用函数而非读常量。**推荐后者**，消除对私有符号的跨模块依赖。

---

### 4.4 `market_overview_client.py` → 拆为 `market_overview/` 包（8 文件）

这是拆分粒度最细的一处，但每个文件 30-60 行、职责单一，值得。

#### (1) `sources/market_overview/_common.py`（~50 行）

迁移：`_retry_call` / `_FETCH_RETRIES` / `_FETCH_RETRY_DELAY` / `_tail_closes` / `_merge_close_dicts` / `_em_udi_headers` / `_EM_*` 常量 / `_parse_em_kline_lines` / `_CN_INDEX_LOOKBACK_DAYS`。

#### (2) `sources/market_overview/usd_index.py`（~90 行）

迁移：`_fetch_usd_index_history` / `_fetch_usd_index_spot` / `_fetch_usd_index`。

#### (3) `sources/market_overview/global_index.py`（~40 行）

迁移：`_fetch_global_index` / `_fetch_us_index_sina` / `_GLOBAL_INDEX_SINA_FALLBACK` / `_GLOBAL_INDEX_EM_ONLY`。

#### (4) `sources/market_overview/cn_index.py`（~30 行）

迁移：`_fetch_cn_index` / `_cn_index_sina_symbol`。

#### (5) `sources/market_overview/foreign_futures.py`（~25 行）

迁移：`_fetch_foreign_futures`。

#### (6) `sources/market_overview/boc_forex.py`（~30 行）

迁移：`_fetch_boc_forex`。

#### (7) `sources/market_overview/us_bond.py`（~30 行）

迁移：`_fetch_us_bond_rates` / `_US_BOND_COLUMN_MAP`。

#### (8) `sources/market_overview/__init__.py`（~50 行）

迁移：`fetch_item_closes` / `fetch_all_items`（这两个是路由分发函数，放在 `__init__` 或单独 `dispatcher.py` 均可，推荐单独文件保持 `__init__` 纯 re-export）。

实际建议再加一个 `dispatcher.py` 放 `fetch_item_closes` + `fetch_all_items`，`__init__.py` 只做 re-export。

---

### 4.5 `analysis_service.py` 轻度拆分（可选）

245 行可接受，但可按"统计 vs 排名"拆为 `queries/bull_market_stats.py` + `queries/rankings.py`，共享的 `_get_bull_market_period` / `_require_rows` / `_empty_index_items` 放 `queries/_common.py`。

**优先级低**，可在前 4 个大文件拆分完成、验证稳定后再做。

---

## 五、迁移策略

### 5.1 分阶段执行（建议 4 个 PR）

| 阶段 | 范围 | 风险 | 验证方式 |
|---|---|---|---|
| PR1 | `baostock_client.py` → `baostock/` 包 | 低 | 跑 `import_point` / `import_turnover` / `import_stock` 各一次 |
| PR2 | `market_overview_client.py` → `market_overview/` 包 | 低 | 调 `/api/v1/analysis/market-overview` |
| PR3 | `global_asset_service.py` → `global_asset/` 包 | 中 | 调 `/api/v1/analysis/asset-price-levels` + `import_global_assets` |
| PR4 | `import_service.py` → `imports/` + orchestrator + sync_status + `ImportResult` | 高 | 全量 `import_dataset=all` 流式 + 非流式各一次 |

### 5.2 兼容性保障

- **`__init__.py` re-export**：每个新包的 `__init__.py` 导出原公开函数，保持 `from astock.services.import_service import import_dataset` 这类旧 import 在过渡期可用（最后阶段再删旧文件）。
- **函数签名不变**：所有 router 调用的函数签名保持原样，router 层零改动（除 import 路径）。
- **`ImportResult` 渐进替换**：先在 `imports/*` 内部使用 dataclass，通过 `to_dict()` 方法兼容 router 直接返回；后续 router 可改为返回 dataclass（FastAPI 会自动序列化）。

### 5.3 测试建议

每阶段迁移后，至少跑：

```bash
# 后端启动
uvicorn astock.main:app --reload

# 非流式全量导入
curl -X POST 'http://localhost:8000/api/v1/admin/data/import?dataset=all'

# 流式全量导入
curl -N -X POST 'http://localhost:8000/api/v1/admin/data/import/stream?dataset=all'

# 各查询接口
curl 'http://localhost:8000/api/v1/analysis/bull-markets/point'
curl 'http://localhost:8000/api/v1/analysis/bull-markets/turnover'
curl 'http://localhost:8000/api/v1/analysis/turnover/ranking'
curl 'http://localhost:8000/api/v1/analysis/stock/ranking'
curl 'http://localhost:8000/api/v1/analysis/asset-price-levels'
curl 'http://localhost:8000/api/v1/analysis/market-overview'
curl 'http://localhost:8000/api/v1/admin/data/sync-status'
```

---

## 六、收益评估

| 维度 | 收益 |
|---|---|
| 可读性 | 最大文件从 738 行降到 ~200 行，单文件单职责 |
| 可测性 | `stock_importer` 拆出 `StockImportContext` 后可单测各步骤 |
| 类型安全 | `ImportResult` 替代 `dict[str, Any]`，IDE 补全 + 静态检查 |
| API 一致性 | baostock 统一为模块级函数，消除 class/函数混用 |
| 读写分离 | `global_asset/refresh.py` vs `query.py` 依赖图清晰 |
| 编排解耦 | `import_orchestrator` 独立，改 SSE 逻辑不影响业务函数 |

**代价**：文件数从 12 增至 28，但每个文件职责单一、行数可控，import 路径通过 `__init__.py` 收敛，调用方感知最小。

---

## 七、待决策项

1. **`ImportResult` dataclass 是否一步到位替换所有 `dict` 返回？**
   - 方案 A（推荐）：内部用 dataclass，router 层通过 `.to_dict()` 过渡，后续再改 router 返回类型。
   - 方案 B：直接让 router 返回 `ImportResult`，FastAPI 自动序列化（需加 `response_model` 或 `model_config`）。

2. **`BaostockClient` 类是否彻底移除改为函数？**
   - 推荐改为函数（类无状态，包装无意义）。
   - 若未来需要连接池/会话复用，再重新引入有状态的类。

3. **`analysis_service.py` 是否本轮一并拆分？**
   - 245 行可接受，建议 PR4 之后单独评估。

4. **`_SOCKET_TIMEOUT_SECONDS` 跨模块引用如何处理？**
   - 推荐封装为 `session.configure_worker_socket()` 函数。
   - 备选：在 `baostock/__init__.py` re-export 常量（过渡期）。

---

## 八、执行顺序建议

1. 确认本方案（待决策项 1-4）
2. PR1：拆 `baostock_client.py`（最低风险，验证拆分包模式）
3. PR2：拆 `market_overview_client.py`（同模式，巩固）
4. PR3：拆 `global_asset_service.py`（涉及读写分离）
5. PR4：拆 `import_service.py` + 引入 `ImportResult`（最大改动，最后做）
6. （可选）PR5：拆 `analysis_service.py`
