#!/usr/bin/env python3
"""用原Docker镜像及空fresh runtime重放12份冻结输出；SDK custom+script，无模型。"""
from pathlib import Path
import argparse
import copy
import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import yaml

REPO = Path(__file__).resolve().parents[3]
FOUR = ('confirmation-brief', 'stage2-migration', 'preauthorized-permissions', 'compaction-checkpoint')
SCRIPTS = {'confirmation-brief': 'check-confirmation-brief.sh', 'stage2-migration': 'check-stage2-migration.sh',
           'preauthorized-permissions': 'check-preauthorized-permissions.sh', 'compaction-checkpoint': 'check-compaction-checkpoint.sh'}
V3 = REPO/'evals/skill-up/evidence/luna-paired/replay-v3'
MAIN = REPO/'evals/skill-up/evidence/luna-paired/with/run'
CONTROL = REPO/'evals/skill-up/evidence/luna-xhigh-control/run'
STAGE2 = REPO/'.eval-work/luna-failed-pairs-stage2-v1-20261030'


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def text_sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')


def child_env(phase):
    env = os.environ.copy()
    for name in ('SKILL_UP_WITHOUT_SKILL_ONLY', 'CODEX_THREAD_ID', 'CODEX_INTERNAL_ORIGINATOR_OVERRIDE'):
        env.pop(name, None)
    env['PATH'] = str(phase/'bin') + os.pathsep + env['PATH']
    env['LUNA_CONTROL_DIR'] = str(phase)
    return env


def cli(binary, phase, prepare=False):
    config = phase/'snapshot/evals/eval.yaml'
    commands = [(['validate', str(config)], 'validate.log'),
                (['run', str(config), '--dry-run'], 'dry-run.log')] if prepare else [
                (['run', str(config), '--output-dir', str(phase/'reports'),
                  '--event-log', str(phase/'events.jsonl')], 'run.log')]
    for args, filename in commands:
        require(not (phase/filename).exists(), '拒绝覆盖CLI证据')
        with (phase/filename).open('wb') as log:
            result = subprocess.run([str(binary), '--config', str(phase/'empty-user.yaml'), *args],
                                    env=child_env(phase), stdout=log, stderr=subprocess.STDOUT)
        require(result.returncode in ((0,) if prepare else (0, 1)), 'SDK基础设施调用失败')


def broker(root):
    isolation = load(root/'frozen/isolation-base.json')
    return subprocess.check_output([isolation['docker_binary'], 'logs', isolation['broker_container']])


def inputs():
    rows = []
    for group, root in (('with', MAIN), ('without', CONTROL)):
        native_path = root/'cases-combined.json'
        native = {r['case_id']: r for r in load(native_path)}
        calibrated = {r['case_id']: r for r in load(V3/(group+'-calibrated.json'))}
        for case in FOUR:
            raw = native[case]
            rows.append({'source_group': 'main-'+group, 'case_id': case, 'arm': group,
                         'source_native': str(native_path), 'source_native_sha256': sha(native_path),
                         'response': raw['response'], 'raw_status': raw['status'],
                         'raw_grading': raw['grading'], 'prior_current_status': calibrated[case]['calibrated_status']})
    manifest = load(STAGE2/'manifest.json')
    require(manifest.get('completed_utc'), 'stage2原8G尚未完成')
    quality = {r['trial_id']: r for r in load(STAGE2/'trial-results.json')}
    for row in manifest['order']:
        if row['case_id'] != 'preauthorized-permissions':
            continue
        root = STAGE2/'trials'/row['trial_id']
        native_path = next((root/'G/reports').glob('iteration-*/result.json'))
        raw = load(native_path)['case_results'][0]
        j_name = quality[row['trial_id']].get('judge_phase', 'J')
        j_native = next((root/j_name/'reports').glob('iteration-*/result.json'))
        j_raw = load(j_native)['case_results'][0]
        require(raw['response'] == j_raw['response'], 'stage2 G/J原文不符')
        rows.append({'source_group': 'stage2-preauth', **row,
                     'source_native': str(native_path), 'source_native_sha256': sha(native_path),
                     'response': raw['response'], 'raw_status': quality[row['trial_id']]['quality_status'],
                     'raw_grading': j_raw['grading'], 'source_quality_native': str(j_native),
                     'source_quality_native_sha256': sha(j_native), 'prior_current_status': j_raw['status']})
    require(len(rows) == 12, '必须原8份main加4份preauth')
    return rows


