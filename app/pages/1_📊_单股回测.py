# coding=utf-8
"""单股回测页面。"""
import sys, os, warnings
from datetime import date, timedelta

warnings.simplefilter('ignore')
warnings.showwarning = lambda *a, **k: None
warnings.warn = lambda *a, **k: None

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from app.backtest import run_backtest, STRATEGY_LABELS

st.set_page_config(page_title='单股回测', layout='wide')

SYMBOL_PRESETS = {
    '🇺🇸 美股': ['usTSLA', 'usAAPL', 'usGOOG', 'usMSFT', 'usNVDA', 'usAMZN'],
    '🇨🇳 A 股': ['sh600036', 'sz000002', 'sz002230', 'sz002594', 'sz300059', 'sh000001'],
    '🇭🇰 港股': ['hk00700', 'hk02318', 'hk09988'],
}

with st.sidebar:
    st.header('📊 单股回测')
    market = st.radio('市场', list(SYMBOL_PRESETS.keys()))
    presets = SYMBOL_PRESETS[market]
    sym_choice = st.selectbox('股票（预设）', presets + ['🖊 手动输入'])
    symbol = st.text_input('Symbol', value='usTSLA').strip() if sym_choice == '🖊 手动输入' else sym_choice

    today = date.today()
    start = st.date_input('起始日期', value=today - timedelta(days=365 * 3))
    end = st.date_input('结束日期', value=today)
    strategy = st.selectbox('策略', list(STRATEGY_LABELS.keys()),
                            format_func=lambda k: STRATEGY_LABELS[k])
    capital = st.number_input('初始资金', min_value=10_000, max_value=100_000_000,
                              value=1_000_000, step=100_000)
    run_btn = st.button('🚀 跑回测', type='primary', use_container_width=True)

st.title(f'回测 · {symbol} · {strategy}')

if not run_btn:
    st.info('👈 设置参数，点跑回测开始')
    st.stop()

with st.spinner(f'拉 {symbol} + 跑 {strategy} ...'):
    try:
        r = run_backtest(symbol=symbol, start=start.strftime('%Y-%m-%d'),
                         end=end.strftime('%Y-%m-%d'), strategy=strategy,
                         initial_capital=float(capital))
    except Exception as e:
        st.error(f'回测失败：{type(e).__name__}: {e}')
        with st.expander('堆栈'):
            import traceback
            st.code(traceback.format_exc())
        st.stop()

m = r['metrics']
if m:
    items = list(m.items())
    cols = st.columns(4)
    for i, (label, value) in enumerate(items):
        with cols[i % 4]:
            if '收益' in label or '回撤' in label or '波动' in label:
                st.metric(label, f'{value:.2%}' if abs(value) < 10 else f'{value:.2f}')
            elif '率' in label or '比' in label:
                st.metric(label, f'{value:.3f}')
            else:
                st.metric(label, f'{value}' if not isinstance(value, float) else f'{value:.3f}')

st.subheader('📈 资金曲线 vs 买入持有')
cap = r['capital_curve']; bench = r['benchmark_curve']
if cap is not None and bench is not None:
    fig, ax = plt.subplots(figsize=(12, 5))
    cap.plot(ax=ax, label='策略', linewidth=2)
    bench.plot(ax=ax, label='买入持有', linewidth=1.5, alpha=0.7)
    ax.axhline(float(capital), color='gray', linestyle=':', alpha=0.5, label='初始资金')
    ax.legend(); ax.grid(alpha=0.3); st.pyplot(fig); plt.close(fig)
else:
    st.warning('没有资金曲线（可能没产生任何交易）')

st.subheader('🕯 K 线 + 买卖点')
kl = r['kl']; orders = r['orders']
if kl is not None and len(kl):
    fig2, ax2 = plt.subplots(figsize=(12, 5))
    ax2.plot(kl.index, kl['close'], color='black', linewidth=1, label='收盘')
    if orders is not None and len(orders):
        if 'buy_date' in orders.columns:
            bd = pd.to_datetime(orders['buy_date'].astype(str), format='%Y%m%d', errors='coerce')
            bp = orders.get('buy_price')
            if bp is not None:
                ax2.scatter(bd, bp, marker='^', color='red', s=80, label='买入', zorder=5)
        if 'sell_date' in orders.columns:
            sd = pd.to_datetime(orders['sell_date'].astype(str), format='%Y%m%d', errors='coerce')
            sp = orders.get('sell_price')
            if sp is not None:
                ax2.scatter(sd, sp, marker='v', color='green', s=80, label='卖出', zorder=5)
    ax2.legend(); ax2.grid(alpha=0.3); st.pyplot(fig2); plt.close(fig2)

if orders is not None and len(orders):
    with st.expander(f'📋 交易明细 共 {len(orders)} 笔'):
        st.dataframe(orders, use_container_width=True)
else:
    st.info('回测期内无交易触发')
