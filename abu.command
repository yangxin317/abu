#!/bin/bash
# Abu Quant 启动器：双击打开 JupyterLab + 自动加载 start_here.ipynb
set -e

ABU_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ABU_DIR"

if [ ! -d ".venv" ]; then
  echo "[abu] .venv 未找到，请先按 README 完成安装。" >&2
  read -n 1 -s -r -p "按任意键关闭..."
  exit 1
fi

source .venv/bin/activate

export PYTHONPATH="$ABU_DIR:$PYTHONPATH"
export JUPYTER_PREFER_ENV_PATH=1
export PYTHONWARNINGS=ignore

echo "[abu] 工作目录: $ABU_DIR"
echo "[abu] 启动 JupyterLab，浏览器将自动打开。关闭此窗口将停止 JupyterLab。"
echo

exec jupyter lab \
  --notebook-dir="$ABU_DIR" \
  --ServerApp.default_url=/lab/tree/start_here.ipynb \
  --ServerApp.open_browser=True
