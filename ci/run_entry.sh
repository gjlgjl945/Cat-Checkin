#!/usr/bin/env bash
# 统一的签到入口包装：超时控制 + 可选重试 + 规范化退出码。
#
# 用法：
#   bash ci/run_entry.sh script/sf/main.py
#
# 环境变量：
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

timeout_seconds="${ENTRY_TIMEOUT_SECONDS:-900}"
retry_max="${RETRY_MAX:-1}"
retry_delay="${RETRY_DELAY_SECONDS:-15}"

# 参数健壮性：非数字或小于 1 时回落到安全默认值
case "$timeout_seconds" in ''|*[!0-9]*) timeout_seconds=900 ;; esac
[ "$timeout_seconds" -lt 30 ] && timeout_seconds=30
case "$retry_max" in ''|*[!0-9]*) retry_max=1 ;; esac
[ "$retry_max" -lt 1 ] && retry_max=1
case "$retry_delay" in ''|*[!0-9]*) retry_delay=15 ;; esac

attempt=1
rc=0
while :; do
  echo "=========================================================="
  echo "▶ 运行 $entry（第 ${attempt}/${retry_max} 次，超时 ${timeout_seconds}s）"
  echo "=========================================================="
  outset=$(date +%s)
  timeout --signal=TERM --kill-after=20 "${timeout_seconds}s" python "$entry"
  rc=$?
  elapsed=$(( $(date +%s) - outset ))
  echo "▶ $entry 退出码: ${rc}，耗时 ${elapsed}s"

  if [ "$rc" -eq 0 ]; then
    break
  fi
  if [ "$rc" -eq 124 ]; then
    echo "::error::$entry 超过 ${timeout_seconds}s 未结束（退出码 124），不再重试"
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
