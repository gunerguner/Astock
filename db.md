# SQLite 缓存技术方案

## 一、设计目标

历史交易数据不变，引入 SQLite 统一缓存。库文件 `cache/astock.db` 提交到 git，团队 clone 后增量更新即可。

## 二、数据库设计

### 2.1 表结构

```sql
-- 1. 全市场成交额（3.2，全量时间序列）
CREATE TABLE turnover (
    date        TEXT PRIMARY KEY,   -- YYYY-MM-DD
    sh_amount   REAL,
    sz_amount   REAL,
    cyb_amount  REAL,
    turnover    REAL,
    cached_at   TEXT                -- ISO 时间戳
);

-- 2. 上证指数点位（3.3，全量时间序列）
CREATE TABLE point (
    date        TEXT PRIMARY KEY,
    close       REAL,
    cached_at   TEXT
);

-- 3. 个股高水位成交额切片（3.1 中间数据）
--    只存「单日成交额 >= 300亿」的个股记录，用于 Top10 排行
CREATE TABLE stock_turnover (
    date        TEXT,               -- YYYY-MM-DD
    code        TEXT,               -- 股票代码 6 位
    name        TEXT,
    amount      REAL,               -- 成交额（元）
    cached_at   TEXT,
    PRIMARY KEY (date, code)
);
CREATE INDEX idx_stock_turnover_amount ON stock_turnover(amount DESC);
```

### 2.2 为什么这样设计

- `turnover`/`point`：以 date 为主键，天然去重，增量 upsert 即可。全量时间序列，每行只增不改（偶有修订则 upsert 覆盖）。
- `stock_turnover`：(date, code) 主键。**只存 ≥300 亿的切片**：
  - 历史 Top10 成交额均在数百亿级，300亿阈值不会漏掉 Top10 候选；
  - 数据量极小（全历史约几十~几百行），可全量入库、随 git 提交；
  - 新增候选日跑完后，把当日 ≥300 亿的个股 upsert 进来，再对全表 `ORDER BY amount DESC LIMIT 10` 即得 Top10。
- `cached_at`：记录写入时间，便于排查，不参与业务逻辑。

## 三、通用数据访问层 `astock/db.py`

```python
# astock/db.py
from pathlib import Path
from datetime import datetime
import sqlite3
import pandas as pd

DB_PATH = Path('cache/astock.db')

def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")   # 注：WAL 会产生 -wal 文件，gitignore 掉
    return conn

def init_db() -> None:
    """建表（IF NOT EXISTS）。main 启动时调用一次。"""

def get_last_date(table: str) -> str | None:
    """SELECT MAX(date) FROM {table}"""

def upsert_df(table: str, df: pd.DataFrame) -> None:
    """DataFrame → INSERT OR REPLACE INTO {table}"""

def query_df(sql: str, params=()) -> pd.DataFrame:
    """读 SQL → DataFrame"""
```

> WAL 模式下会产生 `astock.db-wal`/`astock.db-shm`，需加入 `.gitignore`，只提交 `astock.db`。

## 四、三个场景接入

### 4.1 全市场成交额 `fetch_turnover_data`

```
1. last = get_last_date('turnover')           # 如 '2026-07-04'
2. start = last or START_DATE
3. 增量拉取三指数 amount（baostock, start → today）
4. upsert_df('turnover', new_df)              # 按 date 去重覆盖
5. return query_df("SELECT * FROM turnover ORDER BY date")
```

### 4.2 上证点位 `fetch_point_data`

```
1. last = get_last_date('point')
2. 增量拉取 close（baostock, last → today）
3. upsert_df('point', new_df)
4. return query_df("SELECT * FROM point ORDER BY date")
```

### 4.3 个股 Top10 `fetch_stock_top_turnover`

```
1. big_cap = fetch_big_cap_stocks()                       # 实时，不缓存
2. turnover_df = fetch_turnover_data()                    # 走 4.1 缓存
3. candidate_dates = turnover_df.nlargest(CANDIDATE_DAYS, 'turnover') 的 date
4. 已缓存候选日 = SELECT DISTINCT date FROM stock_turnover
5. 新增候选日 = candidate_dates - 已缓存候选日            # 只差几天到几十天
6. for 新增候选日所在的那些日:
     for 每只大市值股票:
       df = ak.stock_zh_a_hist(code, ...)                # 实时拉日线（不再 parquet 缓存）
       筛出该股在新增候选日的记录
       对 (date, code, amount>=300亿) 的 → upsert stock_turnover
7. Top10 = SELECT * FROM stock_turnover
           WHERE date IN (candidate_dates)
           ORDER BY amount DESC LIMIT 10
8. return Top10
```

**关键点**：
- `fetch_stock_history` 的 parquet 缓存**移除**，改为实时拉日线。
- 新增候选日（通常只有几个~十几个）才需要拉个股日线，老候选日直接查库。
- 阈值 `STOCK_TURNOVER_SLICE_THRESHOLD = 300亿` 放 config。

## 五、配置调整 `astock/config.py`

```python
# 移除
STOCK_CACHE_DIR = 'cache'

# 新增
DB_PATH = 'cache/astock.db'
STOCK_TURNOVER_SLICE_THRESHOLD = 30_000_000_000  # 个股日成交额切片阈值，300亿
```

`CANDIDATE_DAYS`、`MARKET_CAP_THRESHOLD` 保持不变。

## 六、文件改动清单

| 文件 | 改动 |
|------|------|
| `astock/db.py` | **新建**：连接管理 + init_db + get_last_date + upsert_df + query_df |
| `astock/data.py` | 三个 fetch 函数接入 SQLite 增量；移除 `fetch_stock_history` 的 parquet 缓存 |
| `astock/config.py` | 移除 `STOCK_CACHE_DIR`；新增 `DB_PATH`、`STOCK_TURNOVER_SLICE_THRESHOLD` |
| `main.py` | 启动时调用 `init_db()` |
| `.gitignore` | 新增 `cache/astock.db-wal`、`cache/astock.db-shm`（`astock.db` 本身提交） |
| `requirements.txt` | 无需改动（sqlite3 为标准库） |

## 七、边界与一致性

1. **首次运行**：库为空，全量拉取写入，行为等价当前。
2. **同日重复运行**：增量区间为空，直接查库返回，零网络（除大市值快照）。
3. **跨日运行**：只拉新增交易日。
4. **数据修订**：upsert 按 date/date+code 覆盖，修订生效。
5. **Top10 正确性**：300亿阈值 ≤ 历史 Top10 最低值，保证不漏候选；新增候选日外的老数据已在库中。
6. **并发**：单进程脚本，WAL 足够；如需多进程可加 `PRAGMA busy_timeout`。

## 八、迁移说明

- 旧 `cache/stock_*.parquet` 不再使用，可手动删除（或脚本清理）。
- 首次运行新代码会自动建库并填充。

## 九、验证方式

- 首次：删除 `cache/astock.db`，跑 `-p`/`-t`/`-s`，确认三张表有数据、结果正确。
- 同日二次：确认无 baostock/akshare 拉取（仅大市值快照），结果一致。
- 模拟跨日：改库中 `MAX(date)` 为前几天，确认只拉增量。
- Top10：核对 `stock_turnover` 表行数应远小于候选日×股票数（仅 ≥300亿切片）。
