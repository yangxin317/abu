# coding=utf-8
"""组合回测页面：N 个 symbol 同策略，等权资金分配。"""
import sys, os, warnings
from datetime import date, timedelta

warnings.simplefilter('ignore')
warnings.showwarning = lambda *a, **k: None
warnings.warn = lambda *a, **k: None

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import streamlit as st
import matplotlib.pyplot as plt
from app.backtest import STRATEGY_LABELS
from app.portfolio import run_portfolio

st.set_page_config(page_title='组合回测', layout='wide')

PRESET_BASKETS = {
    '美股科技 7 巨头': 'usAAPL,usMSFT,usGOOG,usAMZN,usNVDA,usMETA,usTSLA',
    'A 股核心 6 只': 'sh600036,sh601318,sh600519,sz000002,sz002594,sz300059',
    '港股蓝筹': 'hk00700,hk00939,hk09988,hk03690,hk02318',
    '中美龙头组合': 'usNVDA,usGOOG,sh600036,sz002594,hk00700',
}

with st.sidebar:
    st.header('📈 组合回测')
    basket_choice = st.selectbox('股票池预设', list(PRESET_BASKETS.keys()) + ['🖊 自定义'])
    if basket_choice == '🖊 自定义':
        symbols_str = st.text_area('Symbols（逗号分隔）', value='usAAPL,usMSFT,usGOOG')
    else:
        symbols_str = st.text_area('Symbols（逗号分隔）', value=PRESET_BASKETS[basket_choice])
    symbols = [s.strip() for s in symbols_str.split(',') if s.strip()]

    today = date.today()
    start = st.date_input('起始日期', value=today - timedelta(days=365 * 2))
    end = st.date_input('结束日期', value=today)
    strategy = st.selectbox('策略', list(STRATEGY_LABELS.keys()),
                            format_func=lambda k: STRATEGY_LABELS[k])
    capital = st.number_input('总初始资金（等权拆分到各 symbol）',
                              min_value=10_000, max_value=100_000_000,
                              value=1_000_000, step=100_000)
    run_btn = st.button('🚀 跑组合回测', type='primary', use_container_width=True)

st.title(f'组合回测 · {len(symbols)} 只股票 · {strategy}')

if not run_btn:
    st.info('👈 选股票池 + 策略 + 区间 → 跑回测')
    st.stop()

with st.spinner(f'跑 {len(symbols)} 只股票 ...'):
    try:
        r = run_portfolio(symbols, start.strftime('%Y-%m-%d'),
                          end.strftime('%Y-%m-%d'),
                          strategy=strategy, initial_capital=float(capital))
    except Exception as e:
        st.error(f'失败：{type(e).__name__}: {e}')
        st.stop()

if r['failed']:
    st.warning(f'部分 symbol 失败：{r["failed"]}')

# 组合层面指标
pm = r['portfolio_metrics']
if pm:
    cols = st.columns(min(4, len(pm)))
    for i, (k, v) in enumerate(pm.items()):
        with cols[i % len(cols)]:
            st.metric(k, f'{v:.2%}' if abs(v) < 10 else f'{v:.2f}')

# 组合资金曲线
st.subheader('📈 组合资金曲线 vs 等权买入持有')
pc = r['portfolio_curve']; pb = r['portfolio_benchmark']
if pc is not None and pb is not None:
    fig, ax = plt.subplots(figsize=(12, 5))
    pc.plot(ax=ax, label='策略组合', linewidth=2)
    pb.plot(ax=ax, label='等权买入持有', linewidth=1.5, alpha=0.7)
    ax.axhline(float(capital), color='gray', linestyle=':', alpha=0.5, label='初始资金')
    ax.legend(); ax.grid(alpha=0.3); st.pyplot(fig); plt.close(fig)

# 各 symbol 摘要
st.subheader('📋 各 symbol 摘要')
summary = r['summary']
if summary is not None:
    summary_show = summary.copy()
    for col in ['策略收益', '基准收益', '最大回撤', '胜率']:
        if col in summary_show.columns:
            summary_show[col] = summary_show[col].apply(
                lambda x: f'{x:.2%}' if isinstance(x, (int, float)) else x)
    st.dataframe(summary_show, use_container_width=True)
