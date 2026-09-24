# coding=utf-8
"""
今日信号扫描：对一组 symbol 算最近一根 K 是否触发买/卖信号。
不跑全回测（慢），直接用 raw 数据判断信号 → 更快，更适合每日批量扫描。

支持的信号：
  - turtle_break: N 日新高突破（默认 N=42）
  - turtle_break_long: 60 日新高
  - golden_cross: MA 金叉（fast=5, slow=20，可调）
  - death_cross: MA 死叉
  - ma60_break_up: 价格上穿 60 日均线
"""
from __future__ import annotations

import warnings
from datetime import datetime, timedelta
from typing import Dict, List

import numpy as np
import pandas as pd

warnings.simplefilter('ignore')


def _kl(symbol: str, n_folds: float = 1):
    from app.data_adapter import install_into_abu, make_kl_df
    install_into_abu()
    return make_kl_df(symbol, n_folds=n_folds)


# === 信号判定 ===

def _signal_turtle_break(kl: pd.DataFrame, xd: int = 42) -> Dict:
    if len(kl) < xd + 2:
        return {'fired': False}
    close = kl['close']
    past_max = close.iloc[-(xd + 1):-1].max()  # 不含今天
    today = close.iloc[-1]
    fired = bool(today > past_max)
    return {
        'fired': fired,
        '今日收盘': float(today),
        f'过去{xd}日最高收盘': float(past_max),
        '突破幅度': float((today - past_max) / past_max) if past_max else 0.0,
    }


def _signal_ma_cross(kl: pd.DataFrame, fast: int = 5, slow: int = 20,
                     direction: str = 'up') -> Dict:
    if len(kl) < slow + 2:
        return {'fired': False}
    close = kl['close']
    ma_f = close.rolling(fast).mean()
    ma_s = close.rolling(slow).mean()
    today_diff = ma_f.iloc[-1] - ma_s.iloc[-1]
    yest_diff = ma_f.iloc[-2] - ma_s.iloc[-2]
    if direction == 'up':
        fired = bool(yest_diff <= 0 and today_diff > 0)
    else:
        fired = bool(yest_diff >= 0 and today_diff < 0)
    return {
        'fired': fired,
        f'MA{fast}': float(ma_f.iloc[-1]),
        f'MA{slow}': float(ma_s.iloc[-1]),
        '今日收盘': float(close.iloc[-1]),
    }


def _signal_ma60_break_up(kl: pd.DataFrame) -> Dict:
    if len(kl) < 62:
        return {'fired': False}
    close = kl['close']
    ma60 = close.rolling(60).mean()
    today_above = close.iloc[-1] > ma60.iloc[-1]
    yest_below = close.iloc[-2] <= ma60.iloc[-2]
    fired = bool(today_above and yest_below)
    return {
        'fired': fired,
        '今日收盘': float(close.iloc[-1]),
        'MA60': float(ma60.iloc[-1]),
        '昨日收盘': float(close.iloc[-2]),
    }


SIGNAL_HANDLERS = {
    'turtle_break_42': lambda kl: _signal_turtle_break(kl, xd=42),
    'turtle_break_60': lambda kl: _signal_turtle_break(kl, xd=60),
    'turtle_break_21': lambda kl: _signal_turtle_break(kl, xd=21),
    'ma_golden_5_20': lambda kl: _signal_ma_cross(kl, 5, 20, 'up'),
    'ma_death_5_20':  lambda kl: _signal_ma_cross(kl, 5, 20, 'down'),
    'ma_golden_5_60': lambda kl: _signal_ma_cross(kl, 5, 60, 'up'),
    'ma60_break_up':  _signal_ma60_break_up,
}

SIGNAL_LABELS = {
    'turtle_break_42': '海龟突破 42 日新高',
    'turtle_break_60': '海龟突破 60 日新高',
    'turtle_break_21': '海龟突破 21 日新高',
    'ma_golden_5_20': 'MA 金叉 (5/20)',
    'ma_death_5_20':  'MA 死叉 (5/20)',
    'ma_golden_5_60': 'MA 金叉 (5/60)',
    'ma60_break_up':  '上穿 60 日均线',
}


def scan(symbols: List[str], signals: List[str]) -> pd.DataFrame:
    """对每个 symbol、每种 signal 判定是否触发。返回长格式 DataFrame。"""
    rows = []
    for sym in symbols:
        try:
            kl = _kl(sym, n_folds=1)
            if kl is None or kl.empty:
                rows.append({'symbol': sym, 'signal': '*', 'error': 'no data'})
                continue
            last_date = str(kl.index[-1])[:10]
            for sig in signals:
                handler = SIGNAL_HANDLERS.get(sig)
                if handler is None:
                    continue
                res = handler(kl)
                if res.get('fired'):
                    rows.append({
                        'symbol': sym,
                        'signal': SIGNAL_LABELS.get(sig, sig),
                        'last_date': last_date,
                        **{k: v for k, v in res.items() if k != 'fired'},
                    })
        except Exception as e:
            rows.append({'symbol': sym, 'signal': '*',
                         'error': f'{type(e).__name__}: {str(e)[:80]}'})
    return pd.DataFrame(rows)


# 默认股票池
DEFAULT_POOL = {
    '🇺🇸 美股大盘': ['usAAPL', 'usMSFT', 'usGOOG', 'usNVDA', 'usAMZN', 'usTSLA',
                  'usMETA', 'usAVGO', 'usJPM', 'usV'],
    '🇨🇳 A股核心': ['sh600036', 'sh601318', 'sh600519', 'sz000001', 'sz000002',
                  'sz002230', 'sz002594', 'sz300059', 'sz300750'],
    '🇭🇰 港股蓝筹': ['hk00700', 'hk00939', 'hk09988', 'hk03690', 'hk02318'],
}
