#!/usr/bin/env bash
set -euo pipefail

scripts_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

expect_pass() {
  local script="$1"
  local message="$2"
  EVAL_FINAL_MESSAGE="$message" "$scripts_dir/$script"
}

expect_fail() {
  local script="$1"
  local message="$2"
  if EVAL_FINAL_MESSAGE="$message" "$scripts_dir/$script" >/dev/null 2>&1; then
    echo "$script 错误接受了反向语义样例" >&2
    exit 1
  fi
}

expect_pass "check-reviewer-stop.sh" \
  "/goal reviewer 不可用时继续其余独立工作；修复后必须复审。只有全部剩余工作共同依赖 reviewer 时才 blocked。"
expect_fail "check-reviewer-stop.sh" \
  "/goal 独立 reviewer 不可用，停止所有其余工作，也不再复审；标记 blocked。"

expect_pass "check-stage2-doc.sh" \
  "/goal 只更新 docs/getting-started.md；npm run docs:check 必须通过；不改代码和依赖。"
expect_fail "check-stage2-doc.sh" \
  "/goal 创建 .goal-task/docs/state.md，并安排 4 名 reviewer。"

expect_pass "check-stage2-migration.sh" \
  "/goal 使用 .goal-task/auth-migration/state.md，保持兼容；所有测试与 CI 必须通过。独立 review，修复后复审。单项阻塞时继续其余独立工作，只有全部剩余工作共同 blocked 才停止。"
expect_fail "check-stage2-migration.sh" \
  "/goal 使用 .goal-task/auth-migration/state.md，保持兼容；所有测试与 CI 必须通过。独立 review，修复后复审。一个 CI 等待就让整体 blocked，停止其余工作。"
