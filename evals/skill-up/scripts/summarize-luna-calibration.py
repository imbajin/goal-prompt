#!/usr/bin/env python3
"""只读汇总Luna原始、同Linux脚本、必要业务产物三种判分口径；不调用模型。"""
from pathlib import Path
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timezone
import argparse
import hashlib
import json
import shutil
import tempfile

REPO = Path(__file__).resolve().parents[3]
MAIN = REPO/'evals/skill-up/evidence/luna-paired/with/run'
CONTROL = REPO/'evals/skill-up/evidence/luna-xhigh-control/run'
V3 = REPO/'evals/skill-up/evidence/luna-paired/replay-v3'
SCRIPT = REPO/'.goal-task/luna-with-skill/script-isolation-replay/run-v2-final'
STAGE2 = REPO/'.eval-work/luna-failed-pairs-stage2-v1-20261030'
STATE = REPO/'.eval-work/luna-state-aware-v2-20261030'
FOUR = {'confirmation-brief', 'stage2-migration', 'preauthorized-permissions', 'compaction-checkpoint'}
STATUSES = ('PASS', 'FAIL', 'ERROR', 'SKIP')


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def text_sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def dump(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n')


def counts(rows, field):
    counter = Counter(row[field] for row in rows)
    return {key: counter[key] for key in STATUSES}


def pairing(with_rows, without_rows, field):
    require([r['case_id'] for r in with_rows] == [r['case_id'] for r in without_rows], '配对顺序不符')
    matrix = Counter()
    details = []
    for a, b in zip(with_rows, without_rows):
        x, y = a[field], b[field]
        category = ('both_pass' if x == y == 'PASS' else 'with_only_pass' if x == 'PASS' else
                    'without_only_pass' if y == 'PASS' else 'both_nonpass')
        matrix[category] += 1
        details.append({'case_id': a['case_id'], 'with': x, 'without': y, 'category': category})
    return {'counts': {key: matrix[key] for key in ('with_only_pass', 'without_only_pass', 'both_pass', 'both_nonpass')},
            'cases': details}


class Sources:
    def __init__(self):
        self.items = {}

    def remember(self, path):
        path = path.resolve()
        require(path.is_relative_to(REPO) and path.is_file() and not path.is_symlink(), '非法证据路径')
        fingerprint = sha(path)
        if path in self.items:
            require(self.items[path] == fingerprint, '读取中源文件变化')
        self.items[path] = fingerprint
        return {'path': str(path), 'sha256': fingerprint}

    def read(self, path):
        self.remember(path)
        return load(path)

    def verify(self):
        for path, expected in self.items.items():
            require(sha(path) == expected, '原件发生变化: '+str(path))


def main_native(root, sources):
    manifest = sources.read(root/'manifest.json')
    require(manifest.get('completed_utc') and manifest['all_isolation_audits_pass'], 'main批次未完成')
    require(manifest['model'] == manifest['judge_model'] == 'gpt-6-luna' and
            manifest['effort'] == manifest['judge_effort'] == 'xhigh', 'main模型/effort不符')
    rows = sources.read(root/'cases-combined.json')
    native = []
    for name in ('pilot', 'remaining'):
        native.extend(sources.read(root/name/'iteration-1/result.json')['case_results'])
    require(rows == native and len(rows) == len({r['case_id'] for r in rows}) == 30, 'main原生集合不符')
    return rows


def script_results(root, sources):
    manifest = sources.read(root/'manifest.json')
    require(manifest.get('completed_utc') and manifest['valid'] and manifest['models_called'] == 0 and
            manifest['student_generations_rerun'] == 0 and manifest['broker_accepted_delta'] == 0,
            '同镜像script重放未完成/不为零模型')
    require(sources.read(root/'broker-zero-delta.json')['accepted_delta'] == 0, '重放含模型请求')
    for relative, expected in manifest['frozen_dependencies_sha256'].items():
        require(sources.remember(root/relative)['sha256'] == expected, '重放冻结依赖变动')
    rows, originals = sources.read(root/'results.json'), sources.read(root/'source-outputs.json')
    require(len(rows) == len(originals) == len(manifest['sequence']) == 12, 'script重放不完整')
    result = {}
    for record, original, plan in zip(rows, originals, manifest['sequence']):
        native_path = root/record['native_result_path']
        native_doc = sources.read(native_path)
        require(len(native_doc['case_results']) == 1, 'script native数量错误')
        native = native_doc['case_results'][0]
        require(native['case_id'] == plan['id'] == record['id'] and native['response'] == original['response'] and
                text_sha(native['response']) == record['response_sha256'] == plan['response_sha256'] and
                native['status'] == record['native_linux_status'] and native['grading'] == record['native_grading'] and
                sources.remember(native_path)['sha256'] == record['native_result_sha256'], 'script原文/判分不符')
        require(sources.remember(Path(original['source_native']))['sha256'] == original['source_native_sha256'], 'script旧native来源不符')
        key = (original['source_group'], original.get('trial_id', original['case_id']))
        require(key not in result, 'script来源重复')
        result[key] = {'status': native['status'], 'response': native['response'],
                       'source': sources.remember(native_path), 'original': original,
                       'grading': native['grading'], 'script_record': sources.remember(root/'results.json')}
    return result


def state_results(root, sources):
    manifest = sources.read(root/'manifest.json')
    require(manifest.get('completed_utc') and manifest['request_outcome_coverage_valid'] and
            manifest['student_model_executions'] == 0 and manifest['judge_model_executions'] >= 1 and
            manifest['model'] == manifest['judge_model'] == 'gpt-6-luna' and
            manifest['effort'] == manifest['judge_effort'] == 'xhigh', 'state-aware批次未完成或配置不符')
    for relative, expected in manifest['prepared_files_sha256'].items():
        require(sources.remember(root/relative)['sha256'] == expected, 'state-aware冻结文件变化')
    for path, expected in manifest['source_files_sha256'].items():
        require(sources.remember(Path(path))['sha256'] == expected, 'state-aware原始业务证据变化')
    mapping = sources.read(root/'source-mapping-host-only.json')
    require(sources.remember(root/'source-mapping-host-only.json')['sha256'] == manifest['mapping_sha256'], 'mappingSHA不符')
    records = sources.read(root/'rejudged-results.json')
    require(len(records) == len(mapping) == manifest['sample_count'] == 6, 'state-aware样本不完整')
    result = {}
    actual_sessions = 0
    for record, planned in zip(records, mapping):
        require({k: record[k] for k in planned} == planned, 'state-aware mapping被改写')
        phase = root/'trials'/record['trial_id']/'J'
        paths = list((phase/'reports').glob('iteration-*/result.json'))
        require(len(paths) == 1, 'state-aware native不唯一')
        native = sources.read(paths[0])['case_results'][0]
        audit = sources.read(phase/'state-aware-audit.json')
        require(native['status'] == record['status'] == audit['raw_status'] and
                text_sha(native['response']) == record['candidate_sha256'] == audit['candidate_sha256'] and
                audit['valid'] and audit['student_model_calls'] == 0 and
                audit['business_snapshot_sha256'] == record['business_snapshot_sha256'], 'state-aware原文/判分/产物不符')
        require(sources.remember(root/'samples'/record['trial_id']/'candidate.txt')['sha256'] == record['candidate_sha256'],
                'state-aware冻结final不同')
        require(sources.remember(root/'samples'/record['trial_id']/'business-snapshot.patch')['sha256'] == record['business_snapshot_sha256'],
                'state-aware业务快照不同')
        rollouts = list(phase.rglob('rollout-*.jsonl'))
        require(len(rollouts) == record['judge_model_sessions'] == audit['judge_model_sessions'], '真实J会话数不符')
        require(bool(rollouts) != bool(record['expect_gate_failed']), 'expect短路与实际调用不符')
        actual_sessions += len(rollouts)
        key = (record['cohort'], record['source_trial'])
        require(key not in result, 'state-aware来源重复')
        result[key] = {'status': native['status'], 'response': native['response'], 'grading': native['grading'],
                       'source': sources.remember(paths[0]), 'audit_source': sources.remember(phase/'state-aware-audit.json'),
                       'mapping': planned, 'business_snapshot': sources.remember(root/'samples'/record['trial_id']/'business-snapshot.patch'),
                       'business_context_version': manifest['context_version']}
    outcome = sources.read(root/'request-outcomes.json')
    require(outcome['valid'] and not outcome['findings'] and outcome['recorded_failed_attempts'] == 0 and
            outcome['accepted_requests'] == outcome['completed_200_requests'] == outcome['native_token_usage_records'] and
            actual_sessions == manifest['judge_model_executions'] == len(outcome['sessions']), 'state-aware请求未闭环')
    require(sources.remember(root/'broker-events.jsonl')['sha256'] == outcome['broker_events_sha256'], 'state-awarebrokerSHA不同')
    return result, {'student_model_executions': 0, 'judge_model_sessions': actual_sessions,
                    'accepted_requests': outcome['accepted_requests'], 'completed_200_requests': outcome['completed_200_requests'],
                    'native_token_usage_records': outcome['native_token_usage_records'], 'manifest': sources.remember(root/'manifest.json')}


def preserve(raw, script_status, artifact_status, provenance):
    row = deepcopy(raw)
    require(script_status in STATUSES and artifact_status in STATUSES, '校准状态非法')
    row.update(script_calibrated_status=script_status, artifact_aware_status=artifact_status,
               calibration_provenance=provenance)
    require(row['status'] == raw['status'] and row['grading'] == raw['grading'] and row['response'] == raw['response'], '不得改原生判分/原文')
    return row


def aggregate(out, state_root, script_root):
    require(not out.exists(), '拒绝覆盖calibrated目录')
    for root in (MAIN, CONTROL, V3, script_root, STAGE2, state_root):
        require(not out.is_relative_to(root) and not root.is_relative_to(out), '输出不可覆盖源目录')
    sources = Sources()
    native_main = {'with': main_native(MAIN, sources), 'without': main_native(CONTROL, sources)}
    scripts = script_results(script_root, sources)
    states, state_usage = state_results(state_root, sources)
    main_rows = {}
    for group, raw_rows in native_main.items():
        previous = sources.read(V3/(group+'-calibrated.json'))
        require([r['case_id'] for r in raw_rows] == [r['case_id'] for r in previous], '旧校准集合不同')
        calibrated = []
        for raw, prior in zip(raw_rows, previous):
            require(raw['status'] == prior['status'] and raw['grading'] == prior['grading'] and raw['response'] == prior['response'],
                    '旧校准不保留原native')
            cid = raw['case_id'];script_status = raw['status'];proof = {'base': 'unchanged_native', 'base_source': sources.remember((MAIN if group=='with' else CONTROL)/'cases-combined.json')}
            if cid in FOUR:
                score = scripts[('main-'+group, cid)]
                require(score['response'] == raw['response'], 'script未对应原main final')
                script_status = score['status'];proof['script'] = {k: score[k] for k in ('source', 'grading', 'script_record')}
            require(script_status == prior['calibrated_status'], 'Linux与旧v3 main口径不同，需独立复核')
            artifact_status = script_status
            if cid == 'batch-goal':
                score = states[('main-'+group, cid)]
                require(score['response'] == raw['response'], 'state-aware未对应原main final')
                artifact_status = score['status'];proof['artifact_aware'] = {k: score[k] for k in ('source', 'grading', 'audit_source', 'mapping', 'business_snapshot', 'business_context_version')}
            calibrated.append(preserve(raw, script_status, artifact_status, proof))
        main_rows[group] = calibrated
    stage_manifest = sources.read(STAGE2/'manifest.json')
    require(stage_manifest.get('completed_utc') and stage_manifest['request_outcome_coverage_valid'], 'stage2未完成')
    planned = stage_manifest['order'];original = sources.read(STAGE2/'trial-results.json')
    require(len(planned) == len(original) == stage_manifest['trial_count'] == 8, 'stage2原trial不完整')
    stage_rows = []
    for plan, record in zip(planned, original):
        require(all(record[k] == v for k, v in plan.items()), 'stage2顺序/版本改变')
        tid = record['trial_id'];phase = STAGE2/'trials'/tid
        j = phase/record.get('judge_phase', 'J')
        j_native_path = next((j/'reports').glob('iteration-*/result.json'))
        g_native_path = next((phase/'G/reports').glob('iteration-*/result.json'))
        raw = sources.read(j_native_path)['case_results'][0]
        generated = sources.read(g_native_path)['case_results'][0]
        require(raw['status'] == record['quality_status'] and raw['response'] == generated['response'] and
                text_sha(raw['response']) == record['final_message_sha256'], 'stage2原生quality/final不符')
        script_status = raw['status'];proof = {'base': sources.remember(j_native_path), 'generation': sources.remember(g_native_path)}
        if record['case_id'] == 'preauthorized-permissions':
            score = scripts[('stage2-preauth', tid)]
            require(score['response'] == raw['response'], 'script未对应stage2原final')
            script_status = score['status'];proof['script'] = {k: score[k] for k in ('source', 'grading', 'script_record')}
        artifact_status = script_status
        if record['case_id'] == 'batch-goal':
            score = states[('stage2', tid)]
            require(score['response'] == raw['response'], 'state-aware未对应stage2原final')
            artifact_status = score['status'];proof['artifact_aware'] = {k: score[k] for k in ('source', 'grading', 'audit_source', 'mapping', 'business_snapshot', 'business_context_version')}
        row = preserve(raw, script_status, artifact_status, proof)
        row.update(source_trial_id=tid, source_case_id=record['case_id'], arm=record['arm'],
                   repetition=record['repetition'], order=record['order'], original_trial_record=record,
                   generation_capture_status=generated['status'], generation_capture_is_quality=False)
        stage_rows.append(row)
    stage_scores = defaultdict(lambda: defaultdict(list))
    for row in stage_rows:
        stage_scores[row['source_case_id']][row['arm']].append(row)
    summary = {'created_utc': datetime.now(timezone.utc).isoformat(), 'aggregator_model_calls': 0,
               'script_replay_source': sources.remember(script_root/'manifest.json'),
               'calibration_student_executions': 0, 'state_aware_judge_usage': state_usage,
               'main': {group: {name: counts(rows, field) for name, field in
                        (('raw', 'status'), ('script_calibrated', 'script_calibrated_status'), ('artifact_aware', 'artifact_aware_status'))}
                        for group, rows in main_rows.items()},
               'main_pairing': {name: pairing(main_rows['with'], main_rows['without'], field) for name, field in
                                (('raw', 'status'), ('script_calibrated', 'script_calibrated_status'), ('artifact_aware', 'artifact_aware_status'))},
               'stage2': {cid: {arm: {name: counts(rows, field) for name, field in
                                   (('raw', 'status'), ('script_calibrated', 'script_calibrated_status'), ('artifact_aware', 'artifact_aware_status'))}
                               for arm, rows in arms.items()} for cid, arms in stage_scores.items()},
               'main_remaining_nonpass': {group: [r['case_id'] for r in rows if r['artifact_aware_status'] != 'PASS']
                                          for group, rows in main_rows.items()},
               'original_status_grading_and_response_preserved': True,
               'not_full_30_case_new_blind_judging': True, 'skill_changed_for_calibration': False,
               'state_aware_scope': 'only batch-goal; final plus necessary captured business files; new context, not Skill improvement',
               'not_complete_eval_groups': ['stage3 (excluded entirely; no unfinished result read or counted)'],
               'limits': ['Main native semantic Judges may see Skill text inside candidate trace; not fully blinded.',
                          'State-aware only changes business-material representation for Batch, preserving original rubric.',
                          'Script replays are zero-model; state-aware has real Judge sessions and requests listed separately.',
                          'Natural30 and explicit version-pair cohorts remain separate; small repeats do not prove population equivalence.'],
               'aggregator_sha256': sha(Path(__file__).resolve())}
    sources.verify()
    out.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.'+out.name+'-', dir=out.parent))
    try:
        for group, rows in main_rows.items():
            dump(stage/('main-'+group+'.json'), rows)
            for row in rows:
                target = stage/'main'/group/row['case_id']/'response.txt'
                target.parent.mkdir(parents=True, exist_ok=True);target.write_bytes(row['response'].encode())
        dump(stage/'stage2.json', stage_rows)
        for row in stage_rows:
            target = stage/'stage2'/row['source_trial_id']/'response.txt'
            target.parent.mkdir(parents=True, exist_ok=True);target.write_bytes(row['response'].encode())
        dump(stage/'summary.json', summary)
        inventory = []
        for index, (path, fingerprint) in enumerate(sorted(sources.items.items(), key=lambda x: str(x[0]))):
            # All source JSON is retained verbatim. Large binaries/rollouts are indexed only.
            copied = path.suffix == '.json'
            destination = f'source-json/{index:04d}-{path.name}' if copied else None
            if copied:
                target = stage/destination;target.parent.mkdir(parents=True, exist_ok=True);shutil.copy2(path, target)
                require(sha(target) == fingerprint, 'source JSON复制不一致')
            inventory.append({'source_path': str(path), 'sha256': fingerprint, 'bytes': path.stat().st_size,
                              'copied_source_json': destination})
        dump(stage/'source-index.json', inventory)
        shutil.copy2(Path(__file__).resolve(), stage/'summarize-luna-calibration.py')
        lines = ['# Luna结果的多口径汇总', '',
                 '保留原生status、grading和response，新增script_calibrated_status及artifact_aware_status。汇总过程模型调用0；所有校准student执行0。', '',
                 '|主30口径|with PASS/FAIL/ERROR|without PASS/FAIL/ERROR|', '|---|---|---|']
        for name, title in [('raw', '原始'), ('script_calibrated', '同镜像Linux确定性校准'), ('artifact_aware', '另补必要业务产物的局部口径')]:
            def cell(group):
                c = summary['main'][group][name];return f"{c['PASS']}/{c['FAIL']}/{c['ERROR']}"
            lines.append(f'|{title}|{cell("with")}|{cell("without")}|')
        lines += ['', '必要业务产物口径的主配对矩阵：' + json.dumps(summary['main_pairing']['artifact_aware']['counts'], ensure_ascii=False) + '。', '',
                  f"Batch补材料真实Judge会话{state_usage['judge_model_sessions']}，请求{state_usage['accepted_requests']}，HTTP200及native记录各{state_usage['native_token_usage_records']}；不是全30新盲评，也不是Skill效果改善。", '',
                  '|阶段2案例|版本|原始PASS/FAIL|仅脚本校准PASS/FAIL|再补业务产物PASS/FAIL|', '|---|---|---|---|---|']
        for cid, arms in summary['stage2'].items():
            for arm, values in arms.items():
                def c(name):
                    v = values[name];return f"{v['PASS']}/{v['FAIL']}"
                lines.append(f'|{cid}|{arm}|{c("raw")}|{c("script_calibrated")}|{c("artifact_aware")}|')
        lines += ['', '阶段2原8FAIL全部保留。Batch两个before缺final goal，expect原生FAIL且语义Judge跳过；current使用真实业务文件补齐Judge材料。preauth两个before真实缺上级/安全边界仍FAIL；current两项确定性误报由同Linux新源校准。',
                  '正文来自native response逐字节UTF-8编码，不补换行；每个校准字段附判分来源与完整原生grading。source-index.json保存原件路径与SHA，所有所读源JSON另逐字节复制。',
                  'main剩余with非PASS：' + '、'.join(summary['main_remaining_nonpass']['with']) + '。',
                  '阶段3另行归档，不在本汇总的读取和统计范围。候选修改、完整6.1全量及Claude Code实机不由本次校准证明。']
        (stage/'summary.md').write_text('\n'.join(lines)+'\n')
        sources.verify();require(not out.exists(), '目标已出现，拒绝覆盖');stage.rename(out)
        print(json.dumps({'output': str(out), 'main': summary['main'], 'matrix': summary['main_pairing']['artifact_aware']['counts'],
                          'aggregator_model_calls': 0}, ensure_ascii=False))
    finally:
        if stage.exists():shutil.rmtree(stage)


def self_test():
    raw = {'case_id': 'a', 'status': 'FAIL', 'grading': {'status': 'FAIL'}, 'response': '无换行原文'}
    row = preserve(raw, 'PASS', 'PASS', {'kind': 'test'})
    require(row['status'] == raw['status'] and row['grading'] == raw['grading'] and raw['status'] == 'FAIL', '原生覆盖')
    result = pairing([row], [preserve(raw, 'FAIL', 'FAIL', {})], 'artifact_aware_status')
    require(result['counts']['with_only_pass'] == 1 and result['counts']['both_pass'] == 0, '矩阵计算错误')
    print('PASS raw fields preserved, layered status and computed matrix; models0')


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, default=REPO/'evals/skill-up/evidence/luna-paired/calibrated')
parser.add_argument('--state-aware-run', type=Path, default=STATE)
parser.add_argument('--script-replay-run', type=Path, default=SCRIPT)
parser.add_argument('--self-test', action='store_true')
args = parser.parse_args()
self_test() if args.self_test else aggregate(args.output.resolve(), args.state_aware_run.resolve(), args.script_replay_run.resolve())
