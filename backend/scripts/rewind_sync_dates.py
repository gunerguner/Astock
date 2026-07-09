#!/usr/bin/env python3
"""把本地库水位回拨到昨天/前天，方便测增量刷新路径。

默认行为（推荐）：
  1. 将 sync_meta.last_synced_date 改为目标日（若原水位更晚）
  2. 删除 turnover / point / stock_turnover 中 date > 目标日 的行
     （asset_high 无按日行，只改 sync_meta）

用法（可在任意目录执行）::

  # 在 scripts/ 下直接跑
  python rewind_sync_dates.py --days 2

  # 或在 backend/ 下
  python -m scripts.rewind_sync_dates --days 2 --dry-run
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# DB_PATH 默认是相对路径 db/astock.db，必须先切到 backend/ 再 import engine
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
os.chdir(_BACKEND_ROOT)
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from sqlalchemy import delete, func
from sqlmodel import Session, select

from astock.config import DB_PATH, POINT_INDEX_CONFIG, point_sync_meta_key
from astock.core.database import engine
from astock.core.datetime_utils import add_calendar_days, today_local
from astock.core.sync_status import SyncStatus
from astock.models.point import Point
from astock.models.stock_turnover import StockTurnover
from astock.models.sync_meta import SyncMeta
from astock.models.turnover import Turnover
from astock.services.price_utils import iso_now
from astock.services.sync_store import get_last_date

# dataset 名 → (sync_meta keys, 可选业务表 model)
_DATASET_SPEC: dict[str, tuple[list[str], type | None]] = {
    "turnover": (["turnover"], Turnover),
    "point": (
        ["point"] + [point_sync_meta_key(c) for c in POINT_INDEX_CONFIG],
        Point,
    ),
    "stock": (["stock_turnover"], StockTurnover),
    "global_assets": (["asset_high"], None),
}

_ALL_DATASETS = list(_DATASET_SPEC.keys())


def _resolve_target_date(days: int | None, date: str | None) -> str:
    if date:
        return date
    if days is None:
        raise SystemExit("请指定 --days 或 --date")
    if days < 1:
        raise SystemExit("--days 须 >= 1（1=昨天，2=前天）")
    return add_calendar_days(today_local(), -days)


def _count_after(db: Session, model: type, target: str) -> int:
    return db.exec(
        select(func.count()).select_from(model).where(model.date > target)
    ).one()


def _delete_after(db: Session, model: type, target: str) -> int:
    n = _count_after(db, model, target)
    if n:
        db.exec(delete(model).where(model.date > target))
    return n


def _print_status(db: Session, label: str) -> None:
    print(f"\n=== {label} ===")
    print(f"cwd={Path.cwd()}  db={Path(DB_PATH).resolve()}")
    print(f"today_local={today_local()}")
    print(
        f"turnover.max={get_last_date(db, Turnover)}  "
        f"point.max={get_last_date(db, Point)}  "
        f"stock.max={get_last_date(db, StockTurnover)}"
    )
    rows = db.exec(select(SyncMeta).order_by(SyncMeta.table_name)).all()
    for m in rows:
        print(
            f"  sync_meta[{m.table_name}] "
            f"date={m.last_synced_date} status={m.last_status}"
        )


def rewind(
    *,
    target: str,
    datasets: list[str],
    meta_only: bool,
    dry_run: bool,
) -> None:
    with Session(engine) as db:
        _print_status(db, "回拨前")
        print(f"\n目标水位 target={target}  meta_only={meta_only}  dry_run={dry_run}")
        print(f"datasets={datasets}")

        planned_meta: list[tuple[str, str | None, str]] = []
        planned_delete: list[tuple[str, int]] = []

        for ds in datasets:
            meta_keys, model = _DATASET_SPEC[ds]
            for key in meta_keys:
                meta = db.exec(
                    select(SyncMeta).where(SyncMeta.table_name == key)
                ).first()
                old = meta.last_synced_date if meta else None
                if old is None:
                    print(f"  skip meta {key}: 无记录")
                    continue
                if old <= target:
                    print(f"  skip meta {key}: 已是 {old} (<= {target})")
                    continue
                planned_meta.append((key, old, target))

            if model is not None and not meta_only:
                n = _count_after(db, model, target)
                if n:
                    planned_delete.append((model.__tablename__, n))

        if not planned_meta and not planned_delete:
            print("\n无需改动。")
            return

        print("\n计划改动:")
        for key, old, new in planned_meta:
            print(f"  sync_meta[{key}] {old} → {new}")
        for table, n in planned_delete:
            print(f"  DELETE FROM {table} WHERE date > {target}  ({n} 行)")

        if dry_run:
            print("\n[dry-run] 未写入数据库。")
            return

        now = iso_now()
        for key, _old, new in planned_meta:
            meta = db.exec(
                select(SyncMeta).where(SyncMeta.table_name == key)
            ).first()
            assert meta is not None
            meta.last_synced_date = new
            meta.last_synced_at = now
            meta.last_status = SyncStatus.SUCCESS
            meta.last_error = None
            db.add(meta)

        for ds in datasets:
            _keys, model = _DATASET_SPEC[ds]
            if model is not None and not meta_only:
                _delete_after(db, model, target)

        db.commit()
        _print_status(db, "回拨后")
        print("\n完成。可重新触发管理员刷新测试 Path A/B。")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="回拨 sync_meta / 业务表最新日期，便于测试增量刷新"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--days",
        type=int,
        help="相对上海日历 today 回拨天数：1=昨天，2=前天",
    )
    group.add_argument(
        "--date",
        type=str,
        help="目标水位 YYYY-MM-DD（绝对日期）",
    )
    parser.add_argument(
        "--datasets",
        nargs="+",
        choices=_ALL_DATASETS + ["all"],
        default=["all"],
        help="要回拨的数据集，默认 all",
    )
    parser.add_argument(
        "--meta-only",
        action="store_true",
        help="只改 sync_meta，不删除业务表中晚于目标日的行",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只打印计划，不写库",
    )
    args = parser.parse_args()

    datasets = (
        _ALL_DATASETS
        if "all" in args.datasets
        else list(dict.fromkeys(args.datasets))
    )
    target = _resolve_target_date(args.days, args.date)
    rewind(
        target=target,
        datasets=datasets,
        meta_only=args.meta_only,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
