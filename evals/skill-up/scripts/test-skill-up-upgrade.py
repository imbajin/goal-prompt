#!/usr/bin/env python3
"""用确定性引擎验证 skill-up CLI；不调用模型，不代表 Skill 行为通过。"""

import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile


def run_smoke(binary, root):
    root.mkdir(parents=True, exist_ok=True)
    (root / "SKILL.md").write_text("---\nname: upgrade-probe\ndescription: 确定性 CLI 协议夹具\n---\n")
    engine = root / "engine.py"
    engine.write_text('''import json
from pathlib import Path
counter = Path("executions.txt")
assert not counter.exists(), "被测 Agent 不应重复执行"
counter.write_text("1")
Path("shared.txt").write_text("original")
print(json.dumps({"final_message": "completed", "exit_code": 0}))
''')
    first = root / "first.sh"
    first.write_text('''#!/bin/sh
set -eu
test "$(cat executions.txt)" = 1
test "$(cat shared.txt)" = original
printf changed > shared.txt
echo '受控失败：后续 Judge 仍须运行'
exit 1
''')
    second = root / "second.sh"
    second.write_text('''#!/bin/sh
set -eu
test "$(cat executions.txt)" = 1
test "$(cat shared.txt)" = changed
echo '确认同一次 Agent 输出与顺序共享文件系统'
''')
    for script in (first, second):
        script.chmod(0o755)
    (root / "case.yaml").write_text('''id: shared-runtime
title: 多 Judge 的受控失败及共享环境
input:
  prompt: 执行确定性夹具
''')
    config = f'''schema_version: v1alpha1
environment:
  type: none
mcp:
  servers: []
engine:
  name: deterministic-upgrade-probe
  custom:
    transport: local
    response_format: session_result
    local:
      command: python3
      args: [{json.dumps(str(engine))}]
judges:
  - id: functional
    type: script
    script_path: {json.dumps(str(first))}
  - id: shared-readback
    type: script
    script_path: {json.dumps(str(second))}
cases:
  files: [case.yaml]
  defaults:
    timeout_seconds: 30
    max_turns: 1
  parallelism: 1
benchmark:
  enabled: false
report:
  formats: [json]
'''
    config_path = root / "eval.yaml"
    config_path.write_text(config)
    # 禁用用户配置发现；不读取、复制或记录宿主凭据。
    user_config = root / "empty-user.yaml"
    user_config.write_text("{}\n")
    for gate in (False, True):
        if gate:
            with (root / "case.yaml").open("a") as stream:
                stream.write('expect:\n  must_contain: ["absent-required-marker"]\n')
        out = root / ("gate-failure" if gate else "member-failure")
        command = [binary, "--config", str(user_config), "run", str(config_path),
                   "--output-dir", str(out), "--event-log", str(out) + "-events.jsonl"]
        result = subprocess.run(command, text=True, capture_output=True, timeout=90)
        (root / (out.name + ".log")).write_text(result.stdout + result.stderr)
        assert result.returncode == 1, (command, result.returncode, result.stdout, result.stderr)
        candidates = list(out.rglob("evaluation.json"))
        assert len(candidates) == 1, candidates
        evaluation = json.loads(candidates[0].read_text())
        grading = json.loads(candidates[0].with_name("grading.json").read_text())
        assert evaluation["aggregation"]["status"] == "FAIL", evaluation
        statuses = [member["status"] for member in evaluation["judge_results"]]
        assert statuses == (["SKIP", "SKIP"] if gate else ["FAIL", "PASS"]), evaluation
        summary = grading["summary"]
        assert summary["total"] == 2, summary
        assert summary["pass_rate"] == (0 if gate else 0.5), summary
        print(f"{out.name}: aggregation=FAIL judges={statuses} pass_rate={summary['pass_rate']}")
    print("PASS: 单次执行、顺序共享 runtime、失败归因和 expect gate 评分；无模型调用")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary")
    parser.add_argument("--output", type=Path, help="保留配置、输出、判分和日志的目录")
    args = parser.parse_args()
    binary = str(Path(args.binary).resolve()) if os.sep in args.binary else args.binary
    if args.output:
        run_smoke(binary, args.output.resolve())
    else:
        with tempfile.TemporaryDirectory(prefix="goal-prompt-upgrade-") as temporary:
            run_smoke(binary, Path(temporary))
