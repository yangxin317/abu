# coding=utf-8
"""
现代数据 adapter：把 yfinance / akshare 的数据适配成 abu 期望的 DataFrame 格式，
并 monkey-patch abupy.MarketBu.ABuSymbolPd.make_kl_df 让 abu 整套回测引擎透明用上新数据源。

Symbol 路由（沿用 abu 风格）：
  usTSLA / usAAPL ...        → yfinance
  sh000001 / sz000002 / ...  → akshare 的 stock_zh_a_hist / stock_zh_index_daily
  hk00700 / hk02318 / ...    → akshare 的 stock_hk_hist
"""
import re
import time
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

_cache: dict = {}


def _retry(fn, *, attempts=3, delay=1.5, label=''):
    """简单重试（akshare/yfinance 偶发连接被拒/timeout）。"""
    last = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as e:
            last = e
            if i < attempts - 1:
                time.sleep(delay * (i + 1))
    raise RuntimeError(f'fetch {label} failed after {attempts}x: {type(last).__name__}: {last}') from last


def _normalize(symbol: str):
    s = symbol.strip()
    if s.startswith('us') and len(s) > 2:
        return 'us', s[2:]
    if s.startswith(('sh', 'sz')) and s[2:].isdigit():
        return 'cn', s
    if s.startswith('hk') and s[2:].isdigit():
        return 'hk', s[2:]
    if s.isdigit() and len(s) in (5, 6):
        return 'cn', ('sh' if s.startswith('6') else 'sz') + s
    raise ValueError(f'unrecognized symbol: {symbol!r}')


_yf_session = None


def _get_yf_session():
    """yfinance 0.2.x 支持 curl_cffi session 绕过 Yahoo 反爬。"""
    global _yf_session
    if _yf_session is None:
        try:
            from curl_cffi import requests as cffi_requests
            _yf_session = cffi_requests.Session(impersonate='chrome')
        except Exception:
            _yf_session = False  # 占位避免反复尝试
    return _yf_session if _yf_session else None


def _fetch_us(code: str, start: datetime, end: datetime):
    import yfinance as yf
    def _do():
        kw = dict(start=start, end=end + timedelta(days=1),
                  progress=False, auto_adjust=False)
        sess = _get_yf_session()
        if sess is not None:
            kw['session'] = sess
        df = yf.download(code, **kw)
        if df is None or df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.rename(columns=str.lower)
        return df[['open', 'high', 'low', 'close', 'volume']].copy()
    return _retry(_do, label=f'us:{code}')


def _fetch_via_yf(yf_code: str, start: datetime, end: datetime):
    """yfinance 通用 fallback：A 股用 600036.SS / 000002.SZ，港股用 0700.HK。"""
    import yfinance as yf
    kw = dict(start=start, end=end + timedelta(days=1),
              progress=False, auto_adjust=False)
    sess = _get_yf_session()
    if sess is not None:
        kw['session'] = sess
    df = yf.download(yf_code, **kw)
    if df is None or df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.rename(columns=str.lower)
    return df[['open', 'high', 'low', 'close', 'volume']].copy()


def _fetch_cn(symbol: str, start: datetime, end: datetime):
    import akshare as ak
    code = symbol[2:]

    def _via_akshare():
        if symbol.startswith(('sh000', 'sz399')):
            df = ak.stock_zh_index_daily(symbol=symbol)
            if df is None or df.empty:
                return None
            df['date'] = pd.to_datetime(df['date'])
            df = df.set_index('date').sort_index()
            df = df.loc[(df.index >= pd.Timestamp(start)) & (df.index <= pd.Timestamp(end))]
        else:
            df = ak.stock_zh_a_hist(symbol=code, period='daily',
                                    start_date=start.strftime('%Y%m%d'),
                                    end_date=end.strftime('%Y%m%d'),
                                    adjust='qfq')
            if df is None or df.empty:
                return None
            df = df.rename(columns={'日期': 'date', '开盘': 'open', '最高': 'high',
                                    '最低': 'low', '收盘': 'close', '成交量': 'volume'})
            df['date'] = pd.to_datetime(df['date'])
            df = df.set_index('date').sort_index()
        return df[['open', 'high', 'low', 'close', 'volume']].copy()

    try:
        return _retry(_via_akshare, attempts=2, label=f'cn:{symbol}')
    except Exception:
        # akshare 挂了 → fallback 到 yfinance（A 股代码 600036.SS, 000002.SZ）
        if symbol.startswith('sh'):
            yf_code = code + '.SS'
        elif symbol.startswith('sz'):
            yf_code = code + '.SZ'
        else:
            raise
        return _retry(lambda: _fetch_via_yf(yf_code, start, end),
                      attempts=2, label=f'cn-yf:{yf_code}')


def _fetch_hk(code: str, start: datetime, end: datetime):
    import akshare as ak

    def _via_akshare():
        df = ak.stock_hk_hist(symbol=code, period='daily',
                              start_date=start.strftime('%Y%m%d'),
                              end_date=end.strftime('%Y%m%d'),
                              adjust='qfq')
        if df is None or df.empty:
            return None
        df = df.rename(columns={'日期': 'date', '开盘': 'open', '最高': 'high',
                                '最低': 'low', '收盘': 'close', '成交量': 'volume'})
        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date').sort_index()
        return df[['open', 'high', 'low', 'close', 'volume']].copy()

    try:
        return _retry(_via_akshare, attempts=2, label=f'hk:{code}')
    except Exception:
        # 港股代码 fallback 到 yfinance: 0700.HK
        yf_code = code.lstrip('0').zfill(4) + '.HK'
        return _retry(lambda: _fetch_via_yf(yf_code, start, end),
                      attempts=2, label=f'hk-yf:{yf_code}')


