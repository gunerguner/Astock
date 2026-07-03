"""上证指数点位/全市场成交额统计程序入口。"""

from typing import Any

from astock.config import THRESHOLD_POINT, TURNOVER_THRESHOLD
from astock.data import fetch_point_data, fetch_turnover_data
from astock.analysis import analyze_bull_markets
from astock.report import format_amount, print_bull_market_stats, print_top_turnover


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
    import argparse

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
            run_point_mode(threshold)
        case 'turnover':
            threshold = args.turnover if args.turnover not in (_SENTINEL, None) else TURNOVER_THRESHOLD
            run_turnover_mode(threshold)


if __name__ == '__main__':
    main()
