"""输出：金额格式化与牛市/TopN 统计结果打印。"""

import pandas as pd


def format_amount(value: float | None) -> str:
    """格式化成交额为可读中文单位"""
    if value is None:
        return '-'
    units = [('万亿', 1e12), ('亿', 1e8), ('万', 1e4)]
    for label, base in units:
        if abs(value) >= base:
            return f'{value / base:.2f}{label}'
    return f'{value:.0f}元'


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
