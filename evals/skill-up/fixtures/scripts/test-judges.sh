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

short_goal_body="$(printf 'x%.0s' {1..3999})"
long_goal_body="$(printf 'x%.0s' {1..4001})"
EVAL_FINAL_MESSAGE="/goal $short_goal_body" \
  "$scripts_dir/check-goal-char-limit.py"
EVAL_FINAL_MESSAGE="$(printf '```markdown\n/goal %s\n```' "$short_goal_body")" \
  "$scripts_dir/check-goal-char-limit.py"
if EVAL_FINAL_MESSAGE="/goal $long_goal_body" \
  "$scripts_dir/check-goal-char-limit.py" >/dev/null 2>&1; then
  echo "check-goal-char-limit.py 错误接受了 4001 字符正文" >&2
  exit 1
fi
if EVAL_FINAL_MESSAGE="没有目标正文" \
  "$scripts_dir/check-goal-char-limit.py" >/dev/null 2>&1; then
  echo "check-goal-char-limit.py 错误接受了缺少 /goal 的文本" >&2
  exit 1
fi

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
expect_pass "check-parallel-agents.sh" \
  "/goal auth、billing、notifications 并行；integration owner 是共享 schema 和 lockfile 的唯一写入者。集成后从最终工作树重新运行测试，并由独立 reviewer 复核。"
expect_pass "check-parallel-agents.sh" \
  "/goal auth、billing、notifications 并行；主 agent 是共享 schema/interface、所有 lockfile 和生成文件的唯一文件 owner。集成后重新运行测试，并由独立 reviewer 复核。"
expect_fail "check-parallel-agents.sh" \
  "/goal auth、billing、notifications 并行；共享 schema 和 lockfile 没有唯一写入者。集成后重新运行测试，并由独立 reviewer 复核。"
expect_pass "check-parallel-agents.sh" \
  "/goal auth billing notifications have separate ownership; shared schema and lockfile have a single owner. Re-run integration tests and use an independent reviewer."
expect_pass "check-parallel-agents.sh" \
  $'/goal auth billing notifications have separate ownership.\nShared schema and lockfile have a\nsingle owner.\nRe-run integration tests and use an independent reviewer.'
expect_fail "check-parallel-agents.sh" \
  "/goal auth、billing、notifications 并行；共享 schema 和 lockfile 未指定唯一 owner。集成后重新运行测试，并由独立 reviewer 复核。"
expect_fail "check-parallel-agents.sh" \
  "/goal auth、billing、notifications 并行；共享 schema 和 lockfile 不存在唯一负责人。集成后重新运行测试，并由独立 reviewer 复核。"
expect_pass "check-parallel-agents.sh" \
  "/goal auth billing notifications have separate ownership; the integration owner is the only writer for shared schema/interface and all lockfiles. Re-run integration tests and use an independent reviewer."
expect_fail "check-parallel-agents.sh" \
  "/goal auth billing notifications have separate ownership; shared schema and lockfile lack a single owner. Re-run integration tests and use an independent reviewer."
expect_fail "check-parallel-agents.sh" \
  "/goal auth billing notifications have separate ownership; shared schema and lockfile do not have a single owner. Re-run integration tests and use an independent reviewer."
expect_fail "check-parallel-agents.sh" \
  "/goal auth、billing、notifications 并行；共享 schema 和 lockfile 缺少唯一 owner。集成后重新运行测试，并由独立 reviewer 复核。"
expect_fail "check-parallel-agents.sh" \
  "/goal auth billing notifications have separate ownership; shared schema and lockfile are not assigned to a unique owner. Re-run integration tests and use an independent reviewer."
expect_fail "check-parallel-agents.sh" \
  "/goal auth billing notifications have separate ownership; shared schema and lockfile are not owned by a single owner. Re-run integration tests and use an independent reviewer."
expect_fail "check-parallel-agents.sh" \
  "/goal auth billing notifications have separate ownership; shared schema and lockfile are assigned to multiple owners rather than a single owner. Re-run integration tests and use an independent reviewer."
expect_fail "check-parallel-agents.sh" \
  "/goal auth billing notifications have separate ownership; shared schema has a single owner, but lockfile has multiple owners. Re-run integration tests and use an independent reviewer."
