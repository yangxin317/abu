# coding=utf-8
"""
Abu Quant · 首页（导航 + 概览）
左侧 sidebar 是 streamlit 多页自动列表，pages/ 下每个 .py 是一个功能页。
"""
import sys
import os
import warnings

warnings.simplefilter('ignore')
warnings.showwarning = lambda *a, **k: None
warnings.warn = lambda *a, **k: None

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import streamlit as st


st.set_page_config(page_title='Abu Quant', layout='wide', initial_sidebar_state='expanded')

st.title('🐢 Abu Quant')
st.caption('abu 量化思想 · 现代数据源（yfinance + akshare）· 浏览器单页')

st.markdown('''
### 5 个功能页（左边侧栏切换）

| 页面 | 用来做什么 |
|---|---|
| 📊 **单股回测** | 选 1 只股票 + 1 个策略 → 出资金曲线 / 买卖点 / 关键指标 |
| 📈 **组合回测** | 选 N 只股票同策略 → 出组合资金曲线 / 各 symbol 摘要 |
| 🔍 **技术分析** | 支撑阻力 / 趋势通道 / 黄金分割 / 振幅 / 多 symbol 相关性 |
| ⚙️ **参数优化** | 网格扫描策略参数 → 出收益 / 夏普 / 回撤热力图 |
| 📡 **今日信号** | 扫描股票池，找今日触发买卖信号的 symbol |

### 数据源说明

| 市场 | 主源 | Fallback |
|---|---|---|
| 美股 | yfinance + curl_cffi（绕反爬） | — |
| A 股 | akshare（东方财富） | yfinance（`.SS` / `.SZ`） |
| 港股 | akshare（东方财富） | yfinance（`.HK`） |

数据有缓存，同一个 symbol+区间 第二次拉是秒回。

### 8 个内置策略

`turtle / short_break / long_trend / double_ma / trend_reverse / golden_section / sd_break / n_day_hold`

详细规则见单股回测页面右上角的策略下拉。

### 已知约束

- abu 是 2018 项目，部分内部 API 用了 pandas 1.x，已在 `app/data_adapter.py` 里 monkey-patch 过
- 国内网络下 akshare 偶发 503/connection-aborted，已加重试 + yfinance fallback
- 实盘信号目前只判 raw price/MA 信号，不带 abu 完整决策（速度优先）
''')

st.sidebar.success('👈 在上方下拉里挑一个页面进入')
