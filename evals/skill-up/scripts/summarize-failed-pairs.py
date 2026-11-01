#!/usr/bin/env python3
"""只离线归档已完成的小规模Skill版本对照；不调用模型，不覆盖归档。需PyYAML。"""
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime, timezone
import argparse
import hashlib
import json
import re
import shutil
import tempfile
import yaml

REPO = Path(__file__).resolve().parents[3]
MODEL = 'gpt-6-luna'
VERSION = '0.164.0'
MAIN_RUN = REPO / 'evals/skill-up/evidence/luna-paired/with/run'
STATUSES = ('PASS', 'FAIL', 'ERROR', 'SKIP')
MINIMAL = {'profile': 'minimal', 'final_message': 'include', 'transcript': 'omit',
           'workspace_diff': 'omit', 'generated_files': 'omit'}
ENV_CASES = {'research-goal', 'no-fabrication'}
ENV_FACTS = {'observation_phase': 'initial_task_environment', 'provided_project_material_files': 0,
             'provided_repository_source_files': 0, 'provided_test_material_files': 0,
             'project_test_commands_verified': False, 'business_implementation_behavior_verified': False}
ENV_HEADER = '初始环境事实数据（非VCS diff，非业务实现调查结果）。\n'


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
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def safe(root, relative):
    path = (root / relative).resolve()
    require(path.is_relative_to(root) and not (root / relative).is_symlink(), '源路径越界或符号链接')
    return path


def completed(manifest):
    require(manifest.get('completed_utc') and manifest.get('cases_finished_utc') and
            manifest.get('request_outcome_coverage_valid') is True,
            '批次未完成或outcomes未通过，拒绝归档')
    require(manifest['experiment_kind'] == 'prospective_failed_version_pairs' and
            manifest['models_started'] is True, 'mock/prepare不能归档为真实质量')
    require(manifest['model'] == manifest['judge_model'] == MODEL and
            manifest['effort'] == manifest['judge_effort'] == 'xhigh', '模型/effort不符')


def validate_order(manifest, rows):
    order = manifest['order']
    require(len(order) == len(rows) == manifest['trial_count'] == manifest['student_executions_planned'],
            'trial数不完整')
    require(len({r['trial_id'] for r in order}) == len(order), 'trial ID重复')
    require([r['order'] for r in order] == list(range(1, len(order) + 1)), 'trial顺序不完整')
    for planned, observed in zip(order, rows):
        require(all(observed.get(k) == v for k, v in planned.items()), '结果不等于冻结顺序/实验臂')
    require(set(r['case_id'] for r in order) == set(manifest['case_ids']), 'case集合不符')
    require(set(r['arm'] for r in order) == set(manifest['arms']), '实验臂集合不符')
    cells = Counter((r['case_id'], r['arm']) for r in order)
    require(len(set(cells.values())) == 1 and next(iter(cells.values())) >= 2, '两臂重复数不平衡')
    require(set(cells) == {(c, a) for c in manifest['case_ids'] for a in manifest['arms']}, '缺少case/arm组合')
    for case, arm in cells:
        reps = [r['repetition'] for r in order if r['case_id'] == case and r['arm'] == arm]
        require(sorted(reps) == list(range(1, len(reps) + 1)), '重复序号不完整')


def native_phase(phase, trial):
    paths = list((phase / 'reports').glob('iteration-*/result.json'))
    require(len(paths) == 1, '阶段必须恰好一个原生result')
    result = load(paths[0])
    require(len(result['case_results']) == 1 and result['case_results'][0]['case_id'] == trial,
            '阶段原生结果身份不符')
    case = result['case_results'][0]
    require(case['configuration'] == 'with_skill' and case['status'] in STATUSES, '原生组或状态非法')
    grade = paths[0].parent / trial / 'with_skill/grading.json'
    require(grade.is_file(), '缺少原生grading文件')
    return case, result, paths[0], grade


def container_ids(phase, image, seen):
    ids = load(phase / 'containers.json')
    require(ids and len(ids) == len(set(ids)), '阶段容器记录重复/缺失')
    require(not (set(ids) & seen), 'G/J或不同trial复用了容器')
    seen.update(ids)
    audits = {p.stem: load(p) for p in (phase / 'container-audits').glob('*.json')}
    require(set(audits) == set(ids), '创建审计与容器ID不闭合')
    isolation = load(phase / 'isolation.json')
    args = isolation['create_extra_args']
    expected_tmpfs = dict(args[i + 1].split(':', 1) for i, flag in enumerate(args) if flag == '--tmpfs')
    for row in audits.values():
        require(row['image'] == image and row['readonly'] and row['cap_drop'] == ['ALL'] and
                'no-new-privileges' in row['security_opt'] and row['bind_mounts'] == [] and
                row['networks'] == [isolation['network']] and row['tmpfs'] == expected_tmpfs and
                row['catalog_empty'] and row['host_paths_hidden'] and row['network_locked'] and
                row['model_called_by_preflight'] is False, '容器隔离审计失败')
    return ids


def engine(config):
    require(config['name'] == 'codex' and config['version'] == VERSION and
            config['model'] == {'provider': 'openai', 'name': MODEL}, '引擎配置不符')