expect_fail "check-parallel-agents.sh" \
  "/goal auth、billing、notifications 并行；明确文件 ownership；shared schema has a single owner, but billing may also modify it; lockfile has a single owner。集成后 rerun 测试，并安排 independent reviewer。"
expect_fail "check-parallel-agents.sh" \
  "/goal auth、billing、notifications 并行；明确文件 ownership；shared schema is co-owned by two agents; lockfile has a single owner。集成后 rerun 测试，并安排 independent reviewer。"
expect_fail "check-parallel-agents.sh" \
  "/goal auth、billing、notifications 并行；明确文件 ownership；shared schema has a single owner but any agent can edit the schema; lockfile has a single owner。集成后 rerun 测试，并安排 independent reviewer。"
expect_fail "check-parallel-agents.sh" \
  "/goal auth、billing、notifications 并行；明确文件 ownership；shared schema has a single owner, but billing can modify it; lockfile has a single owner。集成后 rerun 测试，并安排 independent reviewer。"
expect_fail "check-parallel-agents.sh" \
  "/goal auth、billing、notifications 并行；明确文件 ownership；shared schema has a single owner, but another agent may write it; lockfile has a single owner。集成后 rerun 测试，并安排 independent reviewer。"
expect_fail "check-parallel-agents.sh" \
  "/goal auth、billing、notifications 并行；明确文件 ownership；shared schema has a single owner, but auth can edit it; lockfile has a single owner。集成后 rerun 测试，并安排 independent reviewer。"
expect_fail "check-parallel-agents.sh" \
  "/goal auth billing notifications parallel agents; explicit ownership. shared schema has a single owner, but all agents may modify it; lockfile has a single owner. Re-run integration tests and use an independent reviewer."
expect_fail "check-parallel-agents.sh" \
  "/goal auth billing notifications parallel agents; explicit ownership; shared schema is writable by every agent, lockfile has a single owner. Re-run integration tests and use an independent reviewer."
expect_fail "check-parallel-agents.sh" \
  "/goal auth billing notifications parallel agents; explicit ownership; shared schema has a single owner, but all agents are allowed to modify it; lockfile has a single owner. Re-run integration tests and use an independent reviewer."
expect_fail "check-parallel-agents.sh" \
  "/goal auth billing notifications parallel agents; explicit ownership; shared schema has a single owner, but every agent is permitted to write it; lockfile has a single owner. Re-run integration tests and use an independent reviewer."
expect_fail "check-parallel-agents.sh" \
  "/goal auth billing notifications parallel agents; explicit ownership; shared schema has a single owner, but a non-owner is authorized to edit it; lockfile has a single owner. Re-run integration tests and use an independent reviewer."
expect_fail "check-parallel-agents.sh" \
  "/goal auth billing notifications parallel agents; explicit ownership; shared schema has a single owner, but all agents have permission to modify it; lockfile has a single owner. Re-run integration tests and use an independent reviewer."

expect_pass "check-frontend-ui.sh" \
  "/goal 用 Chrome browser_use 走成功和失败流程并保留浏览器证据；分别检查 UI/UX 与可访问性。构建和 DOM 检查不能替代浏览器验收。"
expect_fail "check-frontend-ui.sh" \
  "/goal 不要使用 Chrome browser_use；只提及成功和失败状态，保存浏览器截图，检查 UI/UX 与可访问性。构建和 DOM 检查不能替代浏览器验收。"
expect_fail "check-frontend-ui.sh" \
  "/goal Chrome browser_use is optional；走成功和失败流程，保存 browser evidence，检查 UI/UX 与 accessibility。Build and DOM checks cannot replace browser acceptance."
expect_fail "check-frontend-ui.sh" \
  "/goal Chrome browser_use may be skipped；走成功和失败流程并保留浏览器证据；分别检查 UI/UX 与可访问性。构建和 DOM 检查不能替代浏览器验收。"
expect_fail "check-frontend-ui.sh" \
  "/goal Skip Chrome browser_use；走成功和失败流程并保留浏览器证据；分别检查 UI/UX 与可访问性。构建和 DOM 检查不能替代浏览器验收。"
