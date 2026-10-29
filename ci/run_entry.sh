#!/usr/bin/env bash
# 统一的签到入口包装：超时控制 + 可选重试 + 规范化退出码。
#
# 用法：
#   bash ci/run_entry.sh script/kanxue/sign_in.py
#
# 环境变量：
#   PYTHON_BIN             解释器，默认自动探测 python3 / python
#   ENTRY_TIMEOUT_SECONDS  单次运行超时（秒），默认 900；由矩阵按平台覆盖
#   RETRY_MAX              最大尝试次数，默认 1（不重试）。签到类接口普遍非幂等，
#                          盲目重试可能造成重复答题，故默认关闭、需要时显式开启
#   RETRY_DELAY_SECONDS    重试前的等待基数（秒），第 n 次重试等待 n*基数，默认 15
#
# 退出码：
#   0    脚本成功
#   124  触达超时（timeout 命令约定）
#   2    入口文件缺失或用法错误
#   其他 原样透传脚本退出码，便于在 Actions 上定位失败原因
set -uo pipefail

entry="${1:-}"
if [ -z "$entry" ]; then
  echo "::error::用法: bash ci/run_entry.sh <脚本相对路径>"
  exit 2
fi
if [ ! -f "$entry" ]; then
  echo "::error::入口脚本不存在: $entry"
  exit 2
fi

# 解释器探测：镜像里可能只有 python3（Debian/Ubuntu 默认没有 python 别名）
if [ -z "${PYTHON_BIN:-}" ]; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN=python3
  elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN=python
  else
    echo "::error::未找到可用的 Python 解释器（试过 python3 / python）"
    exit 2
  fi
fi

timeout_seconds="${ENTRY_TIMEOUT_SECONDS:-900}"
retry_max="${RETRY_MAX:-1}"
retry_delay="${RETRY_DELAY_SECONDS:-15}"

# 参数健壮性：非数字或小于下限时回落到安全默认值，避免拼错变量导致行为失控
case "$timeout_seconds" in ''|*[!0-9]*) timeout_seconds=900 ;; esac
[ "$timeout_seconds" -lt 30 ] && timeout_seconds=30
case "$retry_max" in ''|*[!0-9]*) retry_max=1 ;; esac
[ "$retry_max" -lt 1 ] && retry_max=1
case "$retry_delay" in ''|*[!0-9]*) retry_delay=15 ;; esac

# 超时命令：优先 GNU timeout；macOS 未装 coreutils 时降级为「无超时 + 明确告警」，
# 而不是让脚本因为缺命令直接失败（本地调试常见场景）。
if command -v timeout >/dev/null 2>&1; then
  RUN_WITH_TIMEOUT=(timeout --signal=TERM --kill-after=20 "${timeout_seconds}s")
else
  echo "::warning::未找到 timeout 命令，本次运行不施加超时限制"
  RUN_WITH_TIMEOUT=()
fi

# 空数组在 bash 3.2 + set -u 下展开会报错，这里用条件分支而不是直接展开。
run_with_timeout() {
  if [ "${#RUN_WITH_TIMEOUT[@]}" -gt 0 ]; then
    "${RUN_WITH_TIMEOUT[@]}" "$@"
  else
    "$@"
  fi
}

attempt=1
rc=0
while :; do
  echo "=========================================================="
  echo "▶ 运行 $entry（第 ${attempt}/${retry_max} 次，超时 ${timeout_seconds}s，解释器 ${PYTHON_BIN}）"
  echo "=========================================================="
  outset=$(date +%s)
  run_with_timeout "$PYTHON_BIN" "$entry"
  rc=$?
  elapsed=$(( $(date +%s) - outset ))
  echo "▶ $entry 退出码: ${rc}，耗时 ${elapsed}s"

  if [ "$rc" -eq 0 ]; then
    break
  fi
  if [ "$rc" -eq 124 ] || [ "$rc" -eq 137 ]; then
    echo "::error::$entry 超过 ${timeout_seconds}s 未结束（退出码 ${rc}），不再重试"
    break
  fi
  if [ "$attempt" -ge "$retry_max" ]; then
    break
  fi

  wait_seconds=$(( attempt * retry_delay ))
  echo "::warning::$entry 第 ${attempt} 次失败（退出码 ${rc}），${wait_seconds}s 后重试"
  sleep "$wait_seconds"
  attempt=$(( attempt + 1 ))
done

exit "$rc"