def config_phase(phase, manifest):
    config = yaml.safe_load((phase / 'snapshot/evals/eval.yaml').read_text())
    case = yaml.safe_load((phase / 'snapshot/evals/case.yaml').read_text())
    require(config['environment'] == {'type': 'docker', 'image': manifest['image_id']} and
            config['cases']['parallelism'] == 1 and config['cases']['defaults'] == manifest['defaults'] and
            config['cases']['retry_policy'] == manifest['retry'] and config['benchmark']['enabled'] is False,
            '阶段镜像/default/retry/并行配置不符')
    return config, case


def initial_environment(root, manifest, main_manifest):
    if not (set(manifest['case_ids']) & ENV_CASES):
        return None
    env = root / 'dependencies/environment'
    evidence = load(env / 'environment-evidence.json')
    require(sha(env / 'environment-evidence.json') == manifest['initial_environment']['evidence_sha256'] and
            evidence['valid'] and evidence['evidence_kind'] == 'actual_initial_docker_probe' and
            evidence['model_requests_generated'] == 0 and evidence['observations'] == {'initial_entries': []},
            '初始环境不是实际零模型空项目probe')
    require(evidence['image_id'] == manifest['image_id'] and
            evidence['isolation_sha256'] == main_manifest['isolation_original_sha256'], 'probe环境不是同一镜像/策略')
    require(load(env / 'initial-environment.json') == ENV_FACTS and
            sha(env / 'initial-environment.json') == evidence['facts_sha256'] == manifest['initial_environment']['facts_sha256'],
            '共同事实内容或SHA不符')
    for name, key in (('probe-source.py', 'source_sha256'), ('project-probe.stdout', 'probe_stdout_sha256'),
                      ('container-policy.json', 'container_policy_sha256'), ('broker-events.jsonl', 'broker_events_delta_sha256')):
        require(sha(env / name) == evidence[key], '环境probe证据SHA不符')
    require(load(env / 'project-probe.stdout') == {'initial_entries': []} and
            not any(e.get('event') == 'accepted' for e in map(json.loads, (env / 'broker-events.jsonl').read_text().splitlines())),
            '初始事实与原始观测/API窗口不符')
    policy = load(env / 'container-policy.json')
    require(policy['readonly'] and policy['bind_mounts'] == [] and policy['cap_drop'] == ['ALL'] and
            policy['image_id'] == manifest['image_id'], 'probe物理隔离不符')
    return {'facts': ENV_FACTS, 'facts_sha256': evidence['facts_sha256'],
            'evidence_sha256': sha(env / 'environment-evidence.json'),
            'scope': 'initial supplied business material only; not completed implementation/cache investigation'}


def process_evidence(g, case_id, candidate):
    path = g / 'student-process-audit.json'; audit = load(path)
    require(audit['case_id'] == case_id and audit['readonly_verified'] is False and
            audit['business_investigation_completed'] is False and
            audit['review_status'] == 'requires_independent_command_and_write_review', '过程审计错误宣称已只读/完成业务调查')
    commands = []; changes = []; calls = []
    for source in audit['source_rollouts']:
        rollout = safe(g, source['path']); require(sha(rollout) == source['sha256'], '过程原始trace变化')
        for number, line in enumerate(rollout.read_text().splitlines(), 1):
            event = json.loads(line); payload = event.get('payload', {}); item = payload.get('item', {})
            if event.get('type') == 'response_item' and payload.get('type') in ('function_call', 'custom_tool_call'):
                calls.append({'tool': payload.get('name'), 'call_id': payload.get('call_id'),
                              'arguments': payload.get('arguments', payload.get('input', ''))})
            if event.get('type') != 'event_msg' or item.get('type') not in ('CommandExecution', 'FileChange'):
                continue
            location = {'rollout': source['path'], 'line': number, 'ordinal': event.get('ordinal')}
            hashes = {k: text_sha(item[k]) for k in ('aggregated_output', 'stdout', 'stderr') if isinstance(item.get(k), str)}
            common = {**location, 'event_type': payload.get('type'), 'item_id': item.get('id'), 'status': item.get('status'),
                      'timestamp': event.get('timestamp'), 'output_fields_sha256': hashes}
            if item['type'] == 'CommandExecution':
                commands.append({**common, 'command': item.get('command'), 'cwd': item.get('cwd'), 'exit_code': item.get('exit_code'),
                                 'output_sha256': hashes.get('aggregated_output')})
            else:
                require(isinstance(item.get('changes'), dict), '需要人工检查未知FileChange shape')
                for name, change in item['changes'].items():
                    require(isinstance(change, dict), '需要人工检查未知change shape')
                    content = change.get('content')
                    changes.append({**common, 'file_path': name, 'change_type': change.get('type'), 'move_path': change.get('move_path'),
                                    'content_present': isinstance(content, str), 'content_sha256': text_sha(content) if isinstance(content, str) else None,
                                    'parse_status': 'parsed'})
    require(calls == audit['tool_calls'] and commands == audit['native_command_events'] and
            changes == audit['native_file_change_events'], '过程observer遗漏/改动了原生事件')
    # Do not equate an empty FileChange list with no writes. Retain all command
    # text and flag ordinary shell mutation syntax except stderr -> /dev/null.
    possible_writes = []
    for command in commands:
        text = ' '.join(command['command']) if isinstance(command['command'], list) else str(command['command'])
        stripped = re.sub(r'(?:[012])?>\s*/dev/null', '', text)
        if re.search(r'(^|[;&|\s])(mkdir|touch|tee|rm|mv|cp|apply_patch)\b|write_text|write_bytes|[>]\s*\S|git\s+(add|commit|init|checkout|reset)', stripped):
            possible_writes.append(command)
    workspaces = list((g / 'reports').glob('iteration-*/*/with_skill/outputs/workspace'))
    references = []
    for relative in sorted(set(re.findall(r'\.goal-task/[\w./-]+\.md', candidate))):
        retained = [p / relative for p in workspaces if (p / relative).is_file()]
        context = '\n'.join(line for line in candidate.splitlines() if relative in line)
        references.append({'relative_path': relative, 'retained': bool(retained), 'files': [{'path': str(p.relative_to(g)), 'sha256': sha(p)} for p in retained],
                           'candidate_context': context, 'review_status': 'retained_artifact' if retained else 'missing_or_future_proposal_requires_review'})
    return {'source_path': str(path), 'sha256': sha(path), 'tool_call_count': len(calls), 'command_event_count': len(commands),
            'distinct_command_item_count': len({(c['rollout'], c['item_id']) for c in commands}),
            'command_status_counts': dict(Counter(c['status'] for c in commands)), 'file_change_record_count': len(changes),
            'shell_mutation_candidates': possible_writes, 'file_changes': changes, 'final_artifact_references': references,
            'readonly_verified': False, 'requires_independent_process_review': True,
            'limits': 'Observer event/command review only; no general proof of zero filesystem side effects. No business/cache investigation claimed.'}


