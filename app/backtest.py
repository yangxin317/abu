# coding=utf-8
"""
abu 策略回测的轻量封装。
- 对内：用 abu 自带的 ABuPickTimeExecute + AbuFactor* + AbuMetricsBase
- 对外：暴露 run_backtest(symbol, start, end, strategy) → dict 包含 metrics + 数据
"""
from __future__ import annotations

import warnings
from datetime import datetime
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

warnings.simplefilter('ignore')


# 安装数据 hook（只装一次）
def _ensure_adapter_installed():
    if getattr(_ensure_adapter_installed, '_done', False):
        return
    from app.data_adapter import install_into_abu
    install_into_abu()
    _ensure_adapter_installed._done = True


# 策略 → 中文标签
STRATEGY_LABELS: Dict[str, str] = {
    'turtle': '海龟突破（60/42 双突破 + 120 反向 + ATR 套件）',
    'short_break': '短线突破（21 突破 + 55 反向 + ATR 套件）',
    'long_trend': '长趋势（120 突破，仅 ATR 平仓）',
    'double_ma': '双均线（5/60 动态自适应金叉死叉）',
    'trend_reverse': '趋势反转（下跌后反转入场 + ATR 套件）',
    'golden_section': '黄金分割（趋势上行回踩黄金分割位 + ATR）',
    'sd_break': '标准差突破（SD 通道上轨突破 + N 日强卖）',
    'n_day_hold': 'N 日定期持有（突破入场 + 21 日强卖）',
}


def _strategy_factors(strategy: str) -> Tuple[List[dict], List[dict]]:
    """返回 (buy_factors, sell_factors)。"""
    from abupy import (
        AbuFactorBuyBreak, AbuFactorSellBreak,
        AbuFactorAtrNStop, AbuFactorPreAtrNStop, AbuFactorCloseAtrNStop,
        AbuDoubleMaBuy, AbuDoubleMaSell,
        AbuUpDownTrend, AbuDownUpTrend, AbuUpDownGolden,
        AbuSDBreak, AbuFactorSellNDay,
    )

    atr_combo = [
        {'stop_loss_n': 0.5, 'stop_win_n': 3.0, 'class': AbuFactorAtrNStop},
        {'class': AbuFactorPreAtrNStop, 'pre_atr_n': 1.0},
        {'class': AbuFactorCloseAtrNStop, 'close_atr_n': 1.5},
    ]

    if strategy == 'turtle':
        buy = [{'xd': 60, 'class': AbuFactorBuyBreak},
               {'xd': 42, 'class': AbuFactorBuyBreak}]
        sell = [{'xd': 120, 'class': AbuFactorSellBreak}] + atr_combo
    elif strategy == 'short_break':
        buy = [{'xd': 21, 'class': AbuFactorBuyBreak}]
        sell = [{'xd': 55, 'class': AbuFactorSellBreak}] + atr_combo
    elif strategy == 'long_trend':
        buy = [{'xd': 120, 'class': AbuFactorBuyBreak}]
        sell = atr_combo
    elif strategy == 'double_ma':
        # 双均线动态自适应（不传 fast/slow，让 abu 根据大盘形态自动选）
        buy = [{'class': AbuDoubleMaBuy}]
        sell = [{'class': AbuDoubleMaSell}] + atr_combo
    elif strategy == 'trend_reverse':
        # AbuDownUpTrend：N 日下跌后趋势反转入场
        buy = [{'xd': 60, 'past_factor': 4, 'down_deg_threshold': -3,
                'class': AbuDownUpTrend}]
        sell = atr_combo
    elif strategy == 'golden_section':
        # AbuUpDownGolden：上行趋势 + 黄金分割回踩
        buy = [{'xd': 60, 'past_factor': 4, 'class': AbuUpDownGolden}]
        sell = atr_combo
    elif strategy == 'sd_break':
        # 标准差突破 + 21 日强卖
        buy = [{'xd': 30, 'class': AbuSDBreak}]
        sell = [{'sell_n': 21, 'is_sell_today': False, 'class': AbuFactorSellNDay}] + atr_combo
    elif strategy == 'n_day_hold':
        # 突破后定期持有 21 日
        buy = [{'xd': 42, 'class': AbuFactorBuyBreak}]
        sell = [{'sell_n': 21, 'is_sell_today': False, 'class': AbuFactorSellNDay}] + atr_combo
    else:
        raise ValueError(f'unknown strategy: {strategy!r}')
    return buy, sell