def prepare(root, allow_preauth_refresh=False):
    require(not root.exists(), '拒绝覆盖已有replay')
    for case in FOUR:
        definition = yaml.safe_load((REPO/'evals/skill-up/cases'/(case+'.yaml')).read_text())
        require('judges' not in definition and definition.get('judge', {}).get('type') == 'script',
                '当前案例已迁移语义多 Judge；本入口仅供历史协议，请从原冻结归档使用原runner重放。')
    rows = inputs()
    original = load(STAGE2/'manifest.json')
    binary = STAGE2/'dependencies/skill-up'
    require(sha(binary) == original['binary_sha256'], '原二进制SHA不符')
    wrapper = STAGE2/'dependencies/scripts/baseline-docker.py'
    require(sha(wrapper) == original['dependencies_sha256']['scripts/baseline-docker.py'], 'Docker wrapper不是原冻结版')
    isolation = load(STAGE2/'isolation-base.json')
    require(isolation['image_id'] == load(MAIN/'isolation.json')['image_id'], '原镜像不同')
    root.mkdir(parents=True)
    frozen = root/'frozen';frozen.mkdir()
    isolation['docker_binary'] = shutil.which('docker')
    dump(frozen/'isolation-base.json', isolation)
    shutil.copy2(wrapper, frozen/'baseline-docker.py')
    shutil.copy2(Path(__file__).resolve(), frozen/'run-script-replay-isolated.py')
    dump(root/'source-outputs.json', rows)
    source_refresh = {}
    for case in FOUR:
        directory = frozen/case;directory.mkdir()
        config = V3/'with'/case/'corrected-case.yaml'
        checker = V3/'with'/case/'corrected-checker.sh'
        live_checker = REPO/'evals/skill-up/fixtures/scripts'/SCRIPTS[case]
        if case == 'preauthorized-permissions' and allow_preauth_refresh:
            source_refresh[case] = {'previous_v3_sha256': sha(checker), 'new_sha256': sha(live_checker),
                                    'scope': 'explicitly authorized preauth synonym/evidence-confirmation correction'}
            checker = live_checker
        require(sha(checker) == sha(live_checker) and
                sha(config) == sha(REPO/'evals/skill-up/cases'/(case+'.yaml')), 'live判分源与已审查v3不同，需另行冻结授权')
        shutil.copy2(config, directory/'case.yaml');shutil.copy2(checker, directory/SCRIPTS[case])
    tests_source = REPO/'evals/skill-up/fixtures/scripts/test-judges.sh'
    tests_bytes = tests_source.read_bytes()
    tests = subprocess.run(['bash', str(tests_source)], capture_output=True)
    require(tests.returncode == 0 and tests_source.read_bytes() == tests_bytes, '确定性正反自测失败或测试源变化')
    (frozen/'judge-tests-source.sh').write_bytes(tests_bytes)
    (frozen/'judge-tests.log').write_bytes(tests.stdout+tests.stderr)
    sequence = []
    for i, row in enumerate(rows, 1):
        ident = f'script-replay-{i:02d}'
        phase = root/'phases'/ident
        (phase/'bin').mkdir(parents=True)
        shutil.copy2(frozen/'baseline-docker.py', phase/'bin/docker');(phase/'bin/docker').chmod(0o755)
        (phase/'empty-user.yaml').write_text('{}\n')
        spec = copy.deepcopy(isolation)
        for key in ('target_skill', 'skill_bundle_sha256', 'skill_runtime_sha256', 'with_skill_method'):
            spec.pop(key, None)
        dump(phase/'isolation.json', spec)
        case = yaml.safe_load((frozen/row['case_id']/'case.yaml').read_text())
        case['id'] = ident
        script_path = phase/'snapshot'/case['judge']['script_path']
        script_path.parent.mkdir(parents=True)
        shutil.copy2(frozen/row['case_id']/SCRIPTS[row['case_id']], script_path)
        # Only candidate final is replayed. There is no Codex runner/Judge engine.
        code = ("from pathlib import Path;import json;"
                "assert not list(Path('/workspace').rglob('SKILL.md'));"
                "assert not list(Path('/root/.codex/skills').rglob('SKILL.md'));"
                "print(json.dumps({'final_message':"+repr(row['response'])+",'exit_code':0}))")
        config = {'schema_version': 'v1alpha1', 'environment': {'type': 'docker', 'image': spec['image_id']},
                  'skills': [], 'engine': {'name': 'frozen-script-replay', 'custom': {'transport': 'local',
                  'response_format': 'session_result', 'local': {'command': 'python3', 'args': ['-c', code]}}},
                  'cases': {'files': ['evals/case.yaml'], 'parallelism': 1,
                            'defaults': original['defaults'], 'retry_policy': original['retry']},
                  'benchmark': {'enabled': False}, 'report': {'formats': ['json'], 'artifacts': ['transcript']}}
        (phase/'snapshot/evals').mkdir(parents=True)
        (phase/'snapshot/evals/eval.yaml').write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False))
        (phase/'snapshot/evals/case.yaml').write_text(yaml.safe_dump(case, allow_unicode=True, sort_keys=False))
        (phase/'response.txt').write_bytes(row['response'].encode())
        sequence.append({'id': ident, 'source_index': i-1, 'source_group': row['source_group'],
                         'case_id': row['case_id'], 'arm': row['arm'], 'response_sha256': text_sha(row['response'])})
        cli(binary, phase, prepare=True)
    deps = {str(p.relative_to(root)): sha(p) for p in root.rglob('*') if p.is_file()}
    dump(root/'manifest.json', {'created_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
         'mode': 'native_docker_sdk_custom_final_script_only', 'prepared': True,
         'models_called': 0, 'student_generations_rerun': 0, 'image_id': isolation['image_id'],
         'binary_path': str(binary), 'binary_sha256': sha(binary), 'sequence': sequence,
         'frozen_dependencies_sha256': deps, 'score_authority': 'native Linux script, existing exact final',
         'host_auth_mounted': False, 'prior_grades_modified': False,
         'authorized_source_refresh': source_refresh, 'deterministic_tests_exit_code': tests.returncode})
    print(json.dumps({'prepared': str(root), 'cases': len(sequence), 'models_called': 0}, ensure_ascii=False))