def verify_request_audits(root, manifest):
    reports = load(root / 'request-audit-status.json')
    require(reports == manifest['request_audits'], 'manifest与实际请求审计状态不同')
    for record in reports.values():
        for key in ('log', 'report'):
            if record.get(key):
                require(sha(safe(root, record[key])) == record[key + '_sha256'], '审计报告/日志指纹不符')
    strict = load(root / reports['strict_all_http_200_gate']['report'])
    outcome = load(root / reports['explicit_request_outcomes']['report'])
    require(outcome['valid'] and outcome['phase'] == 'final' and not outcome['findings'] and
            reports['explicit_request_outcomes']['passed'], '显式outcome审计未通过')
    require(outcome['accepted_requests'] == outcome['completed_200_requests'] + outcome['recorded_failed_attempts'] and
            outcome['completed_200_requests'] == outcome['native_token_usage_records'], '请求闭环数量不符')
    require(outcome['broker_events_sha256'] == sha(root / 'broker-events.jsonl') and
            outcome['auditor_sha256'] == sha(root / 'audit-request-outcomes.py'), 'outcome来源不符')
    require(strict['broker_events_sha256'] == sha(root / 'broker-events.jsonl') and
            strict['auditor_sha256'] == sha(root / 'audit-baseline-requests.py'), 'strict审计来源不符')
    require(bool(strict['valid']) == bool(reports['strict_all_http_200_gate']['passed']) ==
            bool(manifest['strict_all_http_200_gate_passed']), 'strict失败事实被改写')
    accepted, successful = [], []
    for line in (root / 'broker-events.jsonl').read_text().splitlines():
        event = json.loads(line)
        if event.get('event') == 'accepted':
            require(event['model'] == MODEL and event['effort'] == 'xhigh' and
                    event['thread_sha256'] == event['session_sha256'], '真实请求模型或身份不符')
            accepted.append(event)
        if event.get('event') == 'completed' and event.get('status') == 200:
            successful.append(event)
    key = lambda row: (row['session_sha256'], row['request_sha256'])
    require(Counter(map(key, accepted)) == Counter(map(key, successful)) +
            Counter(map(key, outcome['failed_attempts'])), '请求SHA未逐项闭环')
    require(len(accepted) == outcome['accepted_requests'], 'accepted计数不符')
    return strict, outcome, reports


def rollout_index(root, outcome):
    rows, sessions = [], set()
    for path in sorted(root.rglob('rollout-*.jsonl')):
        events = [json.loads(line) for line in path.read_text().splitlines()]
        metas = [e['payload'] for e in events if e.get('type') == 'session_meta']
        require(len(metas) == 1 and metas[0]['cli_version'] == VERSION, '原生会话版本不符')
        session = text_sha(metas[0]['id'])
        require(session not in sessions, '原生session复用')
        sessions.add(session)
        contexts = [e['payload'] for e in events if e.get('type') == 'turn_context']
        require(contexts and all(c['model'] == MODEL and c['effort'] == 'xhigh' for c in contexts),
                '原生上下文模型/思考深度不符')
        require(session in outcome['sessions'], '存在未闭环原生会话')
        ledger = outcome['sessions'][session]
        require(path == safe(root, ledger['rollout']) and sha(path) == ledger['sha256'], 'ledger rollout来源不符')
        tokens = sum(e.get('type') == 'event_msg' and e.get('payload', {}).get('type') == 'token_count' and
                     bool(e.get('payload', {}).get('info')) for e in events)
        require(tokens == ledger['native_token_usage_records'], '原生token记录数量不符')
        rows.append({'source_path': str(path.resolve()), 'relative_path': str(path.relative_to(root)),
                     'sha256': sha(path), 'bytes': path.stat().st_size, 'session_sha256': session,
                     'cli_version': metas[0]['cli_version'], 'model': MODEL, 'effort': 'xhigh',
                     'native_token_usage_records': tokens})
    require(sessions == set(outcome['sessions']), 'session账本存在未归档的原生rollout')
    return rows


