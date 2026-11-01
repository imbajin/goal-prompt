#!/usr/bin/env python3
"""冻结审计修复并续接原trial映射；复用已完成G/J，prepare不调用模型。"""
from pathlib import Path
from collections import Counter
import argparse
import datetime as dt
import difflib
import hashlib
import importlib.util
import json
import shutil
import subprocess
import yaml

REPO=Path(__file__).resolve().parents[3]

def require(value,message):
    if not value:raise RuntimeError(message)
def load(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def dump(path,value):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def module(path,name):
    spec=importlib.util.spec_from_file_location(name,path);value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value
def native_result(g):
    paths=list((g/'reports').glob('iteration-*/result.json'))
    if not paths:return None
    require(len(paths)==1,'G原始result不唯一')
    cases=load(paths[0])['case_results'];require(len(cases)==1,'G原始case数量不为1');return cases[0]
def existing_candidate(g):
    result=native_result(g);require(result and result['status']=='PASS','既有G未成功完成')
    candidate=(g/'sealed-final-message.txt').read_text();seal=load(g/'seal.json')
    require(candidate==result['response'] and hashlib.sha256(candidate.encode()).hexdigest()==seal['final_message_sha256'],'既有G seal与原始输出不同')
    for row in seal['raw_rollouts']:require(sha(g/row['path'])==row['sha256'],'既有G原生trace变化')
    require(seal['raw_rollouts'],'既有G缺真实模型trace');return candidate
def broker_snapshot(root,iso):
    raw=subprocess.check_output([iso['docker_binary'],'logs',iso['broker_container']],text=True)
    prefix=(root/'broker-events-before.jsonl').read_text();require(raw.startswith(prefix),'原broker前缀被改写或重置')
    return raw,raw[len(prefix):]
def assert_files(root,files):
    for relative,expected in files.items():require(sha(root/relative)==expected,'恢复前原始文件变化: '+relative)
def existing_j(root,trial):
    phases=[root/'trials'/trial/name for name in ('J','J-repaired')]
    completed=[phase for phase in phases if native_result(phase) is not None]
    require(len(completed)<=1,'同trial已有两个原生J结果，拒绝选择性使用')
    for phase in phases:
        if phase not in completed:require(not list(phase.rglob('rollout-*.jsonl')),'未完成J已有模型trace，不能盲目重跑')
    return completed[0] if completed else None

def prepare(root,repair):
    require(not repair.exists(),'拒绝覆盖修复证据');manifest=load(root/'manifest.json')
    require(manifest.get('models_started') and not manifest.get('completed_utc'),'只支持本次已开始且未完成的原批次')
    sequence=load(root/'arm-mapping-host-only.json');require(sequence==manifest['order'] and len(sequence)==manifest['trial_count'],'原trial映射变化')
    require([(r['case_id'],r['arm']) for r in sequence]==[(cid,arm) for cid in manifest['case_ids'] for arm in ('before','current','current','before')],'不是登记的两臂平衡顺序')
    frozen=root/'dependencies';h=module(REPO/'evals/skill-up/scripts/run-failed-pairs.py','repair_prepare_helpers');h.assert_frozen(frozen)
    require(sha(frozen/'sha256.json')==manifest['dependency_manifest_sha256'],'原冻结依赖manifest变化')
    require(sha(frozen/'skill-up')==manifest['binary_sha256'],'原binary变化')
    completed=[r for r in sequence if native_result(root/'trials'/r['trial_id']/'G') is not None]
    require(completed and completed==sequence[:len(completed)],'已完成G不是连续前缀，拒绝猜测其他状态')
    candidates={};reused_j={};recovered_judge_sessions=0
    for row in completed:
        trial=row['trial_id'];g=root/'trials'/trial/'G';candidates[trial]=existing_candidate(g)
        audit=load(g/'reports/isolation-audit.json')
        require(audit['valid'] and audit['skill_coverage'][trial]['actual_full_load_observed'],'既有G没有有效完整Skill加载证据')
        j=existing_j(root,trial)
        if j is not None:
            require(native_result(j)['status'] in ('PASS','FAIL'),'既有J尚不可判分，不能丢弃或盲目重跑')
            reused_j[trial]=j.name;recovered_judge_sessions+=len(h.judge_rollouts(j))
    require(list(reused_j)==[r['trial_id'] for r in completed[:len(reused_j)]],'既有J不是连续前缀')
    require(len(completed)-len(reused_j)<=1,'存在多个已完成G缺J，须人工分诊')
    for row in sequence:
        g=root/'trials'/row['trial_id']/'G';gm=load(g/'manifest.json')
        require(gm['skill_sha256']==manifest['arms'][row['arm']],'原G实验臂与映射不同')
        for relative,expected in gm['skill_sha256'].items():require(sha(g/'snapshot/target/goal-prompt'/relative)==expected,'原G Skill快照变化')
        if row not in completed:require(not (g/'run.log').exists(),'未完成G已有运行日志，不能盲目重跑')
    old_j=root/'trials'/sequence[0]['trial_id']/'J'
    iso=load(root/'isolation-base.json');iso['docker_binary']=shutil.which('docker')
    raw_before,delta=broker_snapshot(root,iso)
    accepted=[json.loads(line) for line in delta.splitlines() if json.loads(line).get('event')=='accepted']
    ids=set()
    for p in (root/'trials').rglob('rollout-*.jsonl'):
        sid=next(json.loads(line)['payload']['id'] for line in p.read_text().splitlines() if json.loads(line).get('type')=='session_meta')
        ids.add(hashlib.sha256(sid.encode()).hexdigest())
    require(accepted and {e['session_sha256'] for e in accepted}==ids,'有未归属既有原生trace的模型请求')
    repair.mkdir(parents=True,mode=0o700)
    for name in ('manifest.json','arm-mapping-host-only.json','broker-events-before.jsonl'):
        shutil.copy2(root/name,repair/('original-'+name))
    shutil.copy2(REPO/'evals/skill-up/scripts/run-failed-pairs.py',repair/'repaired-harness.py')
    shutil.copy2(Path(__file__),repair/'run-failed-pairs-resume.py')
    (repair/'harness-repair.diff').write_text(''.join(difflib.unified_diff((root/'run-failed-pairs.py').read_text().splitlines(True),
        (repair/'repaired-harness.py').read_text().splitlines(True),fromfile='original-frozen-harness',tofile='repaired-harness')))
    (repair/'broker-events-at-repair.jsonl').write_text(delta)
    originals={}
    for name in ('manifest.json','arm-mapping-host-only.json','broker-events-before.jsonl','run-failed-pairs.py','frozen-run-baseline.py','audit-baseline-requests.py','audit-request-outcomes.py','isolation-base.json','dependencies/sha256.json'):
        originals[name]=sha(root/name)
    for row in sequence:
        for phase in ('G','J','J-repaired'):
            for p in (root/'trials'/row['trial_id']/phase).rglob('*'):
                if p.is_file():originals[str(p.relative_to(root))]=sha(p)
    for row in sequence:
        case=yaml.safe_load((frozen/'cases'/f"{row['case_id']}.yaml").read_text())
        j=repair/'real-judge-preflight'/row['trial_id']
        candidate=candidates.get(row['trial_id'],'仅用于真实Judge配置预检，不作质量证据。')
        h.prepare_scoring(j,row['trial_id'],case,candidate,iso,manifest['defaults'],manifest['retry'],frozen)
        config=yaml.safe_load((j/'snapshot/evals/case.yaml').read_text())
        if case['judge']['type']=='agent_judge':require('model' not in config['judge'] and config['judge']['engine']==h.ENGINE,'修复后真实Judge仍有model冲突')
        if row==sequence[0] and (old_j/'snapshot/evals/case.yaml').exists():
            original=yaml.safe_load((old_j/'snapshot/evals/case.yaml').read_text())
            original['judge'].pop('model',None)
            require(original==config,'首J修复改变了model冲突以外的case规则')
            (repair/'first-J-case-repair.diff').write_text(''.join(difflib.unified_diff((old_j/'snapshot/evals/case.yaml').read_text().splitlines(True),
                (j/'snapshot/evals/case.yaml').read_text().splitlines(True),fromfile='original-invalid-J-case',tofile='repaired-J-case')))
        h.run_cli(frozen/'skill-up',j,validate_only=True)
        if row['trial_id'] in reused_j:
            old=root/'trials'/row['trial_id']/reused_j[row['trial_id']]
            h.audit_scoring(old,case,candidate,audit_output=repair/'reused-J-audits'/f"{row['trial_id']}.json")
    raw_after,_=broker_snapshot(root,iso)
    accepted_key=lambda text:Counter((e['session_sha256'],e['request_sha256'],e['counts']['allowed']) for e in map(json.loads,text.splitlines()) if e.get('event')=='accepted')
    require(accepted_key(raw_before)==accepted_key(raw_after),'prepare期间发生模型请求')
    plan={'created_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'run':str(root),'repair':str(repair),'prepare_passed':True,
          'scope':'resume original mapping; reuse completed G and native J verdicts; remaining fresh J-repaired',
          'models_called_during_prepare':0,'original_manifest_student_counter':manifest['student_model_executions'],
          'recovered_student_executions_from_native_results':len(completed),'recovered_judge_model_sessions':recovered_judge_sessions,
          'reused_G':[r['trial_id'] for r in completed],'reused_J':reused_j,'non_mock_real_judge_preflights':len(sequence),
          'original_file_sha256':originals,'repaired_harness_sha256':sha(repair/'repaired-harness.py'),
          'resume_source_sha256':sha(repair/'run-failed-pairs-resume.py'),'original_frozen_dependency_sha256':sha(frozen/'sha256.json'),
          'original_broker_prefix_sha256':sha(root/'broker-events-before.jsonl'),'sequence':sequence,
          'judge_repair':'accept native expect-gate FAIL+SKIP; count actual model rollouts; preserve rubric/threshold/input/context',
          'reuse_first_G':True,'dispatch_started':False}
    plan['repair_file_sha256']={str(p.relative_to(repair)):sha(p) for p in repair.rglob('*') if p.is_file()}
    dump(repair/'plan.json',plan)
    print(f'修复准备完成：复用{len(completed)}G/{len(reused_j)}个原生J结果，{len(sequence)}个真实J预检通过；新增模型请求0')

def dispatch(root,repair):
    plan=load(repair/'plan.json');require(plan['prepare_passed'] and plan['models_called_during_prepare']==0 and not plan['dispatch_started'],'修复未ready或已派发，拒绝重复')
    require(plan['run']==str(root) and plan['repair']==str(repair),'修复目录不同')
    assert_files(root,plan['original_file_sha256']);assert_files(repair,plan['repair_file_sha256'])
    h=module(repair/'repaired-harness.py','repair_dispatch_helpers');frozen=root/'dependencies';h.assert_frozen(frozen)
    require(sha(frozen/'sha256.json')==plan['original_frozen_dependency_sha256'],'原冻结依赖变化')
    manifest=load(root/'manifest.json');iso=load(root/'isolation-base.json');iso['docker_binary']=shutil.which('docker')
    broker_snapshot(root,iso)  # Never replace the original pre-first-G prefix.
    plan['dispatch_started']=True;plan['started_utc']=dt.datetime.now(dt.timezone.utc).isoformat();dump(repair/'plan.json',plan)
    manifest['student_model_executions']=plan['recovered_student_executions_from_native_results'];manifest['judge_model_executions']=plan['recovered_judge_model_sessions']
    manifest['repair']={'directory':str(repair.relative_to(root)),'original_manifest_sha256':sha(repair/'original-manifest.json'),
        'repaired_harness_sha256':plan['repaired_harness_sha256'],'resume_source_sha256':plan['resume_source_sha256'],
        'student_counter_recovered_from_native_results':plan['recovered_student_executions_from_native_results'],'first_G_reused':True,
        'reused_native_J':plan['reused_J'],'quality_source':'reused native J verdicts plus remaining J-repaired; uniformly audited'}
    dump(root/'manifest.json',manifest);results=[]
    for row in plan['sequence']:
        trial=row['trial_id'];g=root/'trials'/trial/'G';j=root/'trials'/trial/plan['reused_J'].get(trial,'J-repaired');h.assert_frozen(frozen)
        case=yaml.safe_load((frozen/'cases'/f"{row['case_id']}.yaml").read_text())
        if trial in plan['reused_G']:candidate=existing_candidate(g);captured=native_result(g)
        else:
            require(native_result(g) is None and not (g/'run.log').exists(),'未运行G已有执行证据，拒绝重复')
            captured=h.run_cli(frozen/'skill-up',g);manifest['student_model_executions']+=1
            candidate=h.capture_seal(g,captured,require_real=True);dump(root/'manifest.json',manifest)
            if candidate is not None:h.audit_generation(root,g,trial)
        if candidate is None:
            results.append({**row,'generation_capture_status':captured['status'],'quality_status':'UNSCORABLE','J_dispatched':False,'error':captured.get('error')})
            dump(root/'trial-results.json',results);continue
        if trial in plan['reused_J']:
            scored=native_result(j)
            h.audit_scoring(j,case,candidate,audit_output=repair/'dispatch-reused-J-audits'/f'{trial}.json')
        else:
            h.prepare_scoring(j,trial,case,candidate,iso,manifest['defaults'],manifest['retry'],frozen)
            h.run_cli(frozen/'skill-up',j,validate_only=True)
            scored=h.run_cli(frozen/'skill-up',j);h.audit_scoring(j,case,candidate)
        g_ids=load(g/'containers.json');j_ids=load(j/'containers.json')
        require(len(g_ids)==len(j_ids)==1 and not set(g_ids)&set(j_ids),'修复后G/J未隔离')
        if trial not in plan['reused_J']:manifest['judge_model_executions']+=len(h.judge_rollouts(j))
        results.append({**row,'generation_capture_status':captured['status'],'quality_status':scored['status'],'J_dispatched':True,
            'judge_phase':j.name,'first_G_reused':row==plan['sequence'][0],'reused_existing_J':trial in plan['reused_J'],'error':scored.get('error'),
            'configured_judge_type':case['judge']['type'],'judge_model_sessions':len(h.judge_rollouts(j)),'expect_gate_failed':h.expect_gate_failed(scored),
            'judge_skipped_by_expect':h.expect_gate_failed(scored),
            'final_message_sha256':hashlib.sha256(candidate.encode()).hexdigest()})
        dump(root/'trial-results.json',results);dump(root/'manifest.json',manifest)
    manifest['cases_finished_utc']=dt.datetime.now(dt.timezone.utc).isoformat();dump(root/'manifest.json',manifest)
    h.snapshot_broker(root,iso);h.assert_frozen(frozen);h.final_request_audits(root,manifest)
    require(sha(root/'broker-events-before.jsonl')==plan['original_broker_prefix_sha256'],'原broker prefix被改变')
    manifest['completed_utc']=dt.datetime.now(dt.timezone.utc).isoformat();dump(root/'manifest.json',manifest)
    plan['completed_utc']=manifest['completed_utc'];dump(repair/'plan.json',plan)
    print('原trial映射恢复完成：既有G/J未重跑，全部真实质量结果原样保留')

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run',type=Path,required=True);parser.add_argument('--repair',type=Path,required=True)
    mode=parser.add_mutually_exclusive_group(required=True);mode.add_argument('--prepare-only',action='store_true');mode.add_argument('--dispatch',action='store_true')
    args=parser.parse_args();root=args.run.resolve();repair=args.repair.resolve();require(repair.is_relative_to(root),'修复证据应留在原运行目录下')
    if args.prepare_only:prepare(root,repair)
    else:dispatch(root,repair)

if __name__=='__main__':main()