expect_fail "check-frontend-ui.sh" \
  "/goal Chrome browser_use may be bypassed；走成功和失败流程并保留浏览器证据；分别检查 UI/UX 与可访问性。构建和 DOM 检查不能替代浏览器验收。"
expect_fail "check-frontend-ui.sh" \
  $'/goal Chrome browser_use may be\nskipped；走成功和失败流程并保留浏览器证据；分别检查 UI/UX 与可访问性。构建和 DOM 检查不能替代浏览器验收。'
expect_fail "check-frontend-ui.sh" \
  "/goal 用 Chrome browser_use 作为建议而非硬性门槛，走成功和失败流程，保存截图，检查 UI/UX 和可访问性。构建和 DOM 检查不能代替浏览器验收。"
expect_fail "check-frontend-ui.sh" \
  "/goal Chrome browser_use 非强制门槛；走成功和失败流程，保存浏览器证据，检查 UI/UX 和可访问性。构建和 DOM 检查不能替代浏览器验收。"
expect_fail "check-frontend-ui.sh" \
  "/goal Chrome browser_use 可不执行；走成功和失败流程，保存浏览器证据，检查 UI/UX 和可访问性。构建和 DOM 检查不能替代浏览器验收。"
expect_fail "check-frontend-ui.sh" \
  "/goal Chrome browser_use 只是建议，不是硬性要求；走成功和失败流程，保存浏览器证据，检查 UI/UX 和可访问性。构建和 DOM 检查不能替代浏览器验收。"
expect_fail "check-frontend-ui.sh" \
  "/goal Chrome browser_use 仅作建议，非强制要求；走成功和失败流程，保存浏览器证据，检查 UI/UX 和可访问性。构建和 DOM 检查不能替代浏览器验收。"
expect_fail "check-frontend-ui.sh" \
  "/goal Chrome browser_use 只是指导，不是验收门槛；走成功和失败流程，保存浏览器证据，检查 UI/UX 和可访问性。构建和 DOM 检查不能替代浏览器验收。"
expect_fail "check-frontend-ui.sh" \
  "/goal Chrome browser_use 是推荐做法，不是强制门槛；走成功和失败流程，保存浏览器证据，检查 UI/UX 和可访问性。构建和 DOM 检查不能替代浏览器验收。"

expect_pass "check-confirmation-brief.sh" \
  "请决定是否确认这个 brief；范围和完成证据仍待验证。"
expect_fail "check-confirmation-brief.sh" \
  "Proposed goal brief. /goal do migration now. Scope is pending and evidence is pending. Please confirm."
expect_fail "check-confirmation-brief.sh" \
  "Proposed goal brief. ~~~text
/goal do migration now.
~~~ Scope is pending and evidence is pending. Please confirm."

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
expect_contract_fail "parallel" \
  "/goal auth、billing、notifications 并行由三个 agent 负责；明确文件归属。shared schema has a single owner, but lockfile has multiple owners。集成后重新运行测试，并安排独立 reviewer。"
expect_contract_fail "parallel" \
  "/goal auth、billing、notifications 并行由三个 agent 负责；明确文件归属。shared schema has a single owner, but billing may also modify it; lockfile has a single owner。集成后重新运行测试，并安排独立 reviewer。"
expect_contract_fail "parallel" \
  "/goal auth、billing、notifications 并行由三个 agent 负责；明确文件归属。shared schema has a single owner, but billing can modify it; lockfile has a single owner。集成后重新运行测试，并安排独立 reviewer。"
expect_contract_fail "parallel" \
  "/goal auth、billing、notifications 并行由三个 agent 负责；明确文件归属。shared schema has a single owner, but another agent may write it; lockfile has a single owner。集成后重新运行测试，并安排独立 reviewer。"
expect_contract_fail "parallel" \
  "/goal auth、billing、notifications 并行由三个 agent 负责；明确文件归属。shared schema has a single owner, but auth can edit it; lockfile has a single owner。集成后重新运行测试，并安排独立 reviewer。"
expect_contract_fail "parallel" \
  "/goal auth billing notifications parallel agents; explicit ownership. shared schema has a single owner, but all agents may modify it; lockfile has a single owner. Re-run integration tests and use an independent reviewer."