def validate_trial(root, row, manifest, seen, rollouts):
    tid, cid, arm = row['trial_id'], row['case_id'], row['arm']
    base = root / 'trials' / tid
    g = base / 'G'
    j_name = row.get('judge_phase', 'J')
    require(j_name in ('J', 'J-repaired'), '未知质量Judge来源')
    j = base / j_name
    original_isolation = load(root / 'isolation-base.json')
    for phase in (g, j):
        require(sha(phase / 'bin/docker') == manifest['dependencies_sha256']['scripts/baseline-docker.py'],
                '实际Docker wrapper不是冻结版本')
        isolation = load(phase / 'isolation.json')
        require(all(isolation[key] == original_isolation[key] for key in
                    ('image_id', 'network', 'api_base_url', 'create_extra_args', 'after_start_command')),
                '阶段隔离策略与冻结根配置不同')
    expected = yaml.safe_load((root / 'dependencies/cases' / (cid + '.yaml')).read_text())
    gp, full_g, g_path, g_grade = native_phase(g, tid)
    jp, full_j, j_path, j_grade = native_phase(j, tid)
    require(gp['status'] == row['generation_capture_status'] == 'PASS' and
            jp['status'] == row['quality_status'] and row['J_dispatched'], 'trial结果与原生G/J不同')
    require(jp['status'] in ('PASS', 'FAIL'), '基础设施ERROR不能计作质量结论')
    candidate = gp['response']
    require(candidate.strip() and gp['response'] == jp['response'] and
            text_sha(candidate) == row['final_message_sha256'] and
            (g / 'sealed-final-message.txt').read_bytes() == candidate.encode(), 'G/J final原文不一致')
    seal, gm, jm = load(g / 'seal.json'), load(g / 'manifest.json'), load(j / 'manifest.json')
    require(seal['final_message_sha256'] == text_sha(candidate) and
            seal['meaning'] == 'capture_only_not_quality_pass' and seal['model_trace_copied_to_J'] is False,
            'G capture封存来源不符')
    require(gm['role'] == 'student_generation_capture_only' and gm['capture_pass_is_not_quality_pass'] and
            gm['mock_zero_model'] is False and gm['skill_sha256'] == manifest['arms'][arm], 'G不是冻结真实实验臂')
    runtime = {p: h for p, h in manifest['arms'][arm].items() if not p.startswith('evals/')}
    require(gm['skill_runtime_sha256'] == runtime and len(runtime) == 7, '运行Skill bundle不符')
    for relative, expected_sha in gm['skill_sha256'].items():
        require(sha(safe(g / gm['skill_snapshot'], relative)) == expected_sha, 'G Skill快照已变')
    ga = load(g / 'reports/isolation-audit.json')
    require(ga['valid'] and not ga['findings'] and ga['configuration'] == 'with_skill' and
            ga['skill_coverage'][tid]['actual_full_load_observed'], 'G没有实际完整加载Skill证据')
    g_ids = container_ids(g, manifest['image_id'], seen)
    installs = {p.stem: load(p) for p in (g / 'skill-install-audits').glob('*.json')}
    require(set(installs) == set(g_ids), '每G容器的目标安装审计未闭环')
    for ident, install in installs.items():
        require(install['container'] == ident and install['files'] == runtime and
                install['catalog_names'] == ['goal-prompt'] and install['model_called'] is False, '目标安装SHA不符')
    j_ids = container_ids(j, manifest['image_id'], seen)
    require(jm['role'] == 'score_only_frozen_replay' and jm['skills'] == [] and
            jm['student_model_calls'] == 0 and jm['mock_zero_model'] is False and
            jm['candidate_sha256'] == text_sha(candidate) and jm['candidate_is_unmodified_final_message'],
            'Judge不是独立真实冻结评分')
    audit_path = j / 'scoring-isolation-audit.json'
    if not audit_path.exists():
        repair_meta = manifest.get('repair', {})
        require(row.get('reused_existing_J') is True and
                repair_meta.get('reused_native_J', {}).get(tid) == j_name,
                '原J缺审计且没有明确修复复用声明')
        repair_root = safe(root, repair_meta['directory'])
        plan = load(repair_root / 'plan.json')
        prepared = repair_root / 'reused-J-audits' / (tid + '.json')
        audit_path = repair_root / 'dispatch-reused-J-audits' / (tid + '.json')
        expected_audit_sha = plan['repair_file_sha256']['reused-J-audits/' + tid + '.json']
        require(sha(prepared) == sha(audit_path) == expected_audit_sha,
                '复用J准备审计/实际复核审计与修复计划SHA不同')
        require(sha(j_path) == plan['original_file_sha256'][str(j_path.relative_to(root))],
                '原J原生结果与修复前封存SHA不同')
    ja, envelope = load(audit_path), load(j / 'candidate-envelope.json')
    require(ja['valid'] and ja['fresh_replay_container'] and ja['skills'] == [] and
            ja['final_message_sha256'] == text_sha(candidate) and envelope['data'] == candidate and
            envelope['sha256'] == text_sha(candidate) and envelope['bytes'] == len(candidate.encode()),
            'Judge新环境或final材料未保真')
    require(not (j / 'skill-install-audits').exists() and not (j / 'snapshot/target').exists(), 'Judge收到Skill安装')
    gc, gcase = config_phase(g, manifest)
    jc, jcase = config_phase(j, manifest)
    engine(gc['engine'])
    require(gc['skills'] == [{'source': 'local_path', 'path': 'target/goal-prompt'}] and
            gc['engine'] == {'name': 'codex', 'version': VERSION, 'model': {'provider': 'openai', 'name': MODEL}} and
            gcase['input']['prompt'] == manifest['prefix'] + expected['input']['prompt'] and
            gp['prompt'] == gcase['input']['prompt'], 'G输入/版本/配置不符')
    require(gcase['judge']['type'] == 'script' and gcase['judge']['script_path'] == 'evals/capture-only.sh',
            'G不是capture-only判分')
    require(full_g['requested_configuration']['engine'] == 'codex' and
            full_g['requested_configuration']['model'] == MODEL and
            full_g['requested_configuration']['version'] == gp['observed_version'] == VERSION,
            'G原生实际配置与冻结值不符')
    require(jc['skills'] == [] and jc['engine']['name'] == 'frozen-output-replay' and
            full_j['requested_configuration']['engine'] == 'frozen-output-replay' and
            jcase['input'] == expected['input'] and jcase.get('expect') == expected.get('expect'), 'J材料/expect不符')
    judge_type = expected['judge']['type']
    actual_judge = jcase['judge']
    judge_gate_passed = jp['gates']['passed']
    environment_case = cid in ENV_CASES
    environment_input = None
    actual_prompts = []
    if judge_type == 'agent_judge':
        engine(actual_judge['engine'])
        expected_context = dict(MINIMAL)
        if environment_case:
            expected_context.update(workspace_diff='include', limits={'max_bytes': 65536},
                                    attachments=[{'path': 'evals/initial-environment.json', 'label': 'initial_environment'}])
        require(actual_judge['context'] == expected_context and actual_judge['skills'] == [] and
                {k: v for k, v in actual_judge.items() if k not in ('engine', 'context', 'skills')} == expected['judge'],
                '原语义rubric或Judge配置变化')
        if judge_gate_passed:
            context = jp['grading']['judge_context']
            materials = {x['key']: x for x in context['manifest']['materials']}
            omitted = ('transcript', 'generated_files') if environment_case else ('transcript', 'workspace_diff', 'generated_files')
            require(context['profile'] == 'minimal' and materials['final_message']['mode'] == 'include' and
                    all(materials[k]['mode'] == 'omit' for k in omitted), 'Judge收到未许可材料或候选被截断')
            final_files = list((j / 'reports').rglob('context/final_message.txt'))
            require(final_files and all(p.read_bytes() == candidate.encode() for p in final_files) and
                    not list((j / 'reports').rglob('context/transcript.json')), 'Judge材料不保真或收到G trace')
            if environment_case:
                facts = root / 'dependencies/environment/initial-environment.json'
                inline = ENV_HEADER + facts.read_text()
                require(load(facts) == ENV_FACTS and sha(j / 'snapshot/evals/initial-environment.json') ==
                        jm['initial_environment_sha256'] == sha(facts), '每J共同初始事实不同')
                material = materials['workspace_diff']
                require(material['mode'] == 'include' and not material.get('truncated') and
                        material['original_bytes'] == len(inline.encode()) <= 65536, '共同事实未完整inline')
                diffs = list((j / 'reports').rglob('context/workspace.diff'))
                attachments = list((j / 'reports').rglob('context/attachments/01-initial-environment.json'))
                require(diffs and all(p.read_text() == inline for p in diffs) and
                        attachments and all(sha(p) == sha(facts) for p in attachments), 'SDK共同事实/附件字节不同')
                environment_input = {'facts_sha256': sha(facts), 'inline_sha256': text_sha(inline),
                                     'direct_inline_verified': False,
                                     'attachment_actual_read_observed': ja['initial_environment']['actual_read_observed'],
                                     'attachment_presence_is_not_read_proof': True}
        else:
            require(jp['status'] == 'FAIL' and all(a.get('skipped') for a in jp['grading']['assertion_results']
                                                 if not a['text'].startswith('expect.')),
                    'expect失败时Judge未按原生规则跳过')
    else:
        require(judge_type == 'script' and actual_judge == expected['judge'], 'script判分配置变化')
        script = safe(j / 'snapshot', actual_judge['script_path'])
        require(sha(script) == jm['script_judge_source_sha256'] ==
                manifest['dependencies_sha256']['evals/' + actual_judge['script_path']], 'script Judge源SHA变化')
        assertions = [a for a in jp['grading']['assertion_results']
                      if a['text'].startswith('script: ') and a['text'].endswith(script.name)]
        require(assertions and all(bool(a.get('skipped')) != bool(judge_gate_passed) for a in assertions),
                'script Judge执行/expect短路事实不符')
    g_rollouts = [r for r in rollouts if r['relative_path'].startswith(str(g.relative_to(root)) + '/')]
    j_rollouts = [r for r in rollouts if r['relative_path'].startswith(str(j.relative_to(root)) + '/')]
    require(g_rollouts and bool(j_rollouts) == (judge_type == 'agent_judge' and judge_gate_passed),
            'Judge模型调用/script或expect短路实际记录不符')
    for item in j_rollouts:
        for number, line in enumerate(Path(item['source_path']).read_text().splitlines(), 1):
            event = json.loads(line)
            payload = event.get('payload', {})
            if event.get('type') == 'response_item' and payload.get('role') in ('user', 'developer'):
                text = '\n'.join(x.get('text', '') for x in payload.get('content', []) if isinstance(x, dict))
                require('<skills_instructions>' not in text and '<skill>' not in text, 'Judge原生加载了Skill')
                if environment_case and payload.get('role') == 'user' and inline in text and candidate in text:
                    require(len(text.encode()) == jp['grading']['judge_context']['prompt_bytes'] and
                            all(c in text for c in expected['judge']['criteria']), '实际完整J prompt字节/criteria不同')
                    actual_prompts.append({'source_rollout': item['source_path'], 'source_rollout_sha256': item['sha256'],
                                           'source_line': number, 'role': 'user', 'text': text, 'sha256': text_sha(text)})
    if environment_case and judge_gate_passed:
        require(actual_prompts, '实际J输入缺完整初始事实')
        environment_input['direct_inline_verified'] = True
    process = process_evidence(g, cid, candidate) if environment_case else None
    invalid = []
    for other in sorted(base.iterdir()):
        if other.is_dir() and other.name.startswith('J') and other.name != j_name:
            raw_rollouts = [r for r in rollouts if r['relative_path'].startswith(str(other.relative_to(root)) + '/')]
            invalid.append({'path': str(other.relative_to(root)), 'counts_toward_quality': False,
                            'raw_rollouts': raw_rollouts, 'model_sessions': len(raw_rollouts),
                            'has_native_result': bool(list((other / 'reports').glob('iteration-*/result.json')))})
    return {**row, 'quality_source': str(j.relative_to(root)), 'quality_is_G_capture': False,
            'student_result_path': str(g_path.relative_to(root)), 'student_result_sha256': sha(g_path),
            'judge_result_path': str(j_path.relative_to(root)), 'judge_result_sha256': sha(j_path),
            'student_grading_path': str(g_grade.relative_to(root)), 'student_grading_sha256': sha(g_grade),
            'judge_grading_path': str(j_grade.relative_to(root)), 'judge_grading_sha256': sha(j_grade),
            'judge_type': judge_type, 'scoring_isolation_audit_path': str(audit_path.relative_to(root)),
            'scoring_isolation_audit_sha256': sha(audit_path), 'judge_gate_passed': judge_gate_passed,
            'judge_executed': judge_gate_passed, 'judge_skipped_by_expect': not judge_gate_passed,
            'judge_model_sessions': len(j_rollouts), 'student_model_sessions': len(g_rollouts),
            'expected_gates': expected.get('expect', {}), 'expected_judge': expected['judge'],
            'generation_container_ids': g_ids, 'judge_container_ids': j_ids,
            'skill_load_evidence': ga['skill_coverage'][tid], 'skill_sha256': gm['skill_sha256'],
            'student_raw_rollouts': g_rollouts, 'judge_raw_rollouts': j_rollouts,
            'invalid_judge_phases': invalid, 'response': candidate, 'grading': jp['grading'],
            'initial_environment_input': environment_input, 'actual_judge_prompts': actual_prompts,
            'student_process': process}


