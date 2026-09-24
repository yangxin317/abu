# coding=utf-8
"""
多 symbol 组合回测：
  - 同策略同参数喂多个 symbol（abu 的 do_symbols_with_same_factors）
  - 等权拆分初始资金，独立跑各 symbol 后聚合资金曲线
"""
from __future__ import annotations

import warnings
from typing import Dict, List

warnings.simplefilter('ignore')


def run_portfolio(symbols: List[str], start: str, end: str,
                  strategy: str = 'turtle',
                  initial_capital: float = 1_000_000) -> Dict:
    """同策略 N 个 symbol 一起回测。返回每个 symbol 的指标 + 合并资金曲线 + 合并基准。"""
    from app.backtest import run_backtest, _strategy_factors  # noqa
    import pandas as pd

    if not symbols:
        raise ValueError('symbols 为空')

    per_capital = float(initial_capital) / len(symbols)
    per_results = {}
    failed = {}
    for sym in symbols:
        try:
            r = run_backtest(sym, start, end, strategy=strategy,
                             initial_capital=per_capital)
            per_results[sym] = r
        except Exception as e:
            failed[sym] = f'{type(e).__name__}: {str(e)[:100]}'

    if not per_results:
        raise RuntimeError(f'所有 symbol 都失败：{failed}')

    # 合并资金曲线（按日期 outer join，缺失值用 forward fill 再用 per_capital 兜底）
    cap_frames = {}
    bench_frames = {}
    for sym, r in per_results.items():
        if r.get('capital_curve') is not None:
            cap_frames[sym] = r['capital_curve']
        if r.get('benchmark_curve') is not None:
            bench_frames[sym] = r['benchmark_curve']

    if cap_frames:
        cap_df = pd.DataFrame(cap_frames).sort_index()
        cap_df = cap_df.ffill().fillna(per_capital)
        portfolio_curve = cap_df.sum(axis=1).rename('portfolio')
    else:
        portfolio_curve = None

    if bench_frames:
        bench_df = pd.DataFrame(bench_frames).sort_index()
        bench_df = bench_df.ffill().fillna(per_capital)
        portfolio_bench = bench_df.sum(axis=1).rename('benchmark')
    else:
        portfolio_bench = None

    # 各 symbol 关键指标摘要
    summary_rows = []
    for sym, r in per_results.items():
        m = r.get('metrics', {}) or {}
        summary_rows.append({
            'symbol': sym,
            '订单数': len(r.get('orders', [])) if r.get('orders') is not None else 0,
            '策略收益': m.get('策略总收益'),
            '基准收益': m.get('基准总收益'),
            '夏普': m.get('夏普比率'),
            '最大回撤': m.get('最大回撤'),
            '胜率': m.get('胜率'),
        })
    summary_df = pd.DataFrame(summary_rows).set_index('symbol') if summary_rows else None

    # 组合层面统计：按合并资金曲线计算
    portfolio_metrics = _portfolio_metrics(portfolio_curve, portfolio_bench, initial_capital)

    return {
        'per_symbol': per_results,
        'failed': failed,
        'portfolio_curve': portfolio_curve,
        'portfolio_benchmark': portfolio_bench,
        'summary': summary_df,
        'portfolio_metrics': portfolio_metrics,
    }


def _portfolio_metrics(curve, bench, initial_capital: float) -> Dict[str, float]:
    if curve is None or len(curve) < 2:
        return {}
    final = float(curve.iloc[-1])
    total_return = final / float(initial_capital) - 1
    # 最大回撤
    rolling_max = curve.cummax()
    drawdown = (curve - rolling_max) / rolling_max
    max_dd = float(drawdown.min())
    # 年化（按交易日 ~252）
    days = len(curve)
    ann = (1 + total_return) ** (252 / max(days, 1)) - 1 if total_return > -1 else None
    out = {
        '组合总收益': total_return,
        '组合最大回撤': max_dd,
    }
    if ann is not None:
        out['组合年化'] = float(ann)
    if bench is not None and len(bench) >= 2:
        bench_ret = float(bench.iloc[-1]) / float(initial_capital) - 1
        out['基准总收益'] = bench_ret
    return out
