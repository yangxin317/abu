# coding=utf-8
"""
技术分析模块封装：调 abu TLine + Similar 出图，返回 matplotlib Figure 给 streamlit。
"""
from __future__ import annotations

import warnings
from typing import List, Dict, Optional

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

warnings.simplefilter('ignore')


def _ensure_data():
    from app.data_adapter import install_into_abu
    install_into_abu()


def _kl(symbol: str, start: str, end: str):
    _ensure_data()
    from app.data_adapter import make_kl_df
    return make_kl_df(symbol, start=start, end=end)


# === 支撑阻力 / 趋势通道 / 黄金分割 / 振幅 ===

def support_resistance_chart(symbol: str, start: str, end: str,
                             only_last: bool = False, best_poly: int = 0):
    """支撑/阻力多重趋势线图。"""
    kl = _kl(symbol, start, end)
    if kl is None or kl.empty:
        return None, None
    from abupy.TLineBu.ABuTLine import AbuTLine
    line = AbuTLine(kl.close, symbol)
    fig = plt.figure(figsize=(11, 5))
    line.show_support_resistance_trend(only_last=only_last, best_poly=best_poly,
                                       show=False, show_step=False)
    return fig, kl


def regress_channel_chart(symbol: str, start: str, end: str, step_x: float = 1.0):
    """线性回归趋势通道（含上下通道）。"""
    kl = _kl(symbol, start, end)
    if kl is None or kl.empty:
        return None, None
    from abupy.TLineBu.ABuTLine import AbuTLine
    line = AbuTLine(kl.close, symbol)
    fig = plt.figure(figsize=(11, 5))
    line.show_regress_trend_channel(step_x=step_x)
    return fig, kl


def golden_section_chart(symbol: str, start: str, end: str, both_golden: bool = True):
    """黄金分割位线（38.2/50/61.8）。"""
    kl = _kl(symbol, start, end)
    if kl is None or kl.empty:
        return None, None
    from abupy.TLineBu.ABuTLine import AbuTLine
    line = AbuTLine(kl.close, symbol)
    fig = plt.figure(figsize=(11, 5))
    line.show_golden(both_golden=both_golden)
    return fig, kl


def skeleton_channel_chart(symbol: str, start: str, end: str, with_mean: bool = True,
                           step_x: float = 1.0):
    """骨架（极值/最值）通道。"""
    kl = _kl(symbol, start, end)
    if kl is None or kl.empty:
        return None, None
    from abupy.TLineBu.ABuTLine import AbuTLine
    line = AbuTLine(kl.close, symbol)
    fig = plt.figure(figsize=(11, 5))
    line.show_skeleton_channel(with_mean=with_mean, step_x=step_x)
    return fig, kl


def shift_distance_chart(symbol: str, start: str, end: str, step_x: float = 1.0):
    """位移路程比（趋势敏感度）图。"""
    kl = _kl(symbol, start, end)
    if kl is None or kl.empty:
        return None, None
    from abupy.TLineBu.ABuTLine import AbuTLine
    line = AbuTLine(kl.close, symbol)
    fig = plt.figure(figsize=(11, 5))
    line.show_shift_distance(step_x=step_x, show_log=False)
    return fig, kl


def amplitude_stats(symbol: str, start: str, end: str) -> Dict:
    """振幅统计：日波动 + 滚动波动 + 振幅分布。"""
    kl = _kl(symbol, start, end)
    if kl is None or kl.empty:
        return {}
    daily_return = kl['close'].pct_change().dropna()
    rolling_vol = daily_return.rolling(20).std() * np.sqrt(252)
    amplitude = (kl['high'] - kl['low']) / kl['pre_close']
    out = {
        'kl': kl,
        'daily_return': daily_return,
        'rolling_vol': rolling_vol,
        'amplitude': amplitude,
        'mean_daily_return': float(daily_return.mean()),
        'std_daily_return': float(daily_return.std()),
        'annualized_vol': float(daily_return.std() * np.sqrt(252)),
        'mean_amplitude': float(amplitude.mean()),
        'max_drawdown': float(((kl['close'] / kl['close'].cummax()) - 1).min()),
    }
    return out


def amplitude_chart(stats: Dict):
    """振幅 4 联图：收盘曲线 / 日收益率 / 滚动波动率 / 日内振幅分布。"""
    if not stats:
        return None
    kl = stats['kl']
    fig, axes = plt.subplots(2, 2, figsize=(12, 7))
    axes[0, 0].plot(kl.index, kl['close'], color='black', linewidth=1)
    axes[0, 0].set_title('收盘价')
    axes[0, 0].grid(alpha=0.3)
    axes[0, 1].hist(stats['daily_return'], bins=60, color='steelblue', alpha=0.8)
    axes[0, 1].set_title(f'日收益率分布 (μ={stats["mean_daily_return"]:.4f}, σ={stats["std_daily_return"]:.4f})')
    axes[1, 0].plot(stats['rolling_vol'].index, stats['rolling_vol'], color='crimson', linewidth=1)
    axes[1, 0].set_title(f'20日滚动年化波动率 (年化σ={stats["annualized_vol"]:.4f})')
    axes[1, 0].grid(alpha=0.3)
    axes[1, 1].plot(stats['amplitude'].index, stats['amplitude'], color='orange', linewidth=0.7)
    axes[1, 1].set_title(f'日内振幅 (high-low)/pre_close, 均值={stats["mean_amplitude"]:.4f}')
    axes[1, 1].grid(alpha=0.3)
    fig.tight_layout()
    return fig


# === 多 symbol 相关性 ===

def correlation_matrix(symbols: List[str], start: str, end: str):
    """相关性矩阵 + 热力图。"""
    _ensure_data()
    from app.data_adapter import make_kl_df
    closes = {}
    for s in symbols:
        try:
            d = make_kl_df(s, start=start, end=end)
            if d is not None and not d.empty:
                closes[s] = d['close'].pct_change()
        except Exception:
            continue
    if len(closes) < 2:
        return None, None
    df = pd.DataFrame(closes).dropna(how='all')
    corr = df.corr()
    fig, ax = plt.subplots(figsize=(0.7 * len(corr) + 4, 0.6 * len(corr) + 3))
    im = ax.imshow(corr.values, cmap='RdBu_r', vmin=-1, vmax=1, aspect='auto')
    ax.set_xticks(range(len(corr.columns)))
    ax.set_xticklabels(corr.columns, rotation=45, ha='right')
    ax.set_yticks(range(len(corr.index)))
    ax.set_yticklabels(corr.index)
    for i in range(len(corr)):
        for j in range(len(corr)):
            v = corr.values[i, j]
            ax.text(j, i, f'{v:.2f}', ha='center', va='center',
                    color='white' if abs(v) > 0.5 else 'black', fontsize=9)
    fig.colorbar(im, ax=ax, fraction=0.04)
    ax.set_title('日收益率 Pearson 相关系数')
    fig.tight_layout()
    return fig, corr