def dispatch(root):
    manifest = load(root/'manifest.json')
    require(manifest['prepared'] and not manifest.get('started_utc'), '尚未准备或已启动，禁止重复派发')
    for relative, expected in manifest['frozen_dependencies_sha256'].items():
        require(sha(root/relative) == expected, '冻结依赖改变: '+relative)
    binary = Path(manifest['binary_path'])
    require(sha(binary) == manifest['binary_sha256'], '二进制发生变化')
    rows = load(root/'source-outputs.json')
    before = broker(root)
    manifest['started_utc'] = dt.datetime.now(dt.timezone.utc).isoformat()
    manifest['broker_before_sha256'] = hashlib.sha256(before).hexdigest()
    dump(root/'manifest.json', manifest)
    results, seen = [], set()
    for planned in manifest['sequence']:
        phase = root/'phases'/planned['id'];source = rows[planned['source_index']]
        require(sha(Path(source['source_native'])) == source['source_native_sha256'], '原native结果被修改')
        cli(binary, phase)
        files = list((phase/'reports').glob('iteration-*/result.json'))
        require(len(files) == 1, '原生replay结果不唯一')
        result = load(files[0])['case_results'][0]
        require(result['response'] == source['response'] and result['status'] in ('PASS', 'FAIL'), '原文改变或环境错误')
        require(not list(phase.rglob('rollout-*.jsonl')) and not (phase/'skill-install-audits').exists(), '重放意外调用模型或安装Skill')
        require(all(result.get(k, 0) == 0 for k in ('input_tokens', 'output_tokens', 'judge_input_tokens', 'judge_output_tokens')),
                '出现模型token记录')
        ids = load(phase/'containers.json')
        require(ids and not (set(ids) & seen) and len(ids) == len(set(ids)), '容器重用')
        seen.update(ids)
        audits = {p.stem: load(p) for p in (phase/'container-audits').glob('*.json')}
        require(set(audits) == set(ids), '容器创建审计不闭环')
        for audit in audits.values():
            require(audit['image'] == manifest['image_id'] and audit['readonly'] and audit['bind_mounts'] == [] and
                    audit['catalog_empty'] and audit['host_paths_hidden'] and audit['network_locked'] and
                    audit['cap_drop'] == ['ALL'] and 'no-new-privileges' in audit['security_opt'], '隔离审计不符')
        results.append({**planned, 'original_native_status': source['raw_status'],
                        'prior_current_status': source['prior_current_status'], 'native_linux_status': result['status'],
                        'native_result_path': str(files[0].relative_to(root)), 'native_result_sha256': sha(files[0]),
                        'native_grading': result['grading'], 'container_ids': ids,
                        'models_called': 0, 'student_generations_rerun': 0})
        dump(root/'results.json', results)
    after = broker(root)
    require(after.startswith(before), 'broker日志被重置')
    delta = after[len(before):]
    events = [json.loads(line) for line in delta.decode(errors='replace').splitlines() if line.strip()]
    accepted = sum(e.get('event') == 'accepted' for e in events)
    require(accepted == 0, 'broker出现模型请求；不得标为零模型有效重放')
    for relative, expected in manifest['frozen_dependencies_sha256'].items():
        require(sha(root/relative) == expected, '运行中冻结依赖改变: '+relative)
    dump(root/'broker-zero-delta.json', {'accepted_delta': accepted, 'events': events,
         'before_sha256': hashlib.sha256(before).hexdigest(), 'after_sha256': hashlib.sha256(after).hexdigest(),
         'models_called': 0, 'valid': True})
    manifest.update(completed_utc=dt.datetime.now(dt.timezone.utc).isoformat(), results=len(results),
                    valid=True, unique_container_count=len(seen), broker_accepted_delta=accepted)
    dump(root/'manifest.json', manifest)
    print(json.dumps({'completed': str(root), 'cases': len(results), 'broker_accepted_delta': accepted,
                      'native_linux_results': [(r['id'], r['native_linux_status']) for r in results]}, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--allow-preauth-source-refresh', action='store_true')
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--prepare-only', action='store_true');mode.add_argument('--dispatch', action='store_true')
    args = parser.parse_args();root = args.root.resolve()
    prepare(root, args.allow_preauth_source_refresh) if args.prepare_only else dispatch(root)


if __name__ == '__main__':
    main()
