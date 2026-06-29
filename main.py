"""
上证指数点位/全市场成交额统计程序
"""

import time
import argparse
from typing import Any
from contextlib import contextmanager
from datetime import datetime

import baostock as bs
import pandas as pd

# 配置参数
THRESHOLD_POINT = 4000
TURNOVER_THRESHOLD = 2_000_000_000_000  # 默认2万亿
START_DATE = '2005-01-01'

# 牛市时期定义
BULL_MARKETS = {
    '2007-2008年牛市': {'start': '2007-01-01', 'end': '2008-12-31'},
    '2015年牛市': {'start': '2015-01-01', 'end': '2015-12-31'},
    '2025年牛市': {'start': '2024-07-01', 'end': '2026-9-30'}
}


def format_amount(value: float | None) -> str:
    """格式化成交额为可读中文单位"""
    if value is None:
        return '-'
    units = [('万亿', 1e12), ('亿', 1e8), ('万', 1e4)]
    for label, base in units:
        if abs(value) >= base:
            return f'{value / base:.2f}{label}'
    return f'{value:.0f}元'


@contextmanager
def baostock_session():
    """封装 baostock 登录/登出，确保退出时正确 logout。"""
    lg = bs.login()
    try:
        yield lg
    finally:
        bs.logout()


def fetch_index_data(code: str, fields: str, desc: str) -> pd.DataFrame | None:
    """通用指数数据获取"""
    start_ts = time.perf_counter()
    with baostock_session() as lg:
        if lg.error_code != '0':
            print(f'登录失败: {lg.error_msg}')
            return None

        rs = bs.query_history_k_data_plus(
            code, fields,
            start_date=START_DATE,
            end_date=datetime.now().strftime('%Y-%m-%d'),
            frequency="d"
        )

        if rs.error_code != '0':
            print(f'查询失败: {rs.error_msg}')
            return None

        data_list = [rs.get_row_data() for _ in iter(rs.next, False)]
        df = pd.DataFrame(data_list, columns=rs.fields)

        for col in df.columns:
            if col != 'date':
                df[col] = df[col].astype(float)
        df['date'] = pd.to_datetime(df['date'])

        cost = time.perf_counter() - start_ts
        print(f'{desc}数据获取完成，共 {len(df)} 条记录（耗时 {cost:.2f}秒）\n')
        return df


def fetch_point_data() -> pd.DataFrame | None:
    """获取上证指数点位数据"""
    return fetch_index_data("sh.000001", "date,close", "上证指数")


def fetch_turnover_data() -> pd.DataFrame | None:
    """获取上证+深市+创业板成交额"""
    start_ts = time.perf_counter()
    with baostock_session() as lg:
        if lg.error_code != '0':
            print(f'登录失败: {lg.error_msg}')
            return None

        index_codes = {
            'sh_amount': 'sh.000001',
            'sz_amount': 'sz.399001',
            'cyb_amount': 'sz.399006',
        }

        all_records = []
        for col_name, code in index_codes.items():
            rs = bs.query_history_k_data_plus(
                code, "date,amount",
                start_date=START_DATE,
                end_date=datetime.now().strftime('%Y-%m-%d'),
                frequency="d"
            )
            if rs.error_code != '0':
                continue

            rows = [rs.get_row_data() for _ in iter(rs.next, False)]
            if not rows:
                continue

            df = pd.DataFrame(rows, columns=rs.fields)
            df['amount'] = df['amount'].astype(float)
            df['date'] = pd.to_datetime(df['date'])
            df.rename(columns={'amount': col_name}, inplace=True)
            all_records.append(df[['date', col_name]])

        if not all_records:
            print('未获取到有效的成交额数据')
            return None

        merged = pd.concat(all_records, axis=0).groupby('date', as_index=False).sum()

        for col in ['sh_amount', 'sz_amount', 'cyb_amount']:
            if col not in merged.columns:
                merged[col] = 0.0

        merged['turnover'] = merged[['sh_amount', 'sz_amount', 'cyb_amount']].sum(axis=1)
        merged = merged.sort_values('date')

        cost = time.perf_counter() - start_ts
        print(f'成交额数据汇总完成，共 {len(merged)} 个交易日（耗时 {cost:.2f}秒）\n')
        return merged


