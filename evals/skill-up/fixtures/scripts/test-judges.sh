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

expect_contract_pass() {
  local profile="$1"
  local message="$2"
  EVAL_FINAL_MESSAGE="$message" "$scripts_dir/check-goal-contract.py" --profile "$profile"
}

expect_contract_fail() {
  local profile="$1"
  local message="$2"
  if EVAL_FINAL_MESSAGE="$message" "$scripts_dir/check-goal-contract.py" --profile "$profile" >/dev/null 2>&1; then
    echo "check-goal-contract.py 错误接受了缺少关键契约的样例 ($profile)" >&2
    exit 1
  fi
}

expect_contract_root_pass() {
  local profile="$1"
  local root="$2"
  "$scripts_dir/check-goal-contract.py" --profile "$profile" --root "$root"
}

expect_contract_source_fail() {
  local profile="$1"
  local source="$2"
  if "$scripts_dir/check-goal-contract.py" --profile "$profile" --source "$source" >/dev/null 2>&1; then
    echo "check-goal-contract.py 错误接受了不完整 Markdown 文档 ($profile)" >&2
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
expect_pass "check-stage2-migration.sh" \
  "/goal 使用 .goal-task/auth-migration/state.md，保持兼容；所有测试与 CI 必须通过。独立评审，修复后复核。单项等待时继续其余不依赖的工作，只有全部剩余工作共同阻塞才停止。"

expect_pass "check-reviewer-stop.sh" \
  "/goal 独立 reviewer 暂不可用时继续其余独立工作；修复后再次审查。只有所有剩余工作共同依赖 reviewer 才整体阻塞。"
expect_pass "check-reviewer-stop.sh" \
  "/goal reviewer 暂不可用时可以继续源码分析和其他不依赖审查的工作；只有 reviewer 成为唯一剩余门禁时才整体 blocked，修复后重新评审。"
expect_pass "check-reviewer-stop.sh" \
  "/goal reviewer unavailable 时继续 independent work；reviewer 是唯一剩余 gate 才 blocked，修复后 re-review。"
expect_pass "check-reviewer-stop.sh" \
  "/goal reviewer 暂不可用时可以继续源码分析和其他不依赖审查的工作；只有 reviewer 成为唯一剩余门禁时才整体 blocked，修复后重新评审。"
expect_fail "check-reviewer-stop.sh" \
  "/goal reviewer 暂不可用，停止所有源码分析和其他工作，之后再处理复审。"

expect_pass "check-parallel-agents.sh" \
  "/goal auth、billing、notifications 并行处理；明确文件归属。共享 schema 和 lockfile 由唯一负责人维护。集成接缝完成后再次运行测试，并安排独立评审。"
expect_pass "check-parallel-agents.sh" \
  "/goal auth、billing、notifications 并行处理；明确 ownership，Agent 0 唯一负责共享 schema 和 lockfile。集成树上重新运行测试，并安排独立只读 reviewer。"
expect_pass "check-parallel-agents.sh" \
  "/goal auth、billing、notifications 并行；Agent 0 是唯一可修改共享 schema/lockfile 的 owner。集成后重跑测试，独立 reviewer 复核。"
expect_pass "check-parallel-agents.sh" \
  "/goal auth、billing、notifications 并行；Agent 0 是唯一可以修改共享 schema/lockfile 的 owner。集成后重跑测试，独立 reviewer 复核。"
expect_pass "check-parallel-agents.sh" \
  "/goal auth、billing、notifications 并行；共享 schema 由唯一 schema owner 维护，lockfile 由唯一 dependency owner 维护。集成后重跑测试，独立 reviewer 复核。"

expect_pass "check-frontend-ui.sh" \
  "/goal 用 Chrome browser_use 走成功和失败流程并保留浏览器证据；分别检查 UI/UX 与可访问性。构建和 DOM 检查不能替代浏览器验收。"

expect_pass "check-confirmation-brief.sh" \
  "请决定是否确认这个 brief；范围和完成证据仍待验证。"

expect_contract_pass "long" \
  "/goal Progress [██░░] 50%（2/4 gates）。This loop: 完成本轮事项；Remaining: 两项；Next: 继续验证。每个里程碑验证后创建 commit，并在下一次报告总结当前完成事项。compaction 前把完成项和下一步写入 state.md。"
expect_contract_fail "long" \
  "/goal 完成迁移并运行测试；当前进度 50%，之后继续处理剩余工作。"
expect_contract_pass "long" \
  "/goal 当前进度 50%（2/4 gates）。本轮完成事项；剩余两项；下一步继续验证。每个里程碑提交 commit；压缩前把完成事项和下一步写入 state.md。"
expect_contract_fail "long" \
  "/goal 当前进度 50%。本轮完成事项；剩余两项；下一步继续验证。每个里程碑提交 commit；压缩前把完成事项和下一步写入 state.md。"
expect_contract_pass "long" \
  "/goal Progress [░░░░] 0%。This loop: 已创建并验证 state.md；Remaining: 核实仓库；Next: 执行 baseline。里程碑 commit。compaction 前将完成项写入 state.md。"
expect_contract_pass "long" \
  "/goal Progress [██░░] 50%（2/4 gates）。This loop: 完成本轮事项，当前完成内容已记录；Remaining: 两项；Next: 继续验证。Do not skip the milestone commit; do not omit an independent reviewer; do not omit the state.md checkpoint；compaction 前写入 state.md。"
expect_contract_pass "long" \
  "/goal Progress [██░░] 50%（2/4 gates）。This loop: 完成本轮事项，当前完成内容已记录；Remaining: 两项；Next: 继续验证。Do not forget to create a milestone commit; do not fail to make the reviewer check; 不要在压缩前忘记写入 state.md。compaction 前写入 state.md。"
expect_contract_pass "long" \
  "/goal Progress [██░░] 50%（2/4 gates）。This loop: 完成本轮事项，当前完成内容已记录；Remaining: 两项；Next: 继续验证。不要跳过里程碑 commit；不要遗漏独立 reviewer；不要忘记 state.md 检查点；leave without state.md checkpoint 是不可接受的。compaction 前写入 state.md。"
expect_contract_pass "long" \
  "/goal Progress [██░░] 50%（2/4 gates）。This loop: 完成本轮事项，当前完成内容已记录；Remaining: 两项；Next: 继续验证。Do not avoid creating a milestone commit; do not avoid the independent reviewer；compaction 前写入 state.md。"
expect_contract_pass "long" \
  "/goal Progress [██░░] 50%（2/4 gates）。This loop: 完成本轮事项，当前完成内容已记录；Remaining: 两项；Next: 继续验证。No skipping the milestone commit; no omitting an independent reviewer; no omitting the state.md checkpoint。compaction 前写入 state.md。"
expect_contract_pass "long" \
  "/goal Progress [██░░] 50%（2/4 gates）。This loop: 完成本轮事项，当前完成内容已记录；Remaining: 两项；Next: 继续验证。Without skipping the milestone commit; without omitting an independent reviewer; without omitting the state.md checkpoint。compaction 前写入 state.md。"
expect_contract_pass "long" \
  "/goal Progress [██░░] 50%（2/4 gates）。This loop: 完成本轮事项，当前完成内容已记录；Remaining: 两项；Next: 继续验证。没有跳过里程碑 commit；没有遗漏独立 reviewer；没有遗漏 state.md 检查点。压缩前写入 state.md。"
expect_contract_fail "long" \
  "/goal Progress [██░░] 50%（2/4 gates）。This loop: 完成本轮事项，当前完成内容已记录；Remaining: 两项；Next: 继续验证。Do not avoid skipping the milestone commit；compaction 前写入 state.md；independent reviewer。"
expect_contract_fail "long" \
  "/goal Progress [██░░] 50%（2/4 gates）。This loop: 完成本轮事项；Remaining: 两项；Next: 继续验证。不要创建 milestone commit；压缩前不要写入 state.md；无需独立 reviewer。"
expect_contract_fail "long" \
  "/goal Progress [██░░] 50%（2/4 gates）。This loop: 完成本轮事项；Remaining: 两项；Next: 继续验证。milestone commit 非必需；state.md checkpoint 可选；独立 reviewer 不是必需门槛。"
expect_contract_fail "long" \
  "/goal Progress [██░░] 50%（2/4 gates）。This loop: 完成本轮事项；Remaining: 两项；Next: 继续验证。no milestone commit; state.md checkpoint is not mandatory; independent reviewer not needed。"
expect_contract_fail "long" \
  "/goal Progress [██░░] 50%（2/4 gates）。This loop: 完成本轮事项；Remaining: 两项；Next: 继续验证。no state.md checkpoint; milestone commit; independent reviewer。"
expect_contract_fail "long" \
  "/goal Progress [██░░] 50%（2/4 gates）。This loop: 完成本轮事项，当前完成内容已记录；Remaining: 两项；Next: 继续验证。Do not forget to avoid creating a milestone commit; compaction 前写入 state.md。independent reviewer。"

expect_contract_pass "parallel" \
  "/goal 并行安排 auth agent 与 billing agent。明确文件 ownership；共享 schema 和 lockfile 由唯一 owner 维护。集成接缝完成后 rerun 测试，并安排 independent reviewer。"
expect_contract_fail "parallel" \
  "/goal 并行让两个 agent 各自修改模块，最后合并。"
expect_contract_pass "parallel" \
  "/goal auth、billing、notifications 并行由三个 agent 负责；明确文件归属。共享 schema 和 lockfile 由唯一负责人维护。集成接缝完成后再次运行测试，并安排独立评审。"

expect_contract_pass "ui" \
  "/goal 用 Chrome browser_use 走成功和失败流程并保存截图；分别检查 UI/UX 与 accessibility。构建和 DOM 检查不能代替浏览器验收。"
expect_contract_fail "ui" \
  "/goal 运行构建和 DOM 检查，确认页面没有问题。"
expect_contract_pass "ui" \
  "/goal 用 Chrome browser_use 走成功和失败流程并保留浏览器证据；分别检查 UI/UX 与可访问性。构建和 DOM 检查不能替代浏览器验收。"

expect_contract_root_pass "long" "$scripts_dir/../contract-artifacts/long"
expect_contract_source_fail "long" "$scripts_dir/../contract-artifacts/long/incomplete.md"

expect_pass "check-native-blocked-scope.sh" \
  "/goal api、worker、web 分开推进；worker 标记 deferred。该项已重试三次并连续三个 goal turns 仍失败。只有所有有意义的剩余工作都依赖同一个条件时，才调用原生 update_goal blocked。"

bad_root="$(mktemp -d /tmp/goal-contract-root.XXXXXX)"
cp "$scripts_dir/../contract-artifacts/long/incomplete.md" "$bad_root/state.md"
if "$scripts_dir/check-goal-contract.py" --profile long --root "$bad_root" >/dev/null 2>&1; then
  echo "check-goal-contract.py 错误接受了不完整 state.md 根目录" >&2
  exit 1
fi
rm -rf "$bad_root"

expect_pass "check-research-brief.sh" \
  "只读研究 brief：证据缺口与架构偏好分开；行为变更 reviewer 不是默认门槛，后续按实际范围决定。"
expect_pass "check-research-brief.sh" \
  "仅分析两个缓存实现，报告证据缺口和偏好；不修改代码、不写入仓库。"
expect_fail "check-research-brief.sh" \
  "研究 brief 需要行为变更 reviewer 作为必须门槛。"