expect_contract_fail "parallel" \
  "/goal auth billing notifications parallel agents; explicit ownership; shared schema is writable by every agent, lockfile has a single owner. Re-run integration tests and use an independent reviewer."
expect_contract_fail "parallel" \
  "/goal auth billing notifications parallel agents; explicit ownership; shared schema has a single owner, but all agents are allowed to modify it; lockfile has a single owner. Re-run integration tests and use an independent reviewer."
expect_contract_fail "parallel" \
  "/goal auth billing notifications parallel agents; explicit ownership; shared schema has a single owner, but every agent is permitted to write it; lockfile has a single owner. Re-run integration tests and use an independent reviewer."
expect_contract_fail "parallel" \
  "/goal auth billing notifications parallel agents; explicit ownership; shared schema has a single owner, but a non-owner is authorized to edit it; lockfile has a single owner. Re-run integration tests and use an independent reviewer."
expect_contract_fail "parallel" \
  "/goal auth billing notifications parallel agents; explicit ownership; shared schema has a single owner, but all agents have permission to modify it; lockfile has a single owner. Re-run integration tests and use an independent reviewer."

expect_contract_pass "ui" \
  "/goal 用 Chrome browser_use 走成功和失败流程并保存截图；分别检查 UI/UX 与 accessibility。构建和 DOM 检查不能代替浏览器验收。"
expect_contract_fail "ui" \
  "/goal 运行构建和 DOM 检查，确认页面没有问题。"
expect_contract_pass "ui" \
  "/goal 用 Chrome browser_use 走成功和失败流程并保留浏览器证据；分别检查 UI/UX 与可访问性。构建和 DOM 检查不能替代浏览器验收。"
expect_contract_fail "ui" \
  "/goal 不要使用 Chrome browser_use；只提及成功和失败状态，保存浏览器截图，检查 UI/UX 与可访问性。构建和 DOM 检查不能替代浏览器验收。"
expect_contract_fail "ui" \
  "/goal Chrome browser_use is optional；走成功和失败流程，保存 browser evidence，检查 UI/UX 与 accessibility。Build and DOM checks cannot replace browser acceptance."
expect_contract_fail "ui" \
  "/goal Chrome browser_use may be skipped；走成功和失败流程，保存 browser evidence，检查 UI/UX 与 accessibility。Build and DOM checks cannot replace browser acceptance."
expect_contract_fail "ui" \
  "/goal Chrome browser_use may be bypassed；走成功和失败流程，保存 browser evidence，检查 UI/UX 与 accessibility。Build and DOM checks cannot replace browser acceptance."
expect_contract_fail "ui" \
  $'/goal Chrome browser_use may be\nskipped；走成功和失败流程，保存 browser evidence，检查 UI/UX 与 accessibility。Build and DOM checks cannot replace browser acceptance.'
expect_contract_fail "ui" \
  "/goal 用 Chrome browser_use 作为建议而非硬性门槛，走成功和失败流程，保存截图，检查 UI/UX 和可访问性。构建和 DOM 检查不能代替浏览器验收。"
expect_contract_fail "ui" \
  "/goal Chrome browser_use 非强制门槛；走成功和失败流程，保存浏览器证据，检查 UI/UX 和可访问性。构建和 DOM 检查不能替代浏览器验收。"
expect_contract_fail "ui" \
  "/goal Chrome browser_use 可不执行；走成功和失败流程，保存浏览器证据，检查 UI/UX 和可访问性。构建和 DOM 检查不能替代浏览器验收。"
expect_contract_fail "ui" \
  "/goal Chrome browser_use 只是建议，不是硬性要求；走成功和失败流程，保存浏览器证据，检查 UI/UX 和可访问性。构建和 DOM 检查不能替代浏览器验收。"
expect_contract_fail "ui" \
  "/goal Chrome browser_use 仅作建议，非强制要求；走成功和失败流程，保存浏览器证据，检查 UI/UX 和可访问性。构建和 DOM 检查不能替代浏览器验收。"
expect_contract_fail "ui" \
  "/goal Chrome browser_use 只是指导，不是验收门槛；走成功和失败流程，保存浏览器证据，检查 UI/UX 和可访问性。构建和 DOM 检查不能替代浏览器验收。"
