#!/usr/bin/env python3
"""离线重放四项确定性 Judge；保留原生判分，只添加独立校准字段。需 PyYAML。"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

import yaml

REPO = Path(__file__).resolve().parents[3]
AFFECTED = {
    'confirmation-brief': 'check-confirmation-brief.sh',
    'stage2-migration': 'check-stage2-migration.sh',
    'preauthorized-permissions': 'check-preauthorized-permissions.sh',
    'compaction-checkpoint': 'check-compaction-checkpoint.sh',
}
STATUSES = ('PASS', 'FAIL', 'ERROR', 'SKIP')


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha_bytes(value):
    return hashlib.sha256(value).hexdigest()


def sha(path):
    return sha_bytes(path.read_bytes())


def load(path):
    return json.loads(path.read_text())


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def counts(rows, field='status'):
    values = Counter(row[field] for row in rows)
    return {status: values[status] for status in STATUSES}


def destination(out, sources):
    require(not out.exists(), '拒绝覆盖已有校准归档')
    for source in sources:
        require(not out.is_relative_to(source) and not source.is_relative_to(out),
                '输出不得覆盖原模型证据、旧replay或源码')


def read_group(root, configuration):
    manifest = load(root / 'manifest.json')
    require(manifest.get('completed_utc') and manifest.get('all_isolation_audits_pass'),
            '只允许已完成且通过隔离审计的原批次')
    require(manifest['model'] == manifest['judge_model'] == 'gpt-6-luna' and
            manifest['effort'] == manifest['judge_effort'] == 'xhigh', '原模型或effort不符')
    rows = load(root / 'cases-combined.json')
    native, locations = [], {}
    for batch, count in (('pilot', 1), ('remaining', 29)):
        result = root / batch / 'iteration-1/result.json'
        cases = load(result)['case_results']
        require(len(cases) == count, '原批次案例数不符')
        native.extend(cases)
        for row in cases:
            locations[row['case_id']] = (result, result.parent / row['case_id'] / configuration)
    require(rows == native, 'combined必须与原生case_results逐字段一致')
    require(len(rows) == len({r['case_id'] for r in rows}) == 30, '必须是原30唯一案例')
    require([r['case_id'] for r in rows] == manifest['case_ids'], '原案例顺序不符')
    require(all(r['configuration'] == configuration and r['status'] in STATUSES for r in rows),
            '原生结果组或状态非法')
    return rows, locations, manifest


def prior_statuses(prior, native):
    calibrated = load(prior / 'without-calibrated.json')
    require(load(prior / 'summary.json')['models_rerun'] == 0, '旧校准不得含新模型运行')
    require(len(calibrated) == 30 and [r['case_id'] for r in calibrated] == [r['case_id'] for r in native],
            '旧校准案例集合不符')
    statuses = {}
    for raw, old in zip(native, calibrated):
        require(old['response'] == raw['response'] and old['prompt'] == raw['prompt'] and
                old['original_status'] == raw['status'], '旧校准输入/输出或原状态变动')
        if raw['case_id'] == 'confirmation-brief':
            require(raw['status'] == 'FAIL' and old['status'] == 'PASS' and
                    old['original_grading'] == raw['grading'], '旧确认门校准来源不符')
        else:
            stripped = {k: v for k, v in old.items() if k not in
                        ('original_status', 'original_grading', 'verdict_provenance')}
            require(stripped == raw, '旧校准改动了非目标案例')
        statuses[raw['case_id']] = old['status']
    confirmation = load(prior / 'confirmation-brief.json')
    raw = next(r for r in native if r['case_id'] == 'confirmation-brief')
    require(confirmation['original_response_sha256'] == sha_bytes(raw['response'].encode()) and
            confirmation['corrected_replay']['exit_code'] == 0 and confirmation['model_calls'] == 0,
            '旧确认门校准响应或判分证据不符')
    return statuses


def observed_exit(raw, original_case):
    expected = original_case.get('expect', {}).get('exit_code')
    assertions = [a for a in raw['grading']['assertion_results'] if a['text'] == 'expect.exit_code']
    require(isinstance(expected, int) and len(assertions) == 1 and
            assertions[0]['passed'] and not assertions[0].get('skipped'),
            '缺少可信的原生exit_code断言，不能推定真实退出值')
    return expected, {'method': 'inferred_from_frozen_passing_native_exit_code_assertion',
                      'native_assertion': assertions[0], 'original_expected_exit_code': expected,
                      'note': '复用原生执行证据；离线重判没有再次执行student，也不声称新测得退出码。'}


def expect_checks(config, response, exit_code):
    expect = config.get('expect', {})
    require(not (set(expect) - {'must_contain', 'exit_code'}), '不支持的expect规则，拒绝静默略过')
    checks = []
    if expect.get('must_contain'):
        require(all(isinstance(s, str) for s in expect['must_contain']), 'must_contain必须是字符串')
        missing = [s for s in expect['must_contain'] if s not in response]
        checks.append({'rule': 'must_contain', 'passed': not missing, 'missing': missing,
                       'expected': expect['must_contain']})
    if 'exit_code' in expect:
        checks.append({'rule': 'exit_code', 'passed': expect['exit_code'] == exit_code,
                       'expected': expect['exit_code'], 'observed_from_native': exit_code})
    return {'passed': all(c['passed'] for c in checks), 'checks': checks}


def run_checker(script, response, timeout):
    # Only the known frozen local scripts execute. Do not inherit auth/provider env.
    env = {'PATH': os.environ.get('PATH', os.defpath), 'LC_ALL': 'C.UTF-8',
           'EVAL_FINAL_MESSAGE': response}
    try:
        result = subprocess.run(['bash', str(script)], env=env, text=True,
                                capture_output=True, timeout=timeout)
        return {'exit_code': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr,
                'execution_error': None}
    except (subprocess.TimeoutExpired, OSError) as exc:
        return {'exit_code': None, 'stdout': '', 'stderr': '',
                'execution_error': type(exc).__name__ + ': ' + str(exc)}


def evaluate(config, script, response, exit_code):
    require(config['judge']['type'] == 'script', '禁止调用非确定性Judge')
    gates = expect_checks(config, response, exit_code)
    execution = run_checker(script, response, config['judge'].get('timeout_seconds', 30))
    # Run the checker even when the gate fails, but label that execution diagnostic.
    # Native-equivalent verdict still obeys expect -> judge short-circuit order.
    status = ('FAIL' if not gates['passed'] else 'ERROR' if execution['execution_error'] else
              'PASS' if execution['exit_code'] == 0 else 'FAIL')
    return {'status': status, 'expect': gates, 'checker': execution,
            'checker_counts_toward_verdict': gates['passed'],
            'checker_diagnostic_only': not gates['passed'], 'model_calls': 0}


def calibrated_row(raw, status, provenance, prior):
    row = deepcopy(raw)
    row.update(calibrated_status=status, calibration_provenance=provenance,
               prior_calibrated_status=prior)
    require(row['status'] == raw['status'] and row['grading'] == raw['grading'],
            '不得改写原生status/grading')
    return row


def self_test():
    old = {'expect': {'must_contain': ['/goal', 'Progress'], 'exit_code': 0}}
    new = {'expect': {'must_contain': ['/goal'], 'exit_code': 0}}
    require(not expect_checks(old, '/goal 进度 0%', 0)['passed'], '字面缺失应失败')
    require(expect_checks(new, '/goal 进度 0%', 0)['passed'], '修正gate应通过')
    require(not expect_checks(new, '/goal', 1)['passed'], '退出失败不得通过')
    raw = {'status': 'FAIL', 'grading': {'status': 'FAIL'}}
    row = calibrated_row(raw, 'PASS', {'kind': 'test'}, 'FAIL')
    require(raw == {'status': 'FAIL', 'grading': {'status': 'FAIL'}} and row['status'] == 'FAIL',
            '校准必须保留原生判分')
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        checker = root / 'checker.sh'
        checker.write_text('exit 0\n')
        config = {'judge': {'type': 'script', 'timeout_seconds': 1}, **new}
        require(evaluate(config, checker, '/goal', 0)['status'] == 'PASS', '脚本成功测试失败')
        checker.write_text('exit 1\n')
        require(evaluate(config, checker, '/goal', 0)['status'] == 'FAIL', '脚本失败不得通过')
        checker.write_text('sleep 2\n')
        require(evaluate(config, checker, '/goal', 0)['status'] == 'ERROR', '超时不得通过')
        require(evaluate(config, root/'missing', '/goal', 0)['status'] != 'PASS', '缺脚本不得通过')
        try:
            destination(root, [])
        except RuntimeError:
            pass
        else:
            raise RuntimeError('已有目录必须拒绝覆盖')
        text = '原文无末尾换行'
        (root/'response.txt').write_bytes(text.encode())
        require((root/'response.txt').read_bytes() == text.encode(), '原文必须逐字节保留')
    print('PASS offline replay: gates, raw-grade preservation, script fail/error, overwrite refusal, exact response bytes; models=0')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--with-run', type=Path, default=REPO/'evals/skill-up/evidence/luna-paired/with/run')
    parser.add_argument('--without-run', type=Path, default=REPO/'evals/skill-up/evidence/luna-xhigh-control/run')
    parser.add_argument('--prior-replay', type=Path, default=REPO/'evals/skill-up/evidence/luna-paired/replay')
    parser.add_argument('--current-evals', type=Path, default=REPO/'evals/skill-up')
    parser.add_argument('--output', type=Path, default=REPO/'evals/skill-up/evidence/luna-paired/replay-v3')
    parser.add_argument('--supersedes', type=Path, default=REPO/'evals/skill-up/evidence/luna-paired/replay-v2')
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    roots = {'with': args.with_run.resolve(), 'without': args.without_run.resolve()}
    prior, current, out = args.prior_replay.resolve(), args.current_evals.resolve(), args.output.resolve()
    supersedes = args.supersedes.resolve()
    require((supersedes/'summary.json').is_file(), '缺少上一版校准，禁止无来源替换')
    destination(out, [*roots.values(), prior, supersedes, current/'cases', current/'fixtures'])
    data = {group: read_group(root, group + '_skill') for group, root in roots.items()}
    require(data['with'][2]['case_ids'] == data['without'][2]['case_ids'], '配对案例集合必须相同')
    previous = prior_statuses(prior, data['without'][0])
    snapshots = {}
    for group, (rows, locations, manifest) in data.items():
        root = roots[group]
        snapshots[group] = {'manifest_sha256': sha(root/'manifest.json'),
                            'cases_combined_sha256': sha(root/'cases-combined.json')}
        for case, script in AFFECTED.items():
            for relative in (f'skill-up/cases/{case}.yaml', f'skill-up/fixtures/scripts/{script}'):
                require(sha(root/'snapshot'/relative) == manifest['snapshot_sha256'][relative],
                        '原冻结源码指纹不符: ' + relative)
    initial_hashes = {str(path): sha(path) for root in roots.values() for path in
                      (root/'manifest.json', root/'cases-combined.json',
                       root/'pilot/iteration-1/result.json', root/'remaining/iteration-1/result.json')}
    initial_hashes.update({str(path): sha(path) for path in prior.rglob('*') if path.is_file()})
    initial_hashes.update({str(path): sha(path) for path in supersedes.rglob('*') if path.is_file()})
    # Freeze one corrected source set before either group is evaluated. Copying
    # live worktree bytes separately for each group would permit version drift.
    current_sources = {}
    for case, script in AFFECTED.items():
        for relative in (f'cases/{case}.yaml', f'fixtures/scripts/{script}'):
            current_sources[relative] = (current/relative).read_bytes()
    test_path = current/'fixtures/scripts/test-judges.sh'
    test_source = test_path.read_bytes()
    out.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.' + out.name + '-', dir=out.parent))
    try:
        all_rows, replay_records = {}, []
        for group, (rows, locations, manifest) in data.items():
            root, calibrated = roots[group], []
            for raw in rows:
                case = raw['case_id']
                baseline = previous[case] if group == 'without' else raw['status']
                provenance = {'kind': 'unchanged_native', 'model_calls': 0}
                status = baseline
                if case in AFFECTED:
                    require(raw['status'] in ('PASS', 'FAIL'), 'ERROR/SKIP不得通过重判变PASS')
                    folder = stage/group/case
                    folder.mkdir(parents=True)
                    response = raw['response']
                    require(isinstance(response, str) and response.strip(), '原生响应缺失')
                    (folder/'response.txt').write_bytes(response.encode())
                    batch, case_root = locations[case]
                    dump(folder/'original-native-case.json', raw)
                    shutil.copy2(case_root/'grading.json', folder/'original-grading.json')
                    configs, scripts = {}, {}
                    for version, source in (('original', root/'snapshot/skill-up'), ('corrected', current)):
                        config_path = source/'cases'/f'{case}.yaml'
                        script_path = source/'fixtures/scripts'/AFFECTED[case]
                        for path, filename in ((config_path, version+'-case.yaml'),
                                               (script_path, version+'-checker.sh')):
                            payload = (current_sources[str(path.relative_to(current))]
                                       if version == 'corrected' else path.read_bytes())
                            (folder/filename).write_bytes(payload)
                        configs[version] = yaml.safe_load((folder/(version+'-case.yaml')).read_text())
                        scripts[version] = folder/(version+'-checker.sh')
                    require(configs['original']['input'] == configs['corrected']['input'] and
                            configs['original']['id'] == configs['corrected']['id'] == case,
                            '校准不得改输入或案例身份')
                    require(all(config['judge']['script_path'] == 'skill-up/fixtures/scripts/' + AFFECTED[case]
                                for config in configs.values()), 'Judge路径与重放脚本不一致')
                    exit_code, exit_source = observed_exit(raw, configs['original'])
                    results = {version: evaluate(configs[version], scripts[version], response, exit_code)
                               for version in ('original', 'corrected')}
                    require(results['original']['status'] == raw['status'],
                            '原判分无法复现，拒绝自动校准: ' + group + '/' + case)
                    require(results['original']['expect']['passed'] == raw['gates']['passed'],
                            '原expect无法复现: ' + group + '/' + case)
                    status = results['corrected']['status']
                    record = {'case_id': case, 'group': group, 'model_calls': 0,
                              'raw_status': raw['status'], 'prior_calibrated_status': baseline,
                              'calibrated_status': status, 'response_sha256': sha_bytes(response.encode()),
                              'native_batch_result_path': str(batch.relative_to(REPO)),
                              'native_batch_result_sha256': sha(batch), 'exit_code_provenance': exit_source,
                              'source_hashes': {name: sha(folder/name) for name in
                                               ('original-case.yaml', 'original-checker.sh',
                                                'corrected-case.yaml', 'corrected-checker.sh',
                                                'original-native-case.json', 'original-grading.json')},
                              'results': results}
                    dump(folder/'replay.json', record)
                    replay_records.append(record)
                    provenance = {'kind': 'offline_script_and_expect_replay', 'model_calls': 0,
                                  'record': f'{group}/{case}/replay.json',
                                  'response_sha256': record['response_sha256'],
                                  'prior_confirmation_replay_preserved': group == 'without' and case == 'confirmation-brief'}
                calibrated.append(calibrated_row(raw, status, provenance, baseline))
            all_rows[group] = calibrated
            dump(stage/(group+'-calibrated.json'), calibrated)
        for path, expected in initial_hashes.items():
            require(sha(Path(path)) == expected, '原生证据或旧replay被修改: ' + path)
        tests = subprocess.run(['bash', str(test_path)], text=True, capture_output=True,
                               env={'PATH': os.environ.get('PATH', os.defpath), 'LC_ALL': 'C.UTF-8'},
                               timeout=120)
        require(tests.returncode == 0, '判分正反自测失败，拒绝归档')
        (stage/'judge-tests.log').write_text(tests.stdout + tests.stderr)
        (stage/'judge-tests-source.sh').write_bytes(test_source)
        require(test_path.read_bytes() == test_source, '判分测试源发生变化')
        for relative, payload in current_sources.items():
            require((current/relative).read_bytes() == payload, '当前判分源中途变化: ' + relative)
        paired = [{'case_id': a['case_id'], 'without_raw': b['status'], 'with_raw': a['status'],
                   'without_calibrated': b['calibrated_status'], 'with_calibrated': a['calibrated_status']}
                  for a, b in zip(all_rows['with'], all_rows['without'])]
        matrix = Counter(r['without_calibrated'] + '→' + r['with_calibrated'] for r in paired)
        summary = {'mode': 'offline_existing_native_output_replay', 'models_rerun': 0,
                   'created_utc': datetime.now(timezone.utc).isoformat(), 'affected_case_ids': list(AFFECTED),
                   'prior_replay_summary_sha256': sha(prior/'summary.json'), 'source_runs': snapshots,
                   'supersedes_calibration': {'path': str(supersedes.relative_to(REPO)),
                                              'summary_sha256': sha(supersedes/'summary.json'),
                                              'prior_archive_unchanged': True},
                   'frozen_corrected_sources_sha256': {name: sha_bytes(payload)
                                                        for name, payload in current_sources.items()},
                   'judge_tests': {'exit_code': tests.returncode,
                                   'source_sha256': sha_bytes(test_source),
                                   'log_sha256': sha(stage/'judge-tests.log')},
                   'raw_counts': {group: counts(rows) for group, rows in all_rows.items()},
                   'calibrated_counts': {group: counts(rows, 'calibrated_status') for group, rows in all_rows.items()},
                   'prior_calibrated_counts': {group: counts(rows, 'prior_calibrated_status') for group, rows in all_rows.items()},
                   'changed_from_raw': {group: [r['case_id'] for r in rows if r['status'] != r['calibrated_status']]
                                        for group, rows in all_rows.items()},
                   'changed_from_prior_calibration': {group: [r['case_id'] for r in rows if r['prior_calibrated_status'] != r['calibrated_status']]
                                                     for group, rows in all_rows.items()},
                   'paired_matrix_without_to_with': dict(matrix), 'paired_cases': paired,
                   'remaining_nonpass': {group: [r['case_id'] for r in rows if r['calibrated_status'] != 'PASS']
                                         for group, rows in all_rows.items()},
                   'raw_native_status_and_grading_unchanged': True,
                   'nonaffected_cases_rejudged': 0,
                   'replayer_sha256': sha(Path(__file__).resolve())}
        dump(stage/'summary.json', summary)
        shutil.copy2(Path(__file__).resolve(), stage/'replay-paired-judges.py')
        lines = ['# Luna配对结果的确定性判分校准', '',
                 '只重放四项既有输出，模型运行0；原生status/grading均保留，校准结果单列。', '',
                 '|组|原始PASS/FAIL/ERROR|本次校准PASS/FAIL/ERROR|', '|---|---|---|']
        for group in ('without', 'with'):
            raw, corrected = summary['raw_counts'][group], summary['calibrated_counts'][group]
            lines.append(f"|{group}|{raw['PASS']}/{raw['FAIL']}/{raw['ERROR']}|{corrected['PASS']}/{corrected['FAIL']}/{corrected['ERROR']}|")
        lines += ['', '配对矩阵方向为without→with：' + '，'.join(f'{k}: {v}' for k, v in sorted(matrix.items())) + '。', '',
                  'without沿用已提交第一次校准后的7PASS基线；本次重放没有新增without状态变化。',
                  'preauthorized-permissions的跨枚举误报已消除，但缺少授权不覆盖上级/安全边界的契约，仍FAIL。',
                  '四项以外26例/组沿用原判分，没有再次调用语义Judge。', '',
                  '此前replay-v2完整保留；本版新增migration局部否定语义检查，并以同一组冻结新判分源重放两组。', '',
                  '所有response.txt来自原生case_results.response逐字节UTF-8编码，不补换行。exit_code复用已通过的原生expect断言并明确记录推定来源。',
                  '旧gate失败时仍诊断性执行checker，但完整校准结果遵守expect短路，不把checker通过覆盖gate失败。', '',
                  'with剩余失败：' + '、'.join(summary['remaining_nonpass']['with']) + '。',
                  'without剩余失败：' + '、'.join(summary['remaining_nonpass']['without']) + '。', '',
                  'with30语义Judge可读取candidate trace中的Skill文本，因此本次只报告原生评分与确定性校准，不宣称with/without原30为完全盲评。']
        (stage/'summary.md').write_text('\n'.join(lines)+'\n')
        require(not out.exists(), '写入前发现归档已存在，拒绝覆盖')
        stage.rename(out)
        print(json.dumps({'output': str(out), 'raw_counts': summary['raw_counts'],
                          'calibrated_counts': summary['calibrated_counts'], 'models_rerun': 0}, ensure_ascii=False))
    finally:
        if stage.exists():
            shutil.rmtree(stage)


if __name__ == '__main__':
    main()