def analyze_bull_markets(df: pd.DataFrame, value_col: str, threshold: float) -> dict:
    """通用牛市时期统计"""
    results = {}

    for market_name, period in BULL_MARKETS.items():
        start_date = pd.to_datetime(period['start'])
        end_date = pd.to_datetime(period['end'])

        mask = (df['date'] >= start_date) & (df['date'] <= end_date) & (df[value_col] > threshold)
        period_data = df[mask]

        results[market_name] = {
            'days': len(period_data),
            'max_value': period_data[value_col].max() if len(period_data) > 0 else None
        }

    return results


def print_bull_market_stats(bull_markets: dict, mode: str, threshold: float) -> None:
    """通用牛市统计结果打印"""
    match mode:
        case 'point':
            title = f'三大牛市时期上证指数收盘价超过{threshold}点统计'
            label = '最高'
            formatter = lambda x: f'{x:.2f}'
        case _:
            title = f'三大牛市时期全A股成交额超过{format_amount(threshold)}统计'
            label = '最高成交额'
            formatter = format_amount

    print(f'{"="*80}')
    print(title)
    print(f'{"="*80}\n')

    total_days = sum(m['days'] for m in bull_markets.values())

    for market_name, info in bull_markets.items():
        print(f'{market_name}: {info["days"]} 天', end='')
        if info['days'] > 0 and info['max_value'] is not None:
            print(f'  ({label}: {formatter(info["max_value"])})')
        else:
            print()

    print(f'\n{"="*80}')
    print(f'三大牛市合计: {total_days} 个交易日')
    print(f'{"="*80}')


def print_top_turnover(df: pd.DataFrame, top_n: int = 5) -> None:
    """打印成交额TopN：沪深合计（深证已含创业板，不再单独列出）"""
    if df.empty:
        print('\n未找到成交额记录\n')
        return

    df = df.copy()
    df['sh_sz_total'] = df['sh_amount'] + df['sz_amount']
    top_sh_sz = df.sort_values('sh_sz_total', ascending=False).head(top_n)

    print(f'\n成交额Top{top_n}（上证+深证，深证已含创业板）：')
    for _, row in top_sh_sz.iterrows():
        date_str = row["date"].strftime("%Y-%m-%d")
        sh = format_amount(row["sh_amount"])
        sz = format_amount(row["sz_amount"])
        total = format_amount(row["sh_sz_total"])
        print(f'  {date_str}: 上证{sh} + 深证{sz} = {total}')

    print()


def run_point_mode(threshold: float) -> None:
    """点位模式"""
    print(f'统计上证指数收盘价超过{threshold}点的历史记录...\n')
    df = fetch_point_data()
    if df is None:
        return

    bull_markets = analyze_bull_markets(df, 'close', threshold)
    print_bull_market_stats(bull_markets, 'point', threshold)


def run_turnover_mode(threshold: float) -> None:
    """成交额模式"""
    print(f'统计全市场成交额超过{format_amount(threshold)}的历史记录...\n')
    df = fetch_turnover_data()
    if df is None:
        return

    bull_markets = analyze_bull_markets(df, 'turnover', threshold)
    print_bull_market_stats(bull_markets, 'turnover', threshold)
    print_top_turnover(df, top_n=10)


def main() -> None:
    """主函数"""
    global THRESHOLD_POINT, TURNOVER_THRESHOLD

    _SENTINEL: Any = object()
    parser = argparse.ArgumentParser(description="上证指数点位/全市场成交额统计")
    parser.add_argument('-p', '--point', nargs='?', default=_SENTINEL, const=None, type=float,
                        help='点位模式，可选阈值（默认4000）')
    parser.add_argument('-t', '--turnover', nargs='?', default=_SENTINEL, const=None, type=float,
                        help='成交额模式，可选阈值（元，默认2万亿）')
    args = parser.parse_args()

    has_turnover = args.turnover is not _SENTINEL
    mode = 'turnover' if has_turnover else 'point'

    match mode:
        case 'point':
            threshold = args.point if args.point not in (_SENTINEL, None) else THRESHOLD_POINT
            THRESHOLD_POINT = threshold
            run_point_mode(threshold)
        case 'turnover':
            threshold = args.turnover if args.turnover not in (_SENTINEL, None) else TURNOVER_THRESHOLD
            TURNOVER_THRESHOLD = threshold
            run_turnover_mode(threshold)


if __name__ == '__main__':
    main()