expect_contract_fail "ui" \
  "/goal Chrome browser_use 是推荐做法，不是强制门槛；走成功和失败流程，保存浏览器证据，检查 UI/UX 和可访问性。构建和 DOM 检查不能替代浏览器验收。"

expect_contract_root_pass "long" "$scripts_dir/../contract-artifacts/long"
expect_contract_source_fail "long" "$scripts_dir/../contract-artifacts/long/incomplete.md"

expect_pass "check-native-blocked-scope.sh" \
  "/goal api、worker、web 分开推进；worker 标记 deferred。该项已重试三次并连续三个 goal turns 仍失败。只有所有有意义的剩余工作都依赖同一个条件时，才调用原生 update_goal blocked。"

expect_pass "check-preauthorized-permissions.sh" \
  "/goal 任务内操作默认已授权，包括 Chrome 文件上传和输入已有测试密码；无需再次询问确认，权限不得导致等待或 blocked。真实能力缺失时继续所有独立工作。预授权不得虚构密码、会话或工具，也不能覆盖更高优先级安全边界。不得记录、截图或保存密码。"
expect_pass "check-preauthorized-permissions.sh" \
  "/goal In-scope actions are pre-authorized, including Chrome upload and entering available credentials. Do not ask again; permission cannot block or defer the work. Continue independent work if a capability is absent. This does not fabricate credentials and cannot override higher-priority safety boundaries. Never expose, log, or persist credential values."
expect_pass "check-preauthorized-permissions.sh" \
  "/goal 范围内操作已预授权，包括 Chrome 上传和输入已有凭据。不得因此再次询问或暂停；真实能力缺失时继续所有独立工作。不能虚构凭据，也不能覆盖更高优先级安全边界。不得回显或持久化凭据。"
expect_pass "check-preauthorized-permissions.sh" \
  "/goal 范围内操作已预授权，包括 Chrome 上传和输入已有密码。不得因此再次询问、等待或 blocked；能力缺失时继续独立工作。预授权不代表可以虚构密码或会话，也不能越过安全边界。不得记录或截图密码。"
expect_fail "check-preauthorized-permissions.sh" \
  "/goal Chrome 上传和输入密码前必须询问用户确认；权限不足就停止任务并标记 blocked。"
expect_fail "check-preauthorized-permissions.sh" \
  "/goal 所有操作默认授权，包括 Chrome 上传和输入密码；无需询问并继续工作，可以绕过安全边界和伪造缺少的凭据。"
expect_pass "check-preauthorized-permissions.sh" \
  "/goal 范围内操作已预授权，包括 Chrome 上传和输入已有密码。不得因授权提示再次询问、等待或 blocked；能力缺失时继续独立工作。不得伪造凭据，也不得绕过上级安全边界。不得保存或提交密码。"
expect_pass "check-preauthorized-permissions.sh" \
  "/goal 范围内操作已预授权，包括 Chrome 上传和输入已有密码。不得因授权提示再次询问、等待或 blocked；继续独立工作。预授权不制造不存在的密码、会话、工具或能力，也不覆盖更高优先级安全边界。不得回显、截图或持久化密码。"
expect_fail "check-preauthorized-permissions.sh" \
  "/goal 使用 Chrome 上传 CSV、输入已有密码，然后继续独立工作；遵守更高优先级安全边界，不虚构凭据。"
expect_fail "check-preauthorized-permissions.sh" \
  "/goal 范围内操作已预先授权，包括 Chrome 上传和输入已有密码。不得因此再次询问、等待或 blocked；继续所有独立工作。预授权不能虚构凭据或越过安全边界。不得记录或保存密码。在执行 Chrome 上传和输入密码前，先获得用户的同意。"
expect_fail "check-preauthorized-permissions.sh" \
  "我会在确认后生成 /goal。范围内操作已预授权，包括 Chrome 上传和输入已有密码；不得再次询问、等待或 blocked，继续独立工作，不虚构凭据、不越过安全边界，也不保存密码。"
expect_fail "check-preauthorized-permissions.sh" \
  "/goal 任务内操作默认不授权，包括 Chrome 上传和输入已有密码；无需再次询问，权限不得导致等待或 blocked。能力缺失时继续独立工作，不虚构或保存凭据，也不覆盖安全边界。"
