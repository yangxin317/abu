# coding=utf-8
"""技术分析页：支撑阻力 / 趋势通道 / 黄金分割 / 振幅 / 相关性。"""
import sys, os, warnings
from datetime import date, timedelta

warnings.simplefilter('ignore')
warnings.showwarning = lambda *a, **k: None
warnings.warn = lambda *a, **k: None

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import streamlit as st
from app import analysis as A

st.set_page_config(page_title='技术分析', layout='wide')

with st.sidebar:
    st.header('🔍 技术分析')
    mode = st.radio('分析类型', [
        '支撑阻力线', '回归趋势通道', '黄金分割位', '骨架通道',
        '位移路程比', '振幅与波动', '多 symbol 相关性',
    ])
    today = date.today()
    start = st.date_input('起始日期', value=today - timedelta(days=365))
    end = st.date_input('结束日期', value=today)

    if mode == '多 symbol 相关性':
        symbols_str = st.text_area('Symbols（逗号分隔）',
                                   value='usAAPL,usNVDA,usGOOG,usTSLA,usMETA')
    else:
        symbol = st.text_input('Symbol', value='usTSLA').strip()

    if mode == '支撑阻力线':
        only_last = st.checkbox('只显示最近一段', value=False)
    if mode in ('回归趋势通道', '骨架通道', '位移路程比'):
        step_x = st.slider('step_x（采样步长）', 0.5, 4.0, 1.0, 0.5)

    run_btn = st.button('🔬 出图', type='primary', use_container_width=True)

st.title(f'技术分析 · {mode}')

if not run_btn:
    st.info('👈 选类型 + 输入 symbol → 出图')
    st.stop()

s = start.strftime('%Y-%m-%d'); e = end.strftime('%Y-%m-%d')
with st.spinner('计算中 ...'):
    try:
        if mode == '支撑阻力线':
            fig, _ = A.support_resistance_chart(symbol, s, e, only_last=only_last)
        elif mode == '回归趋势通道':
            fig, _ = A.regress_channel_chart(symbol, s, e, step_x=step_x)
        elif mode == '黄金分割位':
            fig, _ = A.golden_section_chart(symbol, s, e)
        elif mode == '骨架通道':
            fig, _ = A.skeleton_channel_chart(symbol, s, e, step_x=step_x)
        elif mode == '位移路程比':
            fig, _ = A.shift_distance_chart(symbol, s, e, step_x=step_x)
        elif mode == '振幅与波动':
            stats = A.amplitude_stats(symbol, s, e)
            fig = A.amplitude_chart(stats)
            if stats:
                cols = st.columns(4)
                cols[0].metric('日均收益', f'{stats["mean_daily_return"]:.4%}')
                cols[1].metric('年化波动', f'{stats["annualized_vol"]:.2%}')
                cols[2].metric('日均振幅', f'{stats["mean_amplitude"]:.2%}')
                cols[3].metric('最大回撤', f'{stats["max_drawdown"]:.2%}')
        elif mode == '多 symbol 相关性':
            symbols = [x.strip() for x in symbols_str.split(',') if x.strip()]
            fig, corr = A.correlation_matrix(symbols, s, e)
            if corr is not None:
                st.dataframe(corr.round(3), use_container_width=True)
        else:
            fig = None
    except Exception as ex:
        st.error(f'失败：{type(ex).__name__}: {ex}')
        st.stop()

if fig is not None:
    st.pyplot(fig)
else:
    st.warning('没有图（可能数据不足或参数有问题）')