def fetch_ohlcv(symbol: str, start, end):
    market, code = _normalize(symbol)
    if isinstance(start, str):
        start = datetime.strptime(start, '%Y-%m-%d')
    if isinstance(end, str):
        end = datetime.strptime(end, '%Y-%m-%d')
    key = (symbol, start.date(), end.date())
    if key in _cache:
        return _cache[key]
    if market == 'us':
        df = _fetch_us(code, start, end)
    elif market == 'cn':
        df = _fetch_cn(symbol, start, end)
    else:
        df = _fetch_hk(code, start, end)
    _cache[key] = df
    return df


def make_kl_df(symbol: str, n_folds: int = 2, start=None, end=None):
    """构造 abu 期望的完整 DataFrame（含 atr14/atr21/key/p_change/date_week 等）。"""
    if end is None:
        end = datetime.now()
    elif isinstance(end, str):
        end = datetime.strptime(end, '%Y-%m-%d')
    if start is None:
        start = end - timedelta(days=int(365 * n_folds))
    elif isinstance(start, str):
        start = datetime.strptime(start, '%Y-%m-%d')

    df = fetch_ohlcv(symbol, start, end)
    if df is None or df.empty:
        return None

    df = df.copy()
    df['date'] = df.index.strftime('%Y%m%d').astype(np.int64)
    df['date_week'] = df.index.dayofweek
    df['pre_close'] = df['close'].shift(1)
    df['pre_close'] = df['pre_close'].fillna(df['open'])
    df['p_change'] = np.where(df['pre_close'] == 0, 0,
                              (df['close'] - df['pre_close']) / df['pre_close'] * 100).round(3)
    df['volume'] = df['volume'].astype('int64')

    from abupy.MarketBu.ABuSymbolPd import calc_atr
    calc_atr(df)
    df['key'] = list(range(len(df)))
    out = df[['close', 'high', 'low', 'p_change', 'open', 'pre_close',
              'volume', 'date', 'date_week', 'key', 'atr21', 'atr14']].copy()
    # 用 attrs 存 symbol，pandas 1.x DataFrame 没有 .name 属性
    out.attrs['symbol'] = symbol
    try:
        # 部分 abu 内部代码读 kl.name；尝试 setattr 兜底（pandas 会发 warning，已被全局抑制）
        object.__setattr__(out, 'name', symbol)
    except Exception:
        pass
    return out


def _shim_pandas_for_abu():
    """abu 用了 pandas 1.x 的 API（DataFrame.append），pandas 2.0 已移除。补回来。"""
    if not hasattr(pd.DataFrame, 'append'):
        def _df_append(self, other, ignore_index=False, verify_integrity=False, sort=False):
            objs = [self, other] if not isinstance(other, list) else [self] + other
            return pd.concat(objs, ignore_index=ignore_index, sort=sort)
        pd.DataFrame.append = _df_append  # type: ignore[attr-defined]
    if not hasattr(pd.Series, 'append'):
        def _s_append(self, other, ignore_index=False, verify_integrity=False):
            return pd.concat([self, other] if not isinstance(other, list) else [self] + other,
                             ignore_index=ignore_index)
        pd.Series.append = _s_append  # type: ignore[attr-defined]


def install_into_abu():
    """把 abu 整条数据获取链路替换成本模块。调一次即可。"""
    _shim_pandas_for_abu()
    import abupy.MarketBu.ABuSymbolPd as _SymbolPd

    def patched_make_kl_df(symbol, data_mode=None, n_folds=2, start=None, end=None,
                           benchmark=None, show_progress=True,
                           parallel=False, parallel_save=True):
        # 如果传了 benchmark 但没传 start/end，用 benchmark 的日期范围
        if benchmark is not None and start is None and end is None:
            try:
                bkl = benchmark.kl_pd
                if bkl is not None and len(bkl):
                    start = str(bkl.index[0])[:10]
                    end = str(bkl.index[-1])[:10]
            except Exception:
                pass
        if isinstance(symbol, (list, tuple, pd.Series, pd.Index)):
            panel = {}
            for s in symbol:
                d = make_kl_df(s, n_folds=n_folds, start=start, end=end)
                if d is not None:
                    panel[s] = d
            return panel
        return make_kl_df(symbol, n_folds=n_folds, start=start, end=end)

    _SymbolPd.make_kl_df = patched_make_kl_df

    # combine_pre_kl_pd 想读 kl.name 拉前 n_folds 年，这里也 patch：
    # 优先从 attrs 读 symbol；没有就直接返回原 kl（不再做预热拉数据）。
    _orig_combine = _SymbolPd.combine_pre_kl_pd

    def patched_combine(kl_pd, n_folds=1):
        sym = None
        try:
            sym = kl_pd.attrs.get('symbol') if hasattr(kl_pd, 'attrs') else None
        except Exception:
            sym = None
        if not sym:
            sym = getattr(kl_pd, 'name', None)
        if not sym:
            return kl_pd  # 拿不到 symbol 就跳过预热，直接用现有数据
        try:
            pre = make_kl_df(sym, n_folds=n_folds, end=str(kl_pd.index[0])[:10])
        except Exception:
            return kl_pd
        if pre is None or pre.empty:
            return kl_pd
        combined = pd.concat([pre.iloc[:-1], kl_pd])
        combined['key'] = list(range(len(combined)))
        try:
            object.__setattr__(combined, 'name', sym)
        except Exception:
            pass
        combined.attrs['symbol'] = sym
        return combined

    _SymbolPd.combine_pre_kl_pd = patched_combine