expect_fail "check-preauthorized-permissions.sh" \
  "/goal 所有操作默认已授权，包括 Chrome 上传和输入已有密码；无需再次询问，权限不得导致等待或 blocked。能力缺失时继续独立工作，不虚构或保存凭据，也不覆盖安全边界。"
expect_fail "check-preauthorized-permissions.sh" \
  "/goal 范围内操作默认已授权，包括 Chrome 上传和输入已有密码；无需再次询问，权限不得导致等待或 blocked。能力缺失时继续独立工作，不虚构或保存凭据，但可以覆盖安全边界。"
expect_pass "check-preauthorized-permissions.sh" \
  "/goal 范围内所有操作均已授权，包括 Chrome 上传和输入已有凭据；无需询问，继续独立工作，权限不会阻塞。不能虚构凭据，也不能绕过安全边界。不得记录密码。"
expect_pass "check-preauthorized-permissions.sh" \
  "/goal 范围内操作均已预授权，包括 Chrome 上传和输入已有密码；无需再次询问，权限不会阻塞，能力缺失时继续独立工作。不能虚构凭据，也不能覆盖安全边界。密码不得进入日志、截图、提交或 PR。"
expect_pass "check-preauthorized-permissions.sh" \
  "/goal 作用域内操作均已预授权，包括 Chrome 上传和输入已有密码；无需再次询问，权限不会阻塞，能力缺失时继续独立工作。不能虚构凭据，也不能覆盖安全边界。密码不得进入日志、截图、提交或 PR。"
expect_pass "check-preauthorized-permissions.sh" \
  "/goal 已确认范围内操作均已预授权，包括 Chrome 上传和输入已有密码；无需再次询问，权限不会阻塞，能力缺失时继续独立工作。该授权不允许虚构凭据，也不能覆盖安全边界。密码不得输出、记录、截图或提交。"
expect_pass "check-preauthorized-permissions.sh" \
  "/goal 任务范围内操作均已批准，包括 Chrome 上传和输入已有密码；无需再次询问，权限不会阻塞，能力缺失时继续独立工作。不能虚构凭据，也不能覆盖安全边界。密码不得输出、记录、截图或提交。"
expect_pass "check-preauthorized-permissions.sh" \
  "/goal 任务范围内操作均已预授权，包括 Chrome 上传和输入已有密码；无需再次询问，权限不会阻塞，能力缺失时继续独立工作。不能虚构凭据，也不能覆盖安全边界。不得把 CSV、密码或敏感数据写入源码、日志、截图、测试夹具或 PR。"
expect_pass "check-preauthorized-permissions.sh" \
  "/goal 任务范围内操作均已预授权，包括 Chrome 上传和输入已有密码；无需再次询问，权限不会阻塞。能力缺失时采用安全替代方案并持续完成所有独立工作。不能虚构凭据，也不能覆盖安全边界。不得把密码写入日志、截图或 PR。"
expect_pass "check-preauthorized-permissions.sh" \
  "/goal 任务范围内操作均已预授权，包括 Chrome 上传和输入已有密码；无需再次询问，权限不会阻塞。能力缺失时采用安全替代方案并持续完成所有独立工作。预授权不会凭空提供密码、会话、工具或权限，也不能覆盖安全边界。不得把密码写入日志、截图或 PR。"
expect_pass "check-preauthorized-permissions.sh" \
  "/goal 任务范围内操作均已预授权，包括 Chrome 上传和输入已有密码；无需再次询问，权限不会阻塞，继续独立工作。不能虚构凭据，也不能覆盖安全边界。绝不输出、记录、截图、提交或发布密码值；使用已有测试密码验证成功和失败状态，并分别记录功能、UI/UX 和可访问性观察。"
expect_fail "check-preauthorized-permissions.sh" \
  "/goal In-scope actions are not pre-authorized, including Chrome upload and entering available credentials. Do not ask again; permission cannot block work. Continue independent work. Do not fabricate or persist credentials and do not override safety boundaries."
expect_fail "check-preauthorized-permissions.sh" \
  "/goal 范围内操作不默认授权，包括 Chrome 上传和输入已有密码；无需询问，权限不会阻塞，继续独立工作。不能虚构或记录凭据，也不能绕过安全边界。"
