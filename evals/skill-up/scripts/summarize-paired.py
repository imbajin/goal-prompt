#!/usr/bin/env python3
"""归档已完成的Luna配对结果；只读取证据，不运行模型、不重判、不覆盖replay。"""
from pathlib import Path
from collections import Counter
import argparse
import hashlib
import json
import re
import shutil

REPO=Path(__file__).resolve().parents[3]
MODEL='gpt-6-luna'
STATUSES=('PASS','FAIL','ERROR','SKIP')
SECRET=re.compile(rb'(?:sk-(?:ant-)?[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,})')

def require(condition,message):
    if not condition:raise RuntimeError(message)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def load(path):return json.loads(path.read_text())
def dump(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def counts(cases):return {s:sum(c['status']==s for c in cases) for s in STATUSES}
def under(root,relative):
    path=(root/relative).resolve();require(path.is_relative_to(root),'证据路径越界');return path

def validate_run(root,configuration):
    m=load(root/'manifest.json')
    require(m.get('completed_utc') and m.get('all_isolation_audits_pass'),'批次尚未完成；禁止归档partial run')
    require(m['model']==m['judge_model']==MODEL and m['effort']==m['judge_effort']=='xhigh','模型或深度不符')
    require(m.get('prefix') is None and m['parallelism']==1,'输入前缀或并行度变化')
    require(len(m['case_ids'])==len(set(m['case_ids']))==30,'必须恰好原30个唯一ID')
    spec=load(root/'isolation.json');require(sha(root/'isolation.json')==m['isolation_sha256'],'冻结隔离文件已变')
    positive=('script_execution','tmp_execution_mount','host_paths_hidden','credentials_absent','catalog','no_materialized_skills','network_rules','ripgrep','broker_policy')
    if configuration=='with_skill':positive+=('workspace_target_catalog','judge_empty_catalog','with_skill_pipeline')
    for key in positive:require(spec['checks'][key]['exit_code']==0,'隔离正探针不符: '+key)
    for key in ('identity_missing_denied','identity_bad_uuid_denied','other_model_denied','other_effort_denied','unknown_remote_tool_denied','remote_tool_denied','other_route_denied'):
        require(spec['checks'][key]['exit_code']==22,'HTTP拒绝探针不符: '+key)
    for key in ('top_level_generate_command_denied','proxy_github_denied','direct_public_denied','host_gateway_denied'):
        require(spec['checks'][key]['exit_code']!=0,'网络/入口拒绝探针不符: '+key)
    aliases={'workspace_target_catalog':('workspace-target-catalog.json','workspace-target-catalog.stderr'),
             'judge_empty_catalog':('judge-empty-catalog.json','judge-empty-catalog.stderr')}
    for key,check in spec['checks'].items():
        if key=='with_skill_pipeline':require(sha(root/'preflight/with-skill-pipeline-result.json')==check['result_sha256'],'安装管线预检已变');continue
        names=aliases.get(key,(f'broker-{key}.stdout',f'broker-{key}.stderr'))
        for stream,name in zip(('stdout','stderr'),names):require(sha(root/'preflight'/name)==check[stream+'_sha256'],'预检输出已变: '+name)
    runner='run-with-skill.py' if configuration=='with_skill' else 'run-baseline.py'
    for filename,key in ((runner,'runner_sha256'),('bin/docker','docker_wrapper_sha256'),('audit-baseline-requests.py','request_auditor_sha256')):
        if key in m:require(sha(under(root,filename))==m[key],'冻结文件已变: '+filename)
    if 'baseline_helpers_sha256' in m:require(sha(root/'run-baseline.py')==m['baseline_helpers_sha256'],'实际helper已变')
    if 'isolation_original_sha256' in m:require(sha(root/'isolation-original.json')==m['isolation_original_sha256'],'原始预检配置已变')
    for key,filename in (('pilot_gate_sha256','pilot-request-coverage.json'),('pilot_broker_events_sha256','pilot-broker-events.jsonl')):
        if key in m:require(sha(root/filename)==m[key],'pilot门槛证据已变')
    for relative,expected in m['snapshot_sha256'].items():require(sha(under(root/'snapshot',relative))==expected,'快照SHA不符: '+relative)
    cases=load(root/'cases-combined.json');native=[];case_dirs={};skill_coverage={};contexts=[]
    for batch,expected_n in (('pilot',1),('remaining',29)):
        results=sorted((root/batch).glob('iteration-*/result.json'));require(len(results)==1,'原始批次结果数量错误')
        data=load(results[0]);require(len(data['case_results'])==expected_n,'原始批次case数量错误')
        role=data['requested_configuration'];require(role['role']=='runner' and role['engine']=='codex' and role['model']==MODEL,'runner配置不符')
        native.extend(data['case_results'])
        for case in data['case_results']:case_dirs[case['case_id']]=results[0].parent/case['case_id']/configuration
        audit_name=m.get('isolation_audit_files',{}).get(batch,'isolation-audit.json')
        require(audit_name in ('isolation-audit.json','isolation-audit-reviewed.json'),'未知审计文件')
        audit=load(root/batch/audit_name);require(audit['valid'] and not audit['findings'],'隔离审计未通过')
        require(all(c['model']==MODEL and c['effort']=='xhigh' for c in audit['contexts']),'runner/Judge上下文不符')
        contexts.extend(audit['contexts'])
        if configuration=='with_skill':
            require(audit['configuration']=='with_skill','审计组错误')
            skill_coverage.update(audit['skill_coverage'])
    require(cases==native,'combined与原生result.json不一致')
    require(len(cases)==30 and {c['case_id'] for c in cases}==set(m['case_ids']),'结果集合不完整')
    require(all(c['configuration']==configuration and c['status'] in STATUSES for c in cases),'结果组或状态非法')
    require(counts(cases)=={s:m['case_status_counts'].get(s,0) for s in STATUSES},'manifest计数不符')
    for case in cases:
        if case['status'] in ('PASS','FAIL'):require(bool(case.get('response','').strip()),'可判分case缺响应')
    broker=load(root/'broker-audit.json');coverage=load(root/m.get('request_coverage_file','request-coverage.json'))
    require(broker['valid'] and broker['unmatched_requests']==0,'代理归属审计失败')
    require(coverage['valid'] and coverage['phase']=='final' and not coverage['findings'],'必须有final请求对账')
    require(coverage['accepted_requests']==coverage['completed_200_requests']+coverage.get('recorded_failed_attempts',0) and coverage['completed_200_requests']==coverage['native_token_usage_records'],'模型请求未精确闭环')
    require(sha(root/'broker-events.jsonl')==coverage['broker_events_sha256'],'代理输入已变')
    require(sha(root/m.get('request_auditor_file','audit-baseline-requests.py'))==coverage['auditor_sha256'],'对账源码已变')
    accepted=[];completed=[]
    for line in (root/'broker-events.jsonl').read_text().splitlines():
        e=json.loads(line)
        if e.get('event')=='accepted':accepted.append(e)
        elif e.get('event')=='completed' and e.get('status')==200:completed.append(e)
    key=lambda e:(e.get('session_sha256'),e.get('request_sha256'))
    require(Counter(map(key,accepted))==Counter(map(key,completed))+Counter(map(key,coverage.get('failed_attempts',[]))),'accepted/completed请求SHA不匹配')
    require(all(e['model']==MODEL and e['effort']=='xhigh' and e['thread_sha256']==e['session_sha256'] for e in accepted),'真实请求违反模型/身份契约')
    require(len(accepted)==coverage['accepted_requests'],'代理计数不符')
    actual_sessions=set();raw_rollouts=[]
    for path in sorted(root.rglob('rollout-*.jsonl')):
        require(path.resolve().is_relative_to(root),'rollout路径越界')
        events=[json.loads(line) for line in path.read_text().splitlines()]
        sid=next(e['payload']['id'] for e in events if e.get('type')=='session_meta')
        digest=hashlib.sha256(sid.encode()).hexdigest();require(digest not in actual_sessions,'重复归档会话');actual_sessions.add(digest)
        record=coverage['sessions'].get(digest);require(record and sha(path)==record['sha256'],'rollout与对账来源不一致')
        require(sum(e.get('type')=='token_usage_record' for e in events)==record['native_token_usage_records']==record.get('completed_200_requests',record['accepted_requests']) and record['accepted_requests']==record['native_token_usage_records']+record.get('recorded_failed_attempts',0),'会话请求数量不匹配')
        for event in events:
            if event.get('type')=='turn_context':require(event['payload'].get('model')==MODEL and event['payload'].get('effort')=='xhigh','原生上下文模型不符')
        raw_rollouts.append({'original_path':str(path),'sha256':sha(path),'bytes':path.stat().st_size})
    require(actual_sessions==set(coverage['sessions']),'会话集合不完整')
    if configuration=='with_skill':
        require(m.get('configuration')=='with_skill' and m['with_skill_executed'] is True and m['without_skill_executed'] is False,'with组范围不符')
        require(set(skill_coverage)==set(m['case_ids']),'加载覆盖不完整')
        require(all(r['catalog_seen'] for r in skill_coverage.values()),'case未见目标catalog')
        for row in skill_coverage.values():require(row['actual_full_load_observed']==(row['native_full_injection'] or row['full_file_read']),'加载分类不一致')
        bundle=m['skill_sha256'];runtime={p:h for p,h in bundle.items() if not p.startswith('evals/')}
        require(bundle==spec['skill_bundle_sha256'],'Skill源与预检不一致')
        require(len(bundle)==9 and len(runtime)==7 and runtime==m['skill_runtime_sha256']==spec['target_skill']['files'],'源九文件/运行七文件不符')
        require(m['native_install_excludes']==['evals/'],'native安装排除规则不符')
        skill_root=under(root,m['skill_snapshot'])
        for relative,expected in bundle.items():require(sha(under(skill_root,relative))==expected,'Skill源快照已变')
        containers={p.stem:load(p) for p in (root/'container-audits').glob('*.json')}
        installs={p.stem:load(p) for p in (root/'skill-install-audits').glob('*.json')}
        cleanups={p.stem:load(p) for p in (root/'skill-cleanup-audits').glob('*.json')}
        require(len(installs)==len(containers)==30 and set(installs)==set(containers),'目标安装/容器审计不完整')
        for ident,row in containers.items():
            require(row['image']==spec['image_id'] and row['readonly'] and row['cap_drop']==['ALL'] and not row['bind_mounts'],'容器文件/权限隔离不符')
            require(row['networks']==[spec['network']] and row['network_locked'] and row['catalog_empty'],'容器网络/初始catalog不符')
            require('no-new-privileges' in row['security_opt'],'缺少no-new-privileges')
        for ident,row in installs.items():require(row['container']==ident and row['files']==runtime and row['catalog_names']==['goal-prompt'] and row['model_called'] is False,'目标安装审计不符')
        judges=sum(bool(list((path/'outputs/judge/run').glob('rollout-*.jsonl'))) for path in case_dirs.values())
        require(len(cleanups)==judges and set(cleanups)<=set(installs),'模型Judge前清除记录不完整')
        for ident,row in cleanups.items():require(row['container']==ident and row['files']=={} and row['catalog_names']==[] and row['model_called'] is False,'Judge catalog非空')
        lifecycle={'container_audits':len(containers),'install_audits':len(installs),'cleanup_audits':len(cleanups),'cases_with_model_judge':judges}
    else:
        require(m['with_skill_executed'] is False and m['skills']==[],'对照组混入Skill')
        lifecycle={}
    return {'root':root,'manifest':m,'spec':spec,'cases':cases,'case_dirs':case_dirs,'coverage':coverage,'skill_coverage':skill_coverage,
            'raw_rollouts':raw_rollouts,'lifecycle':lifecycle,'contexts':contexts}

def validate_replay(replay,control):
    summary=load(replay/'summary.json');record=load(replay/'confirmation-brief.json');calibrated=load(replay/'without-calibrated.json')
    original={c['case_id']:c for c in control['cases']}
    require(summary['models_rerun']==record['model_calls']==0 and summary['changed_cases']==['confirmation-brief'],'replay范围不符')
    require(len(calibrated)==30 and {c['case_id'] for c in calibrated}==set(original),'校准对照不完整')
    altered=[]
    for case in calibrated:
        raw=original[case['case_id']]
        require(case['configuration']=='without_skill' and case['response']==raw['response'] and case['prompt']==raw['prompt'],'校准不得改原输入/输出')
        require(case['original_status']==raw['status'],'原始状态不符')
        stripped={k:v for k,v in case.items() if k not in ('original_status','verdict_provenance','original_grading')}
        if case['case_id']!='confirmation-brief':require(stripped==raw and case['verdict_provenance']=='unchanged_original','非目标case被改判')
        else:
            require(raw['status']=='FAIL' and case['status']=='PASS' and case['original_grading']==raw['grading'],'目标重判记录不符')
            require({k:v for k,v in stripped.items() if k not in ('status','grading')}=={k:v for k,v in raw.items() if k not in ('status','grading')},'replay改动了非判分字段')
            require(case['verdict_provenance']=='corrected_script_replay' and case['grading']['status']=='PASS','缺少replay来源')
            require(case['grading']['summary']['failed']==0 and all(a['passed'] for a in case['grading']['assertion_results']),'校准PASS仍含失败断言')
        if raw['status']!=case['status']:altered.append(case['case_id'])
    require(altered==['confirmation-brief'],'非目标状态变化')
    raw=original['confirmation-brief'];require(hashlib.sha256(raw['response'].encode()).hexdigest()==record['original_response_sha256'],'replay响应已变')
    native_path=Path(record['original_native_result_path']).resolve()
    require(native_path.is_relative_to(control['root']) and sha(native_path)==record['original_raw_result_sha256'],'replay原始batch来源不符')
    require(record['original_replay']['exit_code']==1 and record['corrected_replay']['exit_code']==0 and record['original_artifacts_unchanged'],'replay证据不符')
    require(sha(replay/'corrected-check-confirmation-brief.sh')==record['corrected_judge_sha256'],'修正Judge已变')
    require(sha(replay/'original-check-confirmation-brief.sh')==record['original_judge_sha256'],'原Judge已变')
    require(Counter(summary['raw_counts'])==Counter(c['status'] for c in control['cases']) and Counter(summary['calibrated_counts'])==Counter(c['status'] for c in calibrated),'replay汇总计数不符')
    return calibrated,record

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,required=True);parser.add_argument('--without',type=Path,default=REPO/'.eval-work/luna-xhigh-control-v4-20261030')
    parser.add_argument('--replay',type=Path,default=REPO/'evals/skill-up/evidence/luna-paired/replay')
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--invalid-run',type=Path,action='append',default=[])
    args=parser.parse_args();run=args.run.resolve();without=args.without.resolve();replay=args.replay.resolve();out=args.output.resolve()
    require(not out.exists(),'拒绝覆盖已有归档')
    require(not out.is_relative_to(replay) and not replay.is_relative_to(out),'禁止覆盖replay树')
    require(not out.is_relative_to(run) and not out.is_relative_to(without),'归档不能写入模型原件目录')
    with_data=validate_run(run,'with_skill');control=validate_run(without,'without_skill');calibrated,replay_record=validate_replay(replay,control)
    m=with_data['manifest'];prior=control['manifest']
    for key in ('model','effort','judge_model','judge_effort','binary_sha256','skill_up_version','defaults','retry','parallelism','case_ids','original_case_sha256','prefix'):
        require(m[key]==prior[key],'两组冻结协议不同: '+key)
    require(with_data['spec']['image_id']==control['spec']['image_id'] and with_data['spec']['create_extra_args']==control['spec']['create_extra_args'],'两组运行镜像/隔离策略不同')
    require(m['without_reference']['manifest_sha256']==sha(without/'manifest.json') and m['without_reference']['native_case_results_sha256']==sha(without/'cases-combined.json'),'对照引用已变')
    require(not (set(with_data['coverage']['sessions'])&set(control['coverage']['sessions'])),'两组复用了会话')
    checker=run/'snapshot/skill-up/fixtures/scripts/check-confirmation-brief.sh'
    require(sha(checker)==replay_record['corrected_judge_sha256'],'with组未使用同一修正Judge')
    allowed_fixtures={'skill-up/fixtures/scripts/check-confirmation-brief.sh','skill-up/fixtures/scripts/test-judges.sh'}
    old_files={k:v for k,v in prior['snapshot_sha256'].items() if k.startswith('skill-up/fixtures/')}
    new_files={k:v for k,v in m['snapshot_sha256'].items() if k.startswith('skill-up/fixtures/')}
    actual_changes={k:{'without_sha256':old_files.get(k),'with_sha256':new_files.get(k)} for k in sorted(set(old_files)|set(new_files)) if old_files.get(k)!=new_files.get(k)}
    require(actual_changes==m['fixture_changes_from_without'],'fixture变化记录与实际快照不一致')
    require(set(m['fixture_changes_from_without'])<=allowed_fixtures,'出现其他判分/fixture变化')
    raw_map={c['case_id']:c for c in control['cases']};cal_map={c['case_id']:c for c in calibrated};with_map={c['case_id']:c for c in with_data['cases']}
    for cid in m['case_ids']:require(with_map[cid]['prompt']==raw_map[cid]['prompt'],'原始用户输入被改变: '+cid)
    invalid=[]
    for attempt in args.invalid_run:
        attempt=attempt.resolve();meta=load(attempt/'manifest.json');require(attempt!=run and not meta.get('completed_utc'),'无效尝试参数错误')
        rows=[]
        for file in attempt.glob('*/iteration-*/result.json'):rows.extend(load(file)['case_results'])
        require(rows and all(c['configuration']=='with_skill' and c['status']=='ERROR' and c.get('turns',0)==0 and c.get('input_tokens',0)==0 and c.get('output_tokens',0)==0 and 'failed to setup case environment' in c.get('error','') for c in rows),'仅接收模型前设置失败的with尝试')
        require(not list(attempt.rglob('rollout-*.jsonl')),'无效尝试包含模型rollout，不能当零模型')
        invalid.append({'directory':str(attempt),'excluded_from_quality_counts':True,'kind':'pre_agent_setup_error','raw_rollouts_local':[],
                        'limits':'在agent执行前设置失败，没有完整模型输出；不计入最终30例。'})
    out.mkdir(parents=True);files=[];allowed=[run,*[Path(a['directory']) for a in invalid]]
    def archive(source,relative):
        source=source.resolve();require(source.is_file() and any(source.is_relative_to(p) for p in allowed),'归档源路径越界')
        data=source.read_bytes();require(len(data)<4*1024*1024 and not SECRET.search(data),'文件过大或疑似含凭据，拒绝归档: '+str(source))
        dest=out/relative;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,dest)
        files.append({'archive':str(relative),'original_path':str(source),'sha256':sha(source),'bytes':len(data)})
    for relative in ('manifest.json','isolation.json','isolation-original.json','run-with-skill.py','run-baseline.py','audit-baseline-requests.py','bin/docker','without-only.patch',
                     'broker-audit.json','broker-events.jsonl','request-coverage.json','cases-combined.json','docker-events.jsonl','containers.json','validate.log','dry-run.log'):
        archive(run/relative,Path('run')/relative)
    for relative in ('manifest-before-audit-correction.json','finalize-reviewed-audit.py','reviewed-audit-source.py','post-audit-runner.py','lifecycle-audit.json','request-audit.log','request-outcomes.json','post-request-auditor.py','request-outcomes-audit.log','finalize-reviewed-audit-v1.py','request-audit-v1.log'):
        if (run/relative).exists():archive(run/relative,Path('run')/relative)
    for name in ('snapshot','container-audits','skill-install-audits','skill-cleanup-audits','skill-install-progress','preflight'):
        for source in sorted((run/name).rglob('*')):
            if source.is_file():archive(source,Path('run')/source.relative_to(run))
    for batch in ('pilot','remaining'):
        for suffix in ('-command.json','-events.jsonl','.log','-request-coverage.json','-broker-events.jsonl'):
            archive(run/(batch+suffix),Path('run')/(batch+suffix))
        for source in (run/batch).glob('isolation-audit*.json'):archive(source,Path('run')/source.relative_to(run))
        for source in (run/batch).glob('iteration-*/result.json'):archive(source,Path('run')/source.relative_to(run))
        for source in (run/batch).rglob('*'):
            if source.is_file() and (source.name in ('grading.json','evaluation.json','eval_metadata.json','response.md','stdout.json')
                or '/outputs/workspace/.goal-task/' in str(source) or '/outputs/judge/context/' in str(source)):
                archive(source,Path('run')/source.relative_to(run))
    for attempt in invalid:
        base=Path(attempt['directory'])
        for source in base.rglob('*'):
            if source.is_file() and (source.name in ('manifest.json','isolation.json','result.json','response.md','stdout.json','pilot.log','docker-events.jsonl','run-with-skill.py','run-baseline.py','audit-baseline-requests.py')
                                    or source.relative_to(base).as_posix() in ('bin/docker','snapshot/evals/eval.yaml') or source.name.endswith('-events.jsonl')):
                archive(source,Path('invalid-attempts')/base.name/source.relative_to(base))
    rows=[]
    for cid in m['case_ids']:
        case=with_map[cid];relative=Path('cases')/cid;dump(out/relative/'result.json',case)
        (out/relative/'response.md').write_text(case.get('response','')+'\n')
        observed=with_data['skill_coverage'][cid]
        row={'case_id':cid,'without_raw':raw_map[cid]['status'],'without_calibrated':cal_map[cid]['status'],'with_skill':case['status'],
             'replay_changed_without':raw_map[cid]['status']!=cal_map[cid]['status'],'skill_coverage':observed,
             'negative_trigger_case':cid=='trigger-boundary','scorable_pair':cal_map[cid]['status'] in ('PASS','FAIL') and case['status'] in ('PASS','FAIL'),
             'failed_assertions':[r for r in (case.get('grading') or {}).get('assertion_results',[]) if not r.get('passed')],
             'error':case.get('error'),'evidence':str(relative/'result.json')}
        rows.append(row)
    positive=[r for r in rows if not r['negative_trigger_case']]
    transitions=dict(Counter(r['without_calibrated']+' -> '+r['with_skill'] for r in rows))
    pair_counts={'both_pass':sum(r['without_calibrated']==r['with_skill']=='PASS' for r in rows),
                 'with_only_pass':sum(r['without_calibrated']=='FAIL' and r['with_skill']=='PASS' for r in rows),
                 'without_only_pass':sum(r['without_calibrated']=='PASS' and r['with_skill']=='FAIL' for r in rows),
                 'both_fail':sum(r['without_calibrated']==r['with_skill']=='FAIL' for r in rows),
                 'unscorable':sum(not r['scorable_pair'] for r in rows)}
    require(sum(pair_counts.values())==30,'配对分母不符')
    summary={'with_run':str(run),'without_original_run':str(without),'status_counts':{'without_raw':counts(control['cases']),'without_calibrated_replay':counts(calibrated),'with_skill':counts(with_data['cases'])},
             'pair_counts':pair_counts,'transitions':transitions,'cases':rows,'invalid_attempts':invalid,
             'activation':{'positive_cases':len(positive),'positive_full_load_observed':sum(r['skill_coverage']['actual_full_load_observed'] for r in positive),
                           'positive_catalog_only':[r['case_id'] for r in positive if not r['skill_coverage']['actual_full_load_observed']],
                           'negative_trigger_full_load':with_data['skill_coverage']['trigger-boundary']['actual_full_load_observed']},
             'lifecycle':with_data['lifecycle'],'requests':{'accepted':with_data['coverage']['accepted_requests'],'completed_200':with_data['coverage']['completed_200_requests'],
                         'native_usage_records':with_data['coverage']['native_token_usage_records'],'recorded_failed_attempts':with_data['coverage'].get('recorded_failed_attempts',0),'sessions':len(with_data['coverage']['sessions'])},
             'replay_reference':{'directory':str(replay),'files':{str(p.relative_to(replay)):sha(p) for p in replay.rglob('*') if p.is_file()},'model_calls':0},
             'raw_rollouts_local':with_data['raw_rollouts'],'limits':'仅该冻结单批次配对；有catalog不等于加载全文，未加载不宣称Skill起效。Judge目标路径已移除、catalog/原生指令无目标，但candidate trace可包含Skill文本作为待审数据，不构成盲评保证。对照只离线replay一项，其余原判保留；没有重跑without或其他模型。'}
    dump(out/'summary.json',summary)
    c=summary['status_counts'];lines=['# Luna xhigh 原30例配对结果','', '| 口径 | PASS | FAIL | ERROR | SKIP |','| --- | ---: | ---: | ---: | ---: |']
    for label,key in (('without原始实测','without_raw'),('without校准（既有输出replay）','without_calibrated_replay'),('with-Skill本轮实测','with_skill')):
        lines.append('| '+label+' | '+' | '.join(str(c[key][s]) for s in STATUSES)+' |')
    lines+=['', '对照模型未重跑；仅confirmation-brief使用修正Judge重放既有输出，原始6/24/0保留。',
            '',f"配对分类：{pair_counts}。ERROR/SKIP不算通过或行为失败。",
            '',f"29个正向案例中，观察到完整Skill加载{summary['activation']['positive_full_load_observed']}个。目录可见与全文加载分开，trigger-boundary不要求加载。",
            '', '| Case | without原始 | without校准 | with-Skill | catalog | 原生全文注入 | 完整文件读取 | 输出/原判 |',
            '| --- | --- | --- | --- | --- | --- | --- | --- |']
    yes=lambda value:'是' if value else '否'
    for r in rows:
        cov=r['skill_coverage'];lines.append(f"| {r['case_id']} | {r['without_raw']} | {r['without_calibrated']} | {r['with_skill']} | {yes(cov['catalog_seen'])} | {yes(cov['native_full_injection'])} | {yes(cov['full_file_read'])} | [输出](cases/{r['case_id']}/response.md) / [判分]({r['evidence']}) |")
    lines+=['','完整rollout保存在本地运行目录，路径/大小/SHA见summary.json；原始响应、Judge上下文、判分、配置、安装/清除和请求审计随归档保留。',
            '同模型、深度、镜像、原输入和默认门槛；旧对照使用早版宿主守卫，实际隔离证据保留。单次结果不提供普遍能力、成本或稳定性保证。',
            'Judge目标路径已移除、catalog与原生指令无目标；candidate trace可能包含Skill文本作为待审数据，不能称完全不接触Skill文本或盲评。',
            '容量导致goal停滞的宿主案例单独记录，不加入这30个案例，也不作为Skill修复平台能力的证据。']
    (out/'summary.md').write_text('\n'.join(lines)+'\n')
    copied={r['archive'] for r in files};generated=[{'archive':str(p.relative_to(out)),'sha256':sha(p),'bytes':p.stat().st_size}
             for p in out.rglob('*') if p.is_file() and str(p.relative_to(out)) not in copied]
    dump(out/'archive-integrity.json',{'files':files,'generated_files':generated,'raw_rollouts_local':with_data['raw_rollouts'],
                                    'without_manifest_sha256':sha(without/'manifest.json'),'replay_reference':summary['replay_reference']})
    print(json.dumps({'status_counts':c,'pair_counts':pair_counts,'archived_files':len(files),'positive_full_load_observed':summary['activation']['positive_full_load_observed']},ensure_ascii=False))

if __name__=='__main__':main()
