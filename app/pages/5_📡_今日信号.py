# coding=utf-8
"""今日信号扫描页：扫一组 symbol，找今日触发买卖信号的。"""
import sys, os, warnings

warnings.simplefilter('ignore')
warnings.showwarning = lambda *a, **k: None
warnings.warn = lambda *a, **k: None

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import streamlit as st
import pandas as pd
from app.live_signal import scan, SIGNAL_LABELS, DEFAULT_POOL

st.set_page_config(page_title='今日信号', layout='wide')

with st.sidebar:
    st.header('📡 今日信号')
    pool_choice = st.selectbox('股票池预设', list(DEFAULT_POOL.keys()) + ['🖊 自定义'])
    if pool_choice == '🖊 自定义':
        pool_str = st.text_area('Symbols（逗号分隔）',
                                value='usAAPL,usMSFT,usGOOG,usNVDA')
    else:
        pool_str = st.text_area('Symbols', value=','.join(DEFAULT_POOL[pool_choice]))
    pool = [s.strip() for s in pool_str.split(',') if s.strip()]

    st.markdown('**信号类型**')
    selected_signals = []
    for sig_id, label in SIGNAL_LABELS.items():
        if st.checkbox(label, value=sig_id.startswith('turtle_break')):
            selected_signals.append(sig_id)

    run_btn = st.button('🛰 开始扫描', type='primary', use_container_width=True)

st.title('📡 今日触发的信号')

if not run_btn:
    st.info('👈 选股票池和信号类型，点开始扫描')
    st.markdown('''
    ### 信号说明（基于最近一根 K 线 vs 历史数据，不跑全回测）

    - **海龟突破 N 日新高**：今日收盘 > 过去 N 日最高收盘
    - **MA 金叉/死叉**：快线穿越慢线
    - **上穿 60 日均线**：今日收盘越过 60 日 MA
    ''')
    st.stop()

if not selected_signals:
    st.error('至少选 1 个信号类型')
    st.stop()

with st.spinner(f'扫描 {len(pool)} 只 × {len(selected_signals)} 信号 ...'):
    df = scan(pool, selected_signals)

if df.empty:
    st.warning('今天没有任何 symbol 触发选中的信号 🤷')
    st.stop()

# 错误的单独列出
errors = df[df.get('error', pd.Series([False] * len(df))).notna()] if 'error' in df.columns else pd.DataFrame()
fired = df[~df.index.isin(errors.index)] if not errors.empty else df

if not fired.empty:
    st.success(f'触发 **{len(fired)}** 条信号')
    fired_show = fired.copy()
    for col in fired_show.columns:
        if fired_show[col].dtype == 'float64':
            fired_show[col] = fired_show[col].apply(
                lambda x: f'{x:.2%}' if abs(x) < 1 else f'{x:.4f}')
    st.dataframe(fired_show, use_container_width=True)

if not errors.empty:
    with st.expander(f'⚠️ {len(errors)} 个 symbol 失败'):
        st.dataframe(errors[['symbol', 'error']], use_container_width=True)
