#!/bin/bash
# install.sh — experimental-memory-install skill orchestrator (Bash entry).
#
# 实际逻辑全部在 orchestrator.py。本文件只做：
#   1. 找到 python3
#   2. 透传 $GSPD_LANG 环境变量与所有参数到 orchestrator
#
# 这种"单一 Bash 入口 + 厚 Python 实现"是有意为之：agent 端只需要做一次
# Bash 工具调用，不再为每个 lib 函数单独 shell 出去；脚本侧也避免在
# Bash 里手撸 TOML 解析 / SHA 计算 / 原子解压等容易出错的逻辑。
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if ! command -v python3 >/dev/null 2>&1; then
    echo "[experimental-memory-install] FATAL: python3 not found in PATH" >&2
    echo "[experimental-memory-install] (need Python 3.11+ for tomllib; or 3.x with tomli)" >&2
    exit 99
fi

exec python3 "$SCRIPT_DIR/orchestrator.py" --offline "$@"