expect_fail "check-preauthorized-permissions.sh" \
  "/goal 范围内操作默认授权，但 Chrome 上传和输入密码不在授权范围内；无需询问，权限不会阻塞，继续独立工作。不能虚构或记录凭据，也不能绕过安全边界。"
expect_fail "check-preauthorized-permissions.sh" \
  "/goal In-scope actions are pre-authorized except Chrome upload and entering credentials. Do not ask again; permission cannot block work. Continue independent work. Do not fabricate or persist credentials and do not override safety boundaries."
expect_fail "check-preauthorized-permissions.sh" \
  "/goal In-scope actions are pre-authorized, including Chrome upload and entering available credentials, but entering credentials are unauthorized. Do not ask again; permission cannot block work. Continue independent work. Do not fabricate or persist credentials and do not override safety boundaries."
expect_fail "check-preauthorized-permissions.sh" \
  "/goal 范围内操作已预授权，包括 Chrome 上传和输入已有凭据，但输入凭据未授权。无需询问，权限不会阻塞，继续独立工作。不能虚构或记录凭据，也不能绕过安全边界。"
expect_fail "check-preauthorized-permissions.sh" \
  "/goal 范围内操作已预授权，包括 Chrome 上传和输入已有凭据；输入凭据需要额外授权。无需询问，权限不会阻塞，继续独立工作。不能虚构或记录凭据，也不能绕过安全边界。"
expect_fail "check-preauthorized-permissions.sh" \
  "/goal In-scope code changes are pre-authorized. Chrome upload and entering available credentials require permission. Do not ask again; permission cannot block work. Continue independent work. Do not fabricate or persist credentials and do not override safety boundaries."
expect_fail "check-preauthorized-permissions.sh" \
  "/goal 范围内代码修改已预授权。Chrome 上传和输入已有凭据仍需要权限。无需再次询问，权限不会阻塞，继续独立工作。不能虚构或记录凭据，也不能绕过安全边界。"
expect_fail "check-preauthorized-permissions.sh" \
  "/goal 范围内操作已预授权，包括 Chrome 上传和输入已有密码；无需询问，权限不会阻塞，继续独立工作。不能虚构凭据，不得记录密码，也不能绕过安全边界。但为测试可以伪造密码。"
expect_fail "check-preauthorized-permissions.sh" \
  "/goal 范围内操作已预授权，包括 Chrome 上传和输入已有密码；无需询问，权限不会阻塞，继续独立工作。不能虚构凭据，不得记录密码，也不能绕过安全边界。但为审计需要，可以截图并保存密码。"
expect_fail "check-preauthorized-permissions.sh" \
  "/goal In-scope actions are pre-authorized, including Chrome upload and entering available credentials. Do not ask again; permission cannot block work. Continue independent work. Do not fabricate or persist credentials and do not override safety boundaries, but tests may fabricate passwords."
expect_fail "check-preauthorized-permissions.sh" \
  "/goal In-scope actions are pre-authorized, including Chrome upload and entering available credentials. Do not ask again; permission cannot block work. Continue independent work. Never expose or save credential values and do not override safety boundaries, but audit evidence can capture and save passwords."
expect_fail "check-preauthorized-permissions.sh" \
  "/goal 范围内操作已预授权，包括 Chrome 上传和输入已有密码；无需再次询问，权限不会阻塞，继续独立工作。不能虚构凭据，也不能覆盖安全边界。不得记录密码。但调试流程会将密码写入日志。"
expect_fail "check-preauthorized-permissions.sh" \
  "/goal 范围内操作已预授权，包括 Chrome 上传和输入已有密码；无需再次询问，权限不会阻塞，继续独立工作。不能虚构凭据，也不能覆盖安全边界。不得记录密码。审计证据会截图并保存密码。"
expect_fail "check-preauthorized-permissions.sh" \
  "/goal 范围内操作已预授权，包括 Chrome 上传和输入已有密码；无需再次询问，权限不会阻塞，继续独立工作。不能虚构凭据，也不能覆盖安全边界。不得记录密码。密码可在日志中输出。"