def validate_run(root, main_root=MAIN_RUN):
    manifest = load(root / 'manifest.json')
    completed(manifest)
    main_manifest = load(main_root / 'manifest.json')
    require(main_manifest.get('completed_utc') and main_manifest.get('all_isolation_audits_pass') and
            manifest['main_completed_at_prepare'] and
            sha(main_root / 'manifest.json') == manifest['main_reference']['manifest_sha256'] and
            sha(main_root / 'cases-combined.json') == manifest['main_reference']['cases_sha256'],
            '未绑定已经完成的原30例主批次')
    if 'current' in manifest['arms']:
        require(manifest['arms']['current'] == main_manifest['skill_sha256'], 'current不是原30冻结Skill')
    rows = load(root / 'trial-results.json')
    validate_order(manifest, rows)
    dependencies = load(root / 'dependencies/sha256.json')
    require(sha(root / 'dependencies/sha256.json') == manifest['dependency_manifest_sha256'] and
            dependencies == manifest['dependencies_sha256'], '依赖manifest变化')
    for relative, expected in dependencies.items():
        require(sha(safe(root / 'dependencies', relative)) == expected, '冻结依赖变化: ' + relative)
    initial_environment(root, manifest, main_manifest)
    require(dependencies['skill-up'] == manifest['binary_sha256'] and
            sha(root / 'run-failed-pairs.py') == manifest['runner_sha256'] and
            sha(root / 'prospective-protocol.md') == manifest['protocol_sha256'], '二进制/runner/protocol来源不符')
    if manifest.get('repair'):
        repair = safe(root, manifest['repair']['directory'])
        require(sha(repair / 'original-manifest.json') == manifest['repair']['original_manifest_sha256'] and
                sha(repair / 'repaired-harness.py') == manifest['repair']['repaired_harness_sha256'] and
                sha(repair / 'run-failed-pairs-resume.py') == manifest['repair']['resume_source_sha256'], '修复链来源不符')
        require(manifest['repair']['first_G_reused'] is True, '首G复用事实缺失')
    strict, outcome, request_status = verify_request_audits(root, manifest)
    rollouts = rollout_index(root, outcome)
    seen = set()
    trials = [validate_trial(root, row, manifest, seen, rollouts) for row in rows]
    require(sum(t['student_model_sessions'] > 0 for t in trials) == manifest['student_model_executions'], 'G执行计数不符')
    declared_judge_count = manifest['judge_model_executions']
    actual_judge_count = sum(t['judge_model_sessions'] > 0 for t in trials)
    configured_judge_phases = sum(t['judge_type'] == 'agent_judge' for t in trials)
    actual_judge_sessions = sum(t['judge_model_sessions'] for t in trials)
    require(declared_judge_count in (actual_judge_count, configured_judge_phases, actual_judge_sessions),
            'Judge声明计数既不匹配实际调用，也不匹配旧harness配置阶段计数')
    return manifest, trials, rollouts, strict, outcome, request_status


