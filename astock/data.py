"""数据获取：封装 baostock 会话与指数日线抓取，akshare 个股成交额扫描。"""

import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import akshare as ak
import baostock as bs
import pandas as pd

from .config import (
    CANDIDATE_DAYS,
    MARKET_CAP_THRESHOLD,
    START_DATE,
    STOCK_CACHE_DIR,
)


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


def fetch_big_cap_stocks(market_cap_threshold: float = MARKET_CAP_THRESHOLD) -> pd.DataFrame:
    """获取大市值A股股票列表（基于akshare实时快照过滤）"""
    start_ts = time.perf_counter()
    spot = ak.stock_zh_a_spot_em()
    big_cap = spot[spot['总市值'] > market_cap_threshold].copy()
    big_cap = big_cap[big_cap['代码'].str.match(r'^\d{6}$')]
    cost = time.perf_counter() - start_ts
    threshold_yi = market_cap_threshold / 1e8
    print(f'大市值股票（总市值>{threshold_yi:.0f}亿）筛选完成，共 {len(big_cap)} 只（耗时 {cost:.2f}秒）\n')
    return big_cap[['代码', '名称', '总市值']].reset_index(drop=True)


def fetch_stock_history(code: str) -> pd.DataFrame:
    """获取单只股票全历史日线（带parquet缓存）"""
    cache_dir = Path(STOCK_CACHE_DIR)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f'stock_{code}.parquet'

    if cache_file.exists():
        return pd.read_parquet(cache_file)

    end_date = datetime.now().strftime('%Y%m%d')
    start_date = START_DATE.replace('-', '')
    df = ak.stock_zh_a_hist(symbol=code, period='daily',
                            start_date=start_date, end_date=end_date, adjust='')
    df.to_parquet(cache_file)
    time.sleep(0.3)  # 防东方财富反爬
    return df


def fetch_stock_top_turnover(
    market_cap_threshold: float = MARKET_CAP_THRESHOLD,
    candidate_days: int = CANDIDATE_DAYS,
) -> pd.DataFrame | None:
    """获取全市场大市值股票历史单日成交额Top10。

    两步过滤优化：
    1. 市值过滤：只扫描总市值>阈值的股票（通常100-200只，大幅减少API调用）
    2. 交易日过滤：用全市场总成交额Top N 日作为候选集
       （数学保证：个股成交额 ≤ 全市场总成交额，故个股Top10一定出现在全市场高成交额日）
    """
    start_ts = time.perf_counter()

    # 1. 获取大市值股票列表
    big_cap = fetch_big_cap_stocks(market_cap_threshold)
    if big_cap.empty:
        print('未找到符合市值条件的大市值股票')
        return None

    # 2. 获取全市场总成交额Top N交易日作为候选集
    turnover_df = fetch_turnover_data()
    if turnover_df is None:
        print('获取全市场成交额数据失败，无法构建候选交易日')
        return None
    candidate_dates = set(
        turnover_df.nlargest(candidate_days, 'turnover')['date'].dt.strftime('%Y-%m-%d')
    )
    print(f'候选交易日：全市场总成交额Top{candidate_days}，共 {len(candidate_dates)} 个交易日\n')

    # 3. 逐只拉取全历史日线（带parquet缓存），过滤候选交易日，每股保留Top20
    all_records: list[pd.DataFrame] = []
    total = len(big_cap)
    for i, row in big_cap.iterrows():
        code, name = row['代码'], row['名称']
        try:
            df = fetch_stock_history(code)
            if df.empty:
                continue
            df = df[['日期', '成交额']].copy()
            df['代码'] = code
            df['名称'] = name
            df = df[df['日期'].isin(candidate_dates)]
            if not df.empty:
                all_records.append(df.nlargest(20, '成交额'))
        except Exception as e:
            print(f'  获取 {code}({name}) 失败: {e}')

        if (i + 1) % 20 == 0:
            print(f'  已处理 {i + 1}/{total} 只...')

    if not all_records:
        print('未获取到有效个股成交额数据')
        return None

    # 4. 合并取全局Top10
    result = pd.concat(all_records, ignore_index=True)
    result = result.nlargest(10, '成交额').sort_values('成交额', ascending=False).reset_index(drop=True)

    cost = time.perf_counter() - start_ts
    print(f'个股成交额Top10获取完成，共扫描 {total} 只大市值股票（耗时 {cost:.2f}秒）\n')
    return result