expect_fail "check-preauthorized-permissions.sh" \
  "/goal 范围内操作已预授权，包括 Chrome 上传和输入已有密码；无需再次询问，权限不会阻塞，继续独立工作。不能虚构凭据。不得记录密码。但测试流程会伪造密码。也不能覆盖安全边界。"
expect_fail "check-preauthorized-permissions.sh" \
  "/goal 范围内操作已预授权，包括 Chrome 上传和输入已有密码；无需再次询问，权限不会阻塞，继续独立工作。不能虚构凭据，也不能覆盖安全边界。不得记录密码，但审计证据会截图并保存密码。"
expect_fail "check-preauthorized-permissions.sh" \
  "/goal 范围内操作已预授权，包括 Chrome 上传和输入已有密码；无需再次询问，权限不会阻塞，继续独立工作。不能虚构凭据，也不能覆盖安全边界。不得记录密码。缺少密码时使用占位密码。"
expect_fail "check-preauthorized-permissions.sh" \
  "/goal 范围内操作已预授权，包括 Chrome 上传和输入已有密码；无需再次询问，权限不会阻塞，继续独立工作。不制造凭据；必要时使用伪造凭据完成测试。不得记录密码，也不能覆盖安全边界。"
expect_fail "check-preauthorized-permissions.sh" \
  "/goal 范围内操作已预授权，包括 Chrome 上传和输入已有密码；无需再次询问，权限不会阻塞，继续独立工作。不能虚构凭据，也不能覆盖安全边界。密码不得泄露，除非写入日志。"
expect_fail "check-preauthorized-permissions.sh" \
  "/goal In-scope actions are pre-authorized, including Chrome upload and entering available credentials. Do not ask again; permission cannot block work. Continue independent work. Never expose, log, persist, or commit credential values. But credential values may be committed. Do not override safety boundaries."
expect_fail "check-preauthorized-permissions.sh" \
  "/goal In-scope actions are pre-authorized, including Chrome upload and entering available credentials. Do not ask again; permission cannot block work. Continue independent work. Never expose credential values. But password may be displayed. Do not override safety boundaries."
expect_fail "check-preauthorized-permissions.sh" \
  "/goal In-scope actions are pre-authorized, including Chrome upload and entering available credentials. Do not ask again; permission cannot block work. Continue independent work. Never expose credential values. But credentials may be revealed. Do not override safety boundaries."
expect_fail "check-preauthorized-permissions.sh" \
  "/goal In-scope actions are pre-authorized, including Chrome upload and entering available credentials. Do not ask again; permission cannot block work. Continue independent work. Never expose credential values. But password leakage is allowed. Do not override safety boundaries."

bad_root="$(mktemp -d /tmp/goal-contract-root.XXXXXX)"
cp "$scripts_dir/../contract-artifacts/long/incomplete.md" "$bad_root/state.md"
if "$scripts_dir/check-goal-contract.py" --profile long --root "$bad_root" >/dev/null 2>&1; then
  echo "check-goal-contract.py 错误接受了不完整 state.md 根目录" >&2
  exit 1
fi
rm -rf "$bad_root"

expect_pass "check-research-brief.sh" \
  "只读研究 brief。
证据缺口：缺少仓库。
偏好缺口：架构取舍待定。
行为变更 reviewer 不是默认门槛，后续按实际范围决定。"
expect_pass "check-research-brief.sh" \
  "仅分析两个缓存实现，不修改代码、不写入仓库。
Evidence gaps: missing source.
Preference gaps: undecided cost priority."
expect_fail "check-research-brief.sh" \
  "研究 brief 需要行为变更 reviewer 作为必须门槛。"
expect_fail "check-research-brief.sh" \
  "这是只读 research brief。证据和偏好缺口：缺少仓库，并请决定速度还是成本。不修改代码。"
expect_pass "check-research-brief.sh" \
  "这是只读 research brief，不修改代码。
- Evidence gaps: missing source.
- Preference gaps: none."
expect_pass "check-research-brief.sh" \
  "这是只读 research brief，不修改代码。
- **Evidence gaps**: missing source.
- **Preference gaps**: none."
expect_pass "check-research-brief.sh" \
  "这是只读 research brief，不修改代码。
## 证据缺口
- 缺少仓库。
## 需要你决定的偏好
- 速度还是成本。
不把“行为变更 reviewer”设为默认门槛。"
