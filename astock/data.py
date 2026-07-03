"""数据获取：封装 baostock 会话与指数日线抓取。"""

import time
from contextlib import contextmanager
from datetime import datetime

import baostock as bs
import pandas as pd

from .config import START_DATE


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