def custom_factors(strategy: str, params: dict) -> Tuple[List[dict], List[dict]]:
    """带参数定制的策略（用于 grid search 等）。
    支持 turtle 的 xd_long/xd_short/sell_xd，short_break 的 xd/sell_xd，long_trend 的 xd 等。"""
    from abupy import (AbuFactorBuyBreak, AbuFactorSellBreak,
                       AbuFactorAtrNStop, AbuFactorPreAtrNStop, AbuFactorCloseAtrNStop)
    atr_combo = [
        {'stop_loss_n': params.get('stop_loss_n', 0.5),
         'stop_win_n': params.get('stop_win_n', 3.0),
         'class': AbuFactorAtrNStop},
        {'class': AbuFactorPreAtrNStop, 'pre_atr_n': params.get('pre_atr_n', 1.0)},
        {'class': AbuFactorCloseAtrNStop, 'close_atr_n': params.get('close_atr_n', 1.5)},
    ]
    if strategy == 'turtle':
        buy = [{'xd': params.get('xd_long', 60), 'class': AbuFactorBuyBreak},
               {'xd': params.get('xd_short', 42), 'class': AbuFactorBuyBreak}]
        sell = [{'xd': params.get('sell_xd', 120), 'class': AbuFactorSellBreak}] + atr_combo
    elif strategy == 'short_break':
        buy = [{'xd': params.get('xd', 21), 'class': AbuFactorBuyBreak}]
        sell = [{'xd': params.get('sell_xd', 55), 'class': AbuFactorSellBreak}] + atr_combo
    elif strategy == 'long_trend':
        buy = [{'xd': params.get('xd', 120), 'class': AbuFactorBuyBreak}]
        sell = atr_combo
    else:
        return _strategy_factors(strategy)
    return buy, sell


def run_backtest(symbol: str, start: str, end: str, strategy: str = 'turtle',
                 initial_capital: float = 1_000_000,
                 buy_factors: List[dict] = None, sell_factors: List[dict] = None) -> Dict:
    """
    跑一次回测。
    返回 dict：
      - kl: K 线 DataFrame（abu 加工后）
      - orders: 订单 DataFrame（每笔交易）
      - capital_curve: 资金曲线 Series（index 日期，value 总资产）
      - metrics: dict（夏普 / 最大回撤 / 胜率 / 收益等）
      - benchmark_curve: 基准（买入持有）资金曲线 Series
    """
    _ensure_adapter_installed()
    import abupy
    from abupy import (AbuBenchmark, AbuCapital, ABuPickTimeExecute, AbuMetricsBase)

    if buy_factors is None or sell_factors is None:
        buy_factors, sell_factors = _strategy_factors(strategy)

    benchmark = AbuBenchmark(benchmark=symbol, start=start, end=end, n_folds=2)
    capital = AbuCapital(initial_capital, benchmark)

    orders_pd, action_pd, _ = ABuPickTimeExecute.do_symbols_with_same_factors(
        [symbol], benchmark, buy_factors, sell_factors, capital, show=False)

    metrics = AbuMetricsBase(orders_pd, action_pd, capital, benchmark)
    metrics.fit_metrics()

    kl = benchmark.kl_pd
    capital_curve = None
    cap_pd = getattr(capital, 'capital_pd', None)
    if cap_pd is not None and 'capital_blance' in cap_pd.columns:
        capital_curve = cap_pd['capital_blance']

    # benchmark = 买入持有同 symbol 同区间的资金曲线（对照基准）
    if kl is not None and len(kl):
        ret_close = kl['close'] / kl['close'].iloc[0]
        bench_curve = (initial_capital * ret_close).rename('benchmark')
    else:
        bench_curve = None

    out = {
        'kl': kl,
        'orders': orders_pd,
        'capital_curve': capital_curve,
        'benchmark_curve': bench_curve,
        'metrics': _extract_metrics(metrics),
    }
    return out


def _extract_metrics(metrics) -> Dict[str, float]:
    """从 AbuMetricsBase 抽出关键指标，统一命名。"""
    keys = [
        ('algorithm_period_returns', '策略总收益'),
        ('benchmark_period_returns', '基准总收益'),
        ('algorithm_annualized_returns', '年化收益'),
        ('benchmark_annualized_returns', '基准年化'),
        ('sharp_ratio', '夏普比率'),
        ('algorithm_volatility', '策略波动'),
        ('max_drawdown', '最大回撤'),
        ('win_rate', '胜率'),
        ('profit_loss_ratio', '盈亏比'),
        ('alpha', 'Alpha'),
        ('beta', 'Beta'),
    ]
    out = {}
    for attr, label in keys:
        v = getattr(metrics, attr, None)
        if v is None:
            continue
        try:
            out[label] = float(v)
        except (TypeError, ValueError):
            continue
    # 订单数 / 胜场数（后处理）
    if hasattr(metrics, 'orders_pd') and metrics.orders_pd is not None:
        out['总交易数'] = int(len(metrics.orders_pd))
    return out
