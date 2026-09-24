#!/bin/bash
# Abu Quant · Streamlit 启动器：双击打开浏览器，跑回测 dashboard
set -e

ABU_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ABU_DIR"

if [ ! -d ".venv" ]; then
  echo "[abu] .venv 未找到。" >&2
  read -n 1 -s -r -p "按任意键关闭..."
  exit 1
fi

source .venv/bin/activate

export PYTHONPATH="$ABU_DIR:$PYTHONPATH"
export PYTHONWARNINGS=ignore

echo "[abu] 工作目录: $ABU_DIR"
echo "[abu] 启动 Streamlit。浏览器会自动打开。关闭此窗口将停止服务。"
echo

exec streamlit run app/streamlit_app.py \
  --server.headless=false \
  --server.port=8501 \
  --browser.gatherUsageStats=false