def archive(root, out, main_root=MAIN_RUN):
    require(not out.exists(), '拒绝覆盖已有归档')
    require(not out.is_relative_to(root) and not root.is_relative_to(out), '输出不可覆盖原run')
    require(not out.is_relative_to(main_root) and not main_root.is_relative_to(out), '输出不可覆盖主批次')
    manifest, trials, rollouts, strict, outcome, request_status = validate_run(root, main_root)
    # Copy source/config/grades/logs, but retain full raw rollouts in the local run
    # and point to exact bytes. The executable dependency is hashed, never copied.
    source = []
    for path in sorted(root.rglob('*')):
        if not path.is_file() or '__pycache__' in path.parts or path.suffix == '.pyc':
            continue
        require(not path.is_symlink(), '源文件不得为符号链接')
        relative = str(path.relative_to(root))
        omitted = relative == 'dependencies/skill-up' or path.name.startswith('rollout-')
        source.append({'relative_path': relative, 'source_path': str(path), 'sha256': sha(path),
                       'bytes': path.stat().st_size, 'copied': not omitted,
                       'omitted_reason': ('binary_hash_only' if relative == 'dependencies/skill-up' else
                                          'full_raw_rollout_local_index') if omitted else None})
    out.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.' + out.name + '-', dir=out.parent))
    try:
        for item in source:
            if item['copied']:
                destination = stage / 'run' / item['relative_path']
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item['source_path'], destination)
                require(sha(destination) == item['sha256'], '复制证据SHA不符')
        for trial in trials:
            target = stage / 'trials' / trial['trial_id']
            target.mkdir(parents=True)
            (target / 'response.txt').write_bytes(trial['response'].encode())
            dump(target / 'result.json', trial)
        scores = defaultdict(Counter)
        by_case = defaultdict(lambda: defaultdict(Counter))
        for trial in trials:
            scores[trial['arm']][trial['quality_status']] += 1
            by_case[trial['case_id']][trial['arm']][trial['quality_status']] += 1
        summary = {'source_run': str(root), 'source_manifest_sha256': sha(root / 'manifest.json'),
                   'main_reference': manifest['main_reference'], 'main_run': str(main_root),
                   'created_utc': datetime.now(timezone.utc).isoformat(), 'archive_model_calls': 0,
                   'real_trials': len(trials), 'case_ids': manifest['case_ids'], 'order': manifest['order'],
                   'model': MODEL, 'effort': 'xhigh', 'judge_model': MODEL, 'judge_effort': 'xhigh',
                   'cli_version': VERSION, 'binary_sha256': manifest['binary_sha256'],
                   'version_source': 'frozen G config plus native session_meta and observed_version',
                   'scores_by_arm': {arm: {s: values[s] for s in STATUSES} for arm, values in scores.items()},
                   'scores_by_case': {cid: {arm: {s: values[s] for s in STATUSES} for arm, values in arms.items()}
                                      for cid, arms in by_case.items()},
                   'generation_capture_is_quality': False,
                   'scoring_fresh_container_final_only': not bool(set(manifest['case_ids']) & ENV_CASES),
                   'scoring_common_initial_facts_inline': bool(set(manifest['case_ids']) & ENV_CASES),
                   'initial_environment': initial_environment(root, manifest, load(main_root / 'manifest.json')),
                   'absolute_style_blinding_claim': False, 'unique_scored_container_count':
                       len({c for t in trials for c in t['generation_container_ids'] + t['judge_container_ids']}),
                   'student_model_executions': manifest['student_model_executions'],
                   'judge_model_executions': sum(t['judge_model_sessions'] > 0 for t in trials),
                   'judge_model_sessions': sum(t['judge_model_sessions'] for t in trials),
                   'declared_judge_model_executions': manifest['judge_model_executions'],
                   'declared_judge_counter_meaning': 'harness-declared counter retained; old harness counts configured phases, actual execution derived independently from native rollouts',
                   'script_judge_executions': sum(t['judge_type'] == 'script' and t['judge_executed'] for t in trials),
                   'judges_skipped_by_expect': sum(t['judge_skipped_by_expect'] for t in trials),
                   'strict_all_http_200_gate': {'passed': strict['valid'], **request_status['strict_all_http_200_gate']},
                   'explicit_request_outcomes': {'valid': outcome['valid'], 'accepted_requests': outcome['accepted_requests'],
                                                'completed_200_requests': outcome['completed_200_requests'],
                                                'recorded_failed_attempts': outcome['recorded_failed_attempts'],
                                                'native_token_usage_records': outcome['native_token_usage_records']},
                   'repair': manifest.get('repair'),
                   'invalid_judge_phases': [p for t in trials for p in t['invalid_judge_phases']],
                   'raw_rollouts_stay_local': True, 'raw_rollout_index': 'raw-rollouts-index.json',
                   'source_inventory': 'source-inventory.json', 'archiver_sha256': sha(Path(__file__).resolve()),
                   'limits': ['small repeated sample; no population-level equivalence or regression conclusion',
                              'overall version effect combines shortening and earlier behavior changes',
                              'same explicit invocation prefix; separate from natural activation 30-case cohort',
                              'fresh Skill-free Judge does not prevent guessing a version from response style',
                              'mock/invalid setup grades excluded; capture PASS is not quality PASS',
                              'initial environment facts describe supplied material only; no completed business/cache investigation',
                              'process audit requires independent command/write review; no general zero-filesystem-effects claim']}
        process = [t['student_process'] for t in trials if t['student_process'] is not None]
        if process:
            summary['process_observations'] = {
                'native_command_events': sum(p['command_event_count'] for p in process),
                'distinct_native_command_items': sum(p['distinct_command_item_count'] for p in process),
                'tool_calls': sum(p['tool_call_count'] for p in process),
                'native_file_change_records': sum(p['file_change_record_count'] for p in process),
                'shell_mutation_candidates': [c for p in process for c in p['shell_mutation_candidates']],
                'artifact_references': [r for p in process for r in p['final_artifact_references']],
                'readonly_verified': False, 'requires_independent_process_review': True}
        dump(stage / 'summary.json', summary)
        dump(stage / 'source-inventory.json', source)
        dump(stage / 'raw-rollouts-index.json', rollouts)
        if process:
            dump(stage / 'process-observations.json', summary['process_observations'])
            for trial in trials:
                dump(stage / 'judge-prompts' / (trial['trial_id'] + '.json'), trial['actual_judge_prompts'])
        shutil.copy2(Path(__file__).resolve(), stage / 'summarize-failed-pairs.py')
        lines = ['# 失败样本的小规模版本对照', '',
                 '同一Luna xhigh、同显式调用前缀、冻结原始请求和rubric；每次G/J使用独立容器。G只采集输出，质量取新空Skill容器的J。', '',
                 '|案例|版本|PASS|FAIL|ERROR|', '|---|---|---:|---:|---:|']
        for cid, arms in summary['scores_by_case'].items():
            for arm, values in arms.items():
                lines.append(f"|{cid}|{arm}|{values['PASS']}|{values['FAIL']}|{values['ERROR']}|")
        lines += ['', f"真实student执行{summary['student_model_executions']}次，模型Judge执行{summary['judge_model_executions']}次，script Judge执行{summary['script_judge_executions']}次；归档过程模型调用0。", '',
                  f"strict全HTTP200门槛：{'PASS' if strict['valid'] else 'FAIL（保留原失败）'}；显式outcomes：{'PASS' if outcome['valid'] else 'FAIL'}。", '',
                  '初始J配置失败及repair链完整保留；first G复用，mock和无效J不计作质量成绩。' if manifest.get('repair') else
                  '所有质量结果均来自各trial原生J阶段；mock/预检不纳入质量统计。', '',
                  '本组是少量重复观察，不能据此证明版本等效或普遍无退化。版本差异包含精简及既有行为修复，不能把结果单独归因于长度。',
                  ('共同初始事实完整inline进入J；事实来自实际空业务项目probe，不是已完成缓存/业务调查。G命令/写入过程另存，readonly仍需独立核对。' if process else
                   'final-only评分隔离了原Skill目录与G执行痕迹；没有声称无法从输出风格猜测版本。'), '',
                  '逐trial正文、原grading、配置及修复记录见run/和trials/；完整原始rollout留在本地运行目录，raw-rollouts-index.json记录绝对路径、SHA及字节数。二进制仅保留指纹，不复制。']
        (stage / 'summary.md').write_text('\n'.join(lines) + '\n')
        for item in source:
            require(sha(Path(item['source_path'])) == item['sha256'], '归档中原证据发生变化')
        require(not out.exists(), '目标已出现，拒绝覆盖')
        stage.rename(out)
        print(json.dumps({'output': str(out), 'scores': summary['scores_by_arm'], 'archive_model_calls': 0}, ensure_ascii=False))
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def self_test():
    def refuses(action):
        try:
            action()
        except (RuntimeError, KeyError):
            return
        raise RuntimeError('错误状态未被拒绝')
    refuses(lambda: completed({}))
    base = {'trial_count': 4, 'student_executions_planned': 4, 'case_ids': ['a'], 'arms': {'before': {}, 'current': {}},
            'order': [{'order': i+1, 'trial_id': str(i), 'case_id': 'a', 'arm': arm, 'repetition': rep}
                      for i, (arm, rep) in enumerate([('before', 1), ('current', 1), ('current', 2), ('before', 2)])]}
    validate_order(base, base['order'])
    broken = {**base, 'order': [base['order'][0]] * 4}
    refuses(lambda: validate_order(broken, broken['order']))
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        refuses(lambda: archive(root, root))
        refuses(lambda: safe(root, '../escape'))
    print('PASS partial/mock gate, balanced unique trial order, overwrite refusal, path confinement; models0')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--main-run', type=Path, default=MAIN_RUN)
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    require(args.run and args.output, '必须显式指定--run和--output')
    archive(args.run.resolve(), args.output.resolve(), args.main_run.resolve())


if __name__ == '__main__':
    main()
