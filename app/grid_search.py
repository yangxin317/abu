# coding=utf-8
"""
参数网格搜索：对策略关键参数做笛卡尔积扫描，输出每组的关键指标。
不依赖 abu 内置的 grid_search（那个用多进程 + hdf5，重）；自己跑串行更稳。
"""
from __future__ import annotations

import itertools
import warnings
from typing import Dict, List

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

warnings.simplefilter('ignore')


def grid_search(symbol: str, start: str, end: str, strategy: str,
                param_grid: Dict[str, List], initial_capital: float = 1_000_000) -> pd.DataFrame:
    """
    跑笛卡尔积网格。
    param_grid eg: {'xd_long': [40, 60, 80], 'xd_short': [20, 30, 42]}
    返回 DataFrame，列 = 参数 + 关键指标；index = 序号。
    """
    from app.backtest import run_backtest, custom_factors

    keys = list(param_grid.keys())
    rows = []
    for combo in itertools.product(*[param_grid[k] for k in keys]):
        params = dict(zip(keys, combo))
        try:
            buy, sell = custom_factors(strategy, params)
            r = run_backtest(symbol, start, end, strategy=strategy,
                             initial_capital=initial_capital,
                             buy_factors=buy, sell_factors=sell)
            m = r['metrics']
            rows.append({
                **params,
                '订单数': len(r['orders']) if r['orders'] is not None else 0,
                '策略收益': m.get('策略总收益'),
                '基准收益': m.get('基准总收益'),
                '夏普': m.get('夏普比率'),
                '最大回撤': m.get('最大回撤'),
                '胜率': m.get('胜率'),
            })
        except Exception as e:
            rows.append({**params, 'error': f'{type(e).__name__}: {str(e)[:80]}'})
    return pd.DataFrame(rows)


def heatmap(df: pd.DataFrame, x_col: str, y_col: str, value_col: str = '策略收益',
            title: str = ''):
    """从 grid 结果挑两个参数做热力图（其他参数取均值）。"""
    if df.empty or x_col not in df.columns or y_col not in df.columns or value_col not in df.columns:
        return None
    pivot = df.pivot_table(index=y_col, columns=x_col, values=value_col, aggfunc='mean')
    fig, ax = plt.subplots(figsize=(0.8 * len(pivot.columns) + 4, 0.6 * len(pivot.index) + 3))
    im = ax.imshow(pivot.values, cmap='RdYlGn', aspect='auto')
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    for i in range(len(pivot.index)):
        for j in range(len(pivot.columns)):
            v = pivot.values[i, j]
            if pd.isna(v):
                continue
            ax.text(j, i, f'{v:.2%}' if abs(v) < 10 else f'{v:.2f}',
                    ha='center', va='center', fontsize=9,
                    color='white' if v < pivot.values[~np.isnan(pivot.values)].mean() else 'black')
    ax.set_xlabel(x_col)
    ax.set_ylabel(y_col)
    ax.set_title(title or f'{value_col} 关于 {x_col}×{y_col}')
    fig.colorbar(im, ax=ax, fraction=0.04)
    fig.tight_layout()
    return fig
