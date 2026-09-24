# coding=utf-8
"""参数优化（grid search）页面。"""
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
from app.grid_search import grid_search, heatmap

st.set_page_config(page_title='参数优化', layout='wide')

# 三种支持自定义参数的策略
STRATEGY_PARAMS = {
    'turtle': {
        'xd_long': [40, 60, 80, 100, 120],
        'xd_short': [21, 30, 42, 55],
        'sell_xd': [60, 90, 120, 150],
    },
    'short_break': {
        'xd': [10, 14, 21, 30, 42],
        'sell_xd': [21, 42, 55, 89],
    },
    'long_trend': {
        'xd': [60, 90, 120, 150, 180],
        'stop_loss_n': [0.3, 0.5, 0.8, 1.0],
        'stop_win_n': [2.0, 3.0, 4.0, 5.0],
    },
}

with st.sidebar:
    st.header('⚙️ 参数优化')
    symbol = st.text_input('Symbol', value='usTSLA').strip()
    today = date.today()
    start = st.date_input('起始日期', value=today - timedelta(days=365 * 3))
    end = st.date_input('结束日期', value=today)
    strategy = st.selectbox('策略（仅 turtle/short_break/long_trend 可定制）',
                            list(STRATEGY_PARAMS.keys()))

    st.markdown('**参数网格**（每个参数选要扫描的值，越多越慢）')
    grid_def = STRATEGY_PARAMS[strategy]
    selected_grid = {}
    for pname, defaults in grid_def.items():
        selected_grid[pname] = st.multiselect(pname, defaults, default=defaults[:3])

    capital = st.number_input('初始资金', min_value=10_000, max_value=100_000_000,
                              value=1_000_000, step=100_000)
    run_btn = st.button('🔬 跑网格', type='primary', use_container_width=True)

st.title(f'参数优化 · {symbol} · {strategy}')

if not run_btn:
    n_combos = 1
    for v in selected_grid.values():
        n_combos *= max(1, len(v))
    st.info(f'👈 当前选择 → {n_combos} 组参数组合（点跑网格开始）')
    st.stop()

# 检查参数
for k, v in selected_grid.items():
    if not v:
        st.error(f'参数 {k} 为空，请至少选 1 个值')
        st.stop()

n_combos = 1
for v in selected_grid.values():
    n_combos *= len(v)
st.write(f'共 **{n_combos}** 组参数')

with st.spinner(f'扫描中（每组 ~10s，预计 {n_combos * 10}s）...'):
    df = grid_search(symbol, start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d'),
                     strategy, selected_grid, initial_capital=float(capital))

if df.empty:
    st.error('没有结果')
    st.stop()

# 表格
st.subheader('📋 网格结果（点列头排序）')
df_show = df.copy()
for col in ['策略收益', '基准收益', '最大回撤', '胜率']:
    if col in df_show.columns:
        df_show[col] = df_show[col].apply(
            lambda x: f'{x:.2%}' if isinstance(x, (int, float)) else x)
st.dataframe(df_show, use_container_width=True)

# 热力图（要求选了 ≥ 2 个参数维度）
non_err = df[~df.get('error', pd.Series([False] * len(df))).fillna(False).astype(bool)] \
    if 'error' in df.columns else df
multi_dim_params = [k for k, v in selected_grid.items() if len(v) >= 2]
if len(multi_dim_params) >= 2:
    st.subheader('🔥 热力图')
    cc = st.columns(2)
    with cc[0]:
        x_col = st.selectbox('x 轴', multi_dim_params, index=0)
    with cc[1]:
        y_col = st.selectbox('y 轴', [m for m in multi_dim_params if m != x_col],
                             index=0)
    metric = st.radio('看哪个指标', ['策略收益', '夏普', '最大回撤'], horizontal=True)
    fig = heatmap(non_err, x_col, y_col, value_col=metric)
    if fig is not None:
        st.pyplot(fig)

# Top 5
if '策略收益' in df.columns:
    top = df.dropna(subset=['策略收益']).sort_values('策略收益', ascending=False).head(5)
    st.subheader('🥇 收益 Top 5')
    top_show = top.copy()
    for col in ['策略收益', '基准收益', '最大回撤', '胜率']:
        if col in top_show.columns:
            top_show[col] = top_show[col].apply(
                lambda x: f'{x:.2%}' if isinstance(x, (int, float)) else x)
    st.dataframe(top_show, use_container_width=True)
