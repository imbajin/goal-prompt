#!/usr/bin/env python3
"""用确定性引擎验证 skill-up CLI；不调用模型，不代表 Skill 行为通过。"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile


CALIBRATION_CASES = ('preauthorized-permissions', 'stage2-migration', 'compaction-checkpoint')


def verify_calibration_receipt(source, samples):
    """Bind the saved live calibration to its inputs; do not infer accuracy."""
    import yaml
    digest = lambda value: hashlib.sha256(json.dumps(value, ensure_ascii=False,
        sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    receipt = json.loads((source/'semantic-calibration-receipt.json').read_text())
    if {s['case_id'] for s in samples} != set(CALIBRATION_CASES) or set(receipt['cases']) != set(CALIBRATION_CASES):
        raise ValueError('calibration case coverage changed; update the explicit calibration plan')
    for case_id in CALIBRATION_CASES:
        case = yaml.safe_load((source/'cases'/f'{case_id}.yaml').read_text())
        judges = [j for j in case['judges'] if j['type'] == 'agent_judge']
        if len(judges) != 1:
            raise ValueError(f'{case_id}: update calibration for the new Judge plan')
        subset = sorted(({k: s[k] for k in ('id', 'expected', 'response', 'files')}
                         for s in samples if s['case_id'] == case_id), key=lambda s: s['id'])
        saved = receipt['cases'][case_id]
        if (saved['case_definition_sha256'] != digest(case) or saved['judge_config_sha256'] != digest(judges[0])
                or saved['fixture_subset_sha256'] != digest(subset)):
            raise ValueError(f'{case_id}: calibration is stale; recalibrate changed inputs')
        if len(subset) != 4:
            raise ValueError(f'{case_id}: calibration requires all four planned samples')
        expected = {s['id']: s['expected'] for s in subset}
        verdicts = saved['verdicts']
        if (len(verdicts) != len(expected) or {v['sample_id'] for v in verdicts} != set(expected)
                or any(v['status'] not in ('PASS', 'FAIL') or v['expected'] != expected[v['sample_id']] for v in verdicts)):
            raise ValueError(f'{case_id}: saved calibration is incomplete or has changed labels')
        agreement = all(v['status'] == v['expected'] for v in verdicts)
        if (saved['all_labels_agree'] != agreement or saved['required_agreement'] != len(expected)
                or saved['observed_agreement'] != sum(v['status'] == v['expected'] for v in verdicts)):
            raise ValueError(f'{case_id}: calibration agreement is misreported')


def contract_judge_smoke(binary, root):
    """Check current production routing with a deliberately failing fake Judge.

    This exercises the SDK plan, not semantic accuracy; the latter requires
    the separately labelled calibration fixtures and a real Judge.
    """
    import yaml
    source = Path(__file__).resolve().parents[1]
    # Parse the reusable fixture in CI; this validates data, not semantic labels.
    samples = yaml.safe_load((source/'fixtures/semantic-calibration.yaml').read_text())['samples']
    assert samples and len({s['id'] for s in samples}) == len(samples)
    assert all(s['expected'] in ('PASS', 'FAIL') and isinstance(s['response'], str)
               and s['files'] and all(isinstance(v, str) for v in s['files'].values()) for s in samples)
    verify_calibration_receipt(source, samples)
    changed = json.loads(json.dumps(samples))
    changed[0]['response'] += '\nchanged input'
    try:
        verify_calibration_receipt(source, changed)
    except ValueError:
        pass
    else:
        raise AssertionError('changed fixture reused a stale calibration receipt')
    reduced = [s for s in samples if s['case_id'] != CALIBRATION_CASES[0]]
    try:
        verify_calibration_receipt(source, reduced)
    except ValueError:
        pass
    else:
        raise AssertionError('removed calibration case silently reduced coverage')
    for case_id in CALIBRATION_CASES:
        case = yaml.safe_load((source/'cases'/f'{case_id}.yaml').read_text())
        folder = root / case_id
        folder.mkdir()
        (folder/'SKILL.md').write_text('---\nname: contract-routing-probe\ndescription: Zero-model routing fixture\n---\n')
        # Use the actual case and mechanical checker. The only replacement is
        # a zero-model semantic engine; every original criterion must run.
        mechanical, semantic = case['judges']
        checker = folder/'check-goal-char-limit.py'
        checker.write_bytes((source/'fixtures/scripts/check-goal-char-limit.py').read_bytes())
        checker.chmod(0o755)
        mechanical['script_path'] = str(checker)
        criteria = semantic['criteria']
        verdict = {'results': [{'criterion_id': f'criterion-{i+1}', 'passed': False,
                    'evidence': ['protocol only'], 'failures': ['controlled failure']}
                   for i in range(len(criteria))]}
        code = 'import json;print(json.dumps(' + repr({'final_message': json.dumps(verdict), 'exit_code': 0}) + '))'
        semantic['engine'] = {'name': 'protocol-semantic-judge', 'model': semantic['engine']['model'], 'custom': {
            'transport': 'local', 'response_format': 'session_result',
            'local': {'command': 'python3', 'args': ['-c', code]}}}
        (folder/'case.yaml').write_text(yaml.safe_dump(case, allow_unicode=True, sort_keys=False))
        response = '/goal migrate auth payments orders reports; entry .goal-task/auth-migration/state.md'
        payload = {'final_message': response, 'exit_code': 0}
        config = {'schema_version': 'v1alpha1', 'environment': {'type': 'none'},
            'engine': {'name': 'protocol-frozen-output', 'custom': {
                'transport': 'local', 'response_format': 'session_result',
                'local': {'command': 'python3', 'args': ['-c', 'import json;print(json.dumps(' + repr(payload) + '))']}}},
            'cases': {'files': ['case.yaml'], 'parallelism': 1},
            'benchmark': {'enabled': False}, 'report': {'formats': ['json']}}
        (folder/'eval.yaml').write_text(yaml.safe_dump(config))
        (folder/'empty-user.yaml').write_text('{}\n')
        result = subprocess.run([binary, '--config', str(folder/'empty-user.yaml'), 'run',
            str(folder/'eval.yaml'), '--output-dir', str(folder/'reports')], capture_output=True, text=True, timeout=90)
        (folder/'run.log').write_text(result.stdout + result.stderr)
        assert result.returncode == 1, result.stdout + result.stderr
        paths = list((folder/'reports').rglob('evaluation.json'))
        assert len(paths) == 1, paths
        evaluation = json.loads(paths[0].read_text())
        assert [m['status'] for m in evaluation['judge_results']] == ['PASS', 'FAIL'], evaluation
        assert evaluation['aggregation']['status'] == 'FAIL', evaluation
        grading = evaluation['judge_results'][1]['result']
        assert all(any(c == a['text'] and not a['passed'] and not a.get('skipped')
                       for a in grading['assertion_results']) for c in criteria), grading
    print('PASS: current three cases execute mechanical and semantic members; format PASS cannot mask semantic FAIL; models=0')


def real_judge_schema_smoke(binary, root):
    """Validate the real Judge adapter, which a custom mock can accidentally hide."""
    folder = root / 'real-judge-schema'
    folder.mkdir()
    (folder / 'SKILL.md').write_text('---\nname: real-judge-schema\ndescription: Configuration-only probe\n---\n')
    (folder / 'case.yaml').write_text('''id: real-judge-schema
title: Real Judge configuration only
input:
  prompt: Validate configuration without executing any model.
judge:
  type: agent_judge
  engine:
    name: codex
    version: 0.164.0
    model:
      provider: openai
      name: gpt-6-luna
  context:
    profile: minimal
    final_message: include
    transcript: omit
    workspace_diff: omit
    generated_files: omit
  criteria: ["The final response matches the requested outcome."]
''')
    (folder / 'eval.yaml').write_text('''schema_version: v1alpha1
environment:
  type: none
engine:
  name: codex
  version: 0.164.0
  model:
    provider: openai
    name: gpt-6-luna
cases:
  files: [case.yaml]
benchmark:
  enabled: false
''')
    empty = root / 'empty-user.yaml'
    config = folder / 'eval.yaml'
    commands = [('validate', str(config)), ('run', str(config), '--dry-run')]
    for args in commands:
        result = subprocess.run([binary, '--config', str(empty), *args], text=True, capture_output=True, timeout=30)
        (folder / (args[0] + '.log')).write_text(result.stdout + result.stderr)
        assert result.returncode == 0, result.stdout + result.stderr
        if args[0] == 'run':
            assert 'real-judge-schema' in result.stdout and 'shared-runtime' not in result.stdout, result.stdout
    # This was the actual failure: setting both fields passed mock-only testing.
    path = folder / 'case.yaml'
    path.write_text(path.read_text().replace('  type: agent_judge\n', '  type: agent_judge\n  model: gpt-6-luna\n'))
    # Exercise the complete dry-run path as well as the valid config validation;
    # neither command may start a model or mask the real Judge with a mock.
    result = subprocess.run([binary, '--config', str(empty), 'run', str(config), '--dry-run'], text=True, capture_output=True, timeout=30)
    (folder / 'mutually-exclusive-rejected.log').write_text(result.stdout + result.stderr)
    assert result.returncode != 0 and 'mutually exclusive' in result.stdout + result.stderr, result.stdout + result.stderr
    print('PASS: real Judge engine configuration validates; duplicate model setting rejected; zero model execution')


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
    real_judge_schema_smoke(binary, root)
    contract_judge_smoke(binary, root)


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
