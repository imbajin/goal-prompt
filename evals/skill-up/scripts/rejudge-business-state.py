#!/usr/bin/env python3
"""只重判六份冻结Batch输出；业务产物快照直接入J，无新student运行。"""
from pathlib import Path
import argparse
import copy
import difflib
import hashlib
import importlib.util
import json
import re
import shutil
import uuid
import yaml

REPO=Path(__file__).resolve().parents[3]
MAX_BYTES=65536
CONTEXT={'profile':'minimal','final_message':'include','transcript':'omit',
         'workspace_diff':'include','generated_files':'omit','limits':{'max_bytes':MAX_BYTES}}
HEADER='从已封存生成业务文件重建的产物快照（非VCS原始diff）；仅为被评估产物的数据表示，不代表原Agent执行过这些diff动作。\n'
STABLE_HELPER=REPO/'.eval-work/luna-failed-pairs-stage2-v1-20261030/repair-stage2-v2/repaired-harness.py'
STABLE_HELPER_SHA='39b4dd2df6f1737f9c27c84a48efecf3e69528fe766a22601736c7e6fdda2196'

def require(value,message):
    if not value:raise RuntimeError(message)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def digest(value):return hashlib.sha256(value.encode()).hexdigest()
def load(path):return json.loads(path.read_text())
def dump(path,value):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def helper(path):
    spec=importlib.util.spec_from_file_location('state_rejudge_helpers',path);h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h);return h
def result(phase):
    paths=list((phase/'reports').glob('iteration-*/result.json'));require(len(paths)==1,'缺唯一阶段原始result')
    cases=load(paths[0])['case_results'];require(len(cases)==1,'阶段不止1case');return cases[0]
def phase_for_case(root,configuration):
    paths=list((root/'remaining').glob('iteration-*/result.json'));require(len(paths)==1,'主批次原始result不唯一')
    row=next(c for c in load(paths[0])['case_results'] if c['case_id']=='batch-goal')
    return row,paths[0].parent/'batch-goal'/configuration,paths[0]

def redact(text):
    # Remove only instruction-source identity. Business quantities, relative
    # references, requirements and uncertainty remain verbatim.
    # ASCII identifiers next to Chinese text still reveal the source. Unicode
    # word boundaries treat those scripts as a single word and miss the label.
    left=r'(?<![A-Za-z0-9_])';right=r'(?![A-Za-z0-9_])'
    instruction=left+r'(?:goal-prompt|SKILL\.md|skills?)'+right
    model=left+r'(?:gpt[- ]?6[A-Za-z0-9_.-]*(?:\s+(?:luna|sol|terra|astra))?|6(?:\.\d+)?[- ](?:luna|sol|terra|astra))'+right
    arm=left+r'(?:with|without)[_-]skills?'+right
    rules=[('host_source_path',r'/Users/[^\s`\"\'<>，。；]+','[本地源路径已隐藏]'),
           ('temporary_host_path',r'/var/folders/[^\s`\"\'<>，。；]+','[临时源路径已隐藏]'),
           ('instruction_source_path',r'/workspace/\.codex/skills/[^\s`\"\'<>，。；]+','[控制资料来源]'),
           # Arm names must be removed before their "skill" component; otherwise
           # a hyphenated label leaves an identifying with-/without- prefix.
           ('arm_identity',r'(?i)(?:'+left+r'arm'+right+r'|实验臂|版本臂)\s*[:=]\s*(?:before|current|candidate|(?:with|without)[_-]skills?)'+right+r'|'+arm,'[实验标识已隐藏]'),
           ('instruction_identity',r'(?i)'+instruction+r'|技能','[控制规则]'),
           ('model_identity',r'(?i)'+model,'[模型标识已隐藏]')]
    changes=[];out=text
    for name,pattern,replacement in rules:
        matches=list(re.finditer(pattern,out))
        if matches:
            changes.append({'rule':name,'input_sha256':digest(out),'matches':[{'start':m.start(),'end':m.end(),'original':m.group()} for m in matches],'replacement':replacement})
            out=re.sub(pattern,replacement,out)
    require(not re.search(r'(?i)'+instruction+'|'+model+'|'+arm+r'|/Users/|/var/folders/',out),'脱敏后仍有来源身份')
    return out,changes

def collect_sources(stage2,main_with,main_without,recovered,receipt):
    manifest=load(stage2/'manifest.json');require(manifest.get('completed_utc') and manifest.get('request_outcome_coverage_valid'),'第二批尚未完成')
    rows=load(stage2/'trial-results.json');require(len(rows)==8,'第二批结果不完整')
    samples=[]
    for row in rows[:4]:
        require(row['case_id']=='batch-goal','第二批前4不是Batch')
        g=stage2/'trials'/row['trial_id']/'G';native=result(g)
        p=next((g/'reports').glob('iteration-*/result.json'));workspace=p.parent/row['trial_id']/'with_skill/outputs/workspace'
        j=stage2/'trials'/row['trial_id']/row.get('judge_phase','J')
        samples.append({'cohort':'stage2','source_trial':row['trial_id'],'arm':row['arm'],'response':native['response'],
            'old_status':result(j)['status'],'old_grading':result(j)['grading'],'workspace':workspace,
            'source_files':[p,next((j/'reports').glob('iteration-*/result.json')),g/'seal.json'],
            'extra_business_files':[]})
    for cohort,root,configuration in [('main-with',main_with,'with_skill'),('main-without',main_without,'without_skill')]:
        native,phase,p=phase_for_case(root,configuration)
        samples.append({'cohort':cohort,'source_trial':'batch-goal','arm':configuration,'response':native['response'],
            'old_status':native['status'],'old_grading':native['grading'],'workspace':phase/'outputs/workspace',
            'source_files':[p],'extra_business_files':[]})
    recovery=load(receipt);require(sha(recovered)==recovery['output_sha256'] and recovered.stat().st_size==recovery['bytes'],'恢复产物SHA/长度不同')
    raw=Path(recovery['source_rollout']);require(sha(raw)==recovery['source_rollout_sha256'],'恢复来源rollout变化')
    event=json.loads(raw.read_text().splitlines()[recovery['source_line']-1]);require(event==recovery['event'],'恢复receipt与原生事件不同')
    item=event['payload']['item'];require(item['type']=='FileChange' and item['status']=='completed' and recovery['later_tool_or_mutation_events']==0,'恢复事件不是最后成功写入')
    content=item['changes']['/workspace/migration-blocked-evidence.md']['content']
    require(content.encode()==recovered.read_bytes(),'恢复内容不是精确native literal')
    samples[-1]['extra_business_files']=[('migration-blocked-evidence.md',recovered)]
    samples[-1]['source_files'] += [receipt,recovered,raw]
    return samples

def mock_judge(criteria,candidate,snapshot,files):
    grade={'results':[{'criterion_id':f'criterion-{i+1}','passed':False,'evidence':['mock protocol only'],'failures':['no quality claim']} for i in range(len(criteria))]}
    code="""import hashlib,json,sys
from pathlib import Path
text='\\n'.join(m['content'] for m in json.loads(sys.argv[1]))
candidate=CANDIDATE
snapshot=SNAPSHOT
assert candidate in text,'final missing/truncated'
assert snapshot in text,'business snapshot not fully inline'
assert not Path('/workspace/.codex/skills/goal-prompt').exists(),'Skill reached J'
assert not list(Path('/root/.codex/skills').rglob('SKILL.md')),'home Skill reached J'
assert '/Users/zhu/' not in text.replace(candidate,''),'host source identity reached J'
paths=sorted(Path('/workspace/.skill-up/judge/context/attachments').glob('*.md'))
assert sorted(hashlib.sha256(p.read_bytes()).hexdigest() for p in paths)==FILE_HASHES,'runtime business files differ'
print(json.dumps({'final_message':GRADE,'exit_code':0}))
"""
    return code.replace('FILE_HASHES',repr(sorted(digest(t) for _,t in files))).replace('SNAPSHOT',repr(snapshot)).replace('CANDIDATE',repr(candidate)).replace('GRADE',repr(json.dumps(grade,ensure_ascii=False)))

def prepare_j(h,phase,trial,case,candidate,snapshot,files,iso,defaults,retry,frozen,mock=False):
    _,cfg=h.phase_base(phase,iso,defaults,retry,frozen)
    payload={'final_message':candidate,'exit_code':0,'artifacts':{'workspace_diff':snapshot}}
    cfg['engine']={'name':'frozen-business-artifact-replay','custom':{'transport':'local','response_format':'session_result',
        'local':{'command':'python3','args':['-c','import json;print(json.dumps('+repr(payload)+'))']}}}
    scoring=copy.deepcopy(case);scoring['id']=trial;scoring['title']='冻结业务产物判分'
    scoring['judge']['engine']=copy.deepcopy(h.ENGINE);scoring['judge'].pop('model',None)
    scoring['judge']['context']=copy.deepcopy(CONTEXT);scoring['judge']['skills']=[]
    attachments=[]
    for index,(relative,text) in enumerate(files,1):
        name=f'business-file-{index:02d}.md';destination=phase/'snapshot/evals/business-files'/name
        destination.parent.mkdir(parents=True,exist_ok=True);destination.write_text(text)
        attachments.append({'path':'evals/business-files/'+name,'label':f'business_file_{index:02d}'})
    if attachments:scoring['judge']['context']['attachments']=attachments
    if mock:
        scoring['judge']['engine']={'name':'mock-state-aware-judge','model':copy.deepcopy(h.ENGINE['model']),'custom':{'transport':'local','response_format':'session_result',
            'local':{'command':'python3','args':['-c',mock_judge(case['judge']['criteria'],candidate,snapshot,files),'${messages_json}']}}}
    h.save_config(phase,cfg,scoring)
    dump(phase/'phase-role.json',{'role':'state-aware-frozen-output-rejudge','student_model_calls':0,'mock':mock,
        'candidate_sha256':digest(candidate),'business_snapshot_sha256':digest(snapshot),'business_file_sha256':[digest(t) for _,t in files],
        'context_version':'batch-business-state-v1','snapshot_is_original_vcs_diff':False})

def audit_j(h,phase,sample,mock=False):
    native=result(phase);candidate=(sample/'candidate.txt').read_text();snapshot=(sample/'business-snapshot.patch').read_text()
    require(native['response']==candidate,'重判改写了原final')
    rollouts=h.judge_rollouts(phase);gated=h.expect_gate_failed(native)
    if gated:
        criteria=[a for a in native['grading']['assertion_results'] if not a['text'].startswith('expect.')]
        require(native['status']=='FAIL' and criteria and not rollouts and not native['grading'].get('judge_context'),'原生expect短路错误')
        require(all(a.get('skipped') and a.get('evidence')=='not evaluated: expect gate failed' for a in criteria),'短路并非原生SKIP')
    elif native['status'] in ('PASS','FAIL'):
        context=native['grading']['judge_context'];materials={m['key']:m for m in context['manifest']['materials']}
        require(context['profile']=='minimal' and materials['final_message']['mode']=='include' and materials['workspace_diff']['mode']=='include','直接必要材料被降级')
        require(not materials['workspace_diff'].get('truncated') and materials['workspace_diff']['original_bytes']==len(snapshot.encode()),'业务快照被截断')
        require(all(materials[k]['mode']=='omit' for k in ('transcript','generated_files')),'J收到原工具轨迹/其他文件')
        final=list((phase/'reports').rglob('context/final_message.txt'));diff=list((phase/'reports').rglob('context/workspace.diff'))
        require(final and diff and all(p.read_text()==candidate for p in final) and all(p.read_text()==snapshot for p in diff),'SDK材料不保真')
        if not mock:
            texts=[]
            for path in rollouts:
                for line in path.read_text().splitlines():
                    event=json.loads(line);p=event.get('payload',{})
                    if event.get('type')=='response_item' and p.get('role')=='user':texts.append('\n'.join(b.get('text','') for b in p.get('content',[]) if isinstance(b,dict)))
            require(any(snapshot in t and candidate in t for t in texts),'实际Judge未收到完整inline快照和原final')
    # Raw ERROR is retained and never converted to a quality verdict.
    dump(phase/'state-aware-audit.json',{'valid':True,'raw_status':native['status'],'student_model_calls':0,
        'expect_gate_failed':gated,'judge_model_sessions':len(rollouts),'candidate_sha256':digest(candidate),
        'business_snapshot_sha256':digest(snapshot),'direct_inline_material_verified':not gated and native['status'] in ('PASS','FAIL'),
        'mock_no_quality_claim':mock,'attachment_availability_is_not_reading_proof':True})
    return native,len(rollouts)

def prepare(root,args):
    require(not root.exists(),'拒绝覆盖重判证据')
    require(sha(STABLE_HELPER)==STABLE_HELPER_SHA,'稳定harness源码变化')
    h=helper(STABLE_HELPER);stage2=args.stage2.resolve();main_with=args.main_with.resolve();main_without=args.main_without.resolve()
    samples=collect_sources(stage2,main_with,main_without,args.recovered_without.resolve(),args.recovery_receipt.resolve())
    root.mkdir(parents=True,mode=0o700);shutil.copy2(STABLE_HELPER,root/'frozen-harness.py');shutil.copy2(Path(__file__),root/'rejudge-business-state.py')
    shutil.copytree(stage2/'dependencies',root/'dependencies');frozen=root/'dependencies';h.assert_frozen(frozen)
    for name in ('audit-baseline-requests.py','audit-request-outcomes.py'):shutil.copy2(frozen/'scripts'/name,root/name)
    iso=load(stage2/'isolation-base.json');iso['docker_binary']=shutil.which('docker');dump(root/'isolation.json',iso)
    original=load(stage2/'manifest.json');case=yaml.safe_load((frozen/'cases/batch-goal.yaml').read_text())
    require(sha(frozen/'cases/batch-goal.yaml')==load(main_with/'manifest.json')['original_case_sha256']['batch-goal'],'原Batch rubric/input不一致')
    mapping=[];source_hashes={};source_hashes[str(stage2/'manifest.json')]=sha(stage2/'manifest.json')
    for source in samples:
        trial='s'+uuid.uuid4().hex[:16];sample=root/'samples'/trial;sample.mkdir(parents=True)
        candidate=source['response'];(sample/'candidate.txt').write_text(candidate)
        files=[];raw_files=[];redactions=[]
        workspace=source['workspace']
        if workspace.exists():
            raw_files=[(str(p.relative_to(workspace)),p) for p in sorted((workspace/'.goal-task').rglob('*.md')) if p.is_file()]
        raw_files+=source['extra_business_files']
        for index,(relative,path) in enumerate(raw_files,1):
            require(not path.is_symlink() and not relative.startswith(('.codex/','../')),'非法业务产物路径')
            raw=path.read_text();projected,changes=redact(raw)
            destination=sample/'raw-business'/relative;destination.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,destination)
            target=sample/'projected-business'/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(projected)
            (sample/f'redaction-{index}.diff').write_text(''.join(difflib.unified_diff(raw.splitlines(True),projected.splitlines(True),fromfile='raw-business/'+relative,tofile='projected-business/'+relative)))
            redactions.append({'relative_path':relative,'source_sha256':sha(path),'projected_sha256':digest(projected),'changes':changes})
            source_hashes[str(path.resolve())]=sha(path);files.append((relative,projected))
        refs=set(re.findall(r'\.goal-task/[\w./-]+\.md',candidate));missing=sorted(refs-{relative for relative,_ in files})
        snapshot=HEADER+'业务文件数：'+str(len(files))+'\n'
        for relative,text in files:
            snapshot+='\n'+''.join(difflib.unified_diff([],text.splitlines(True),fromfile='/dev/null',tofile=relative))
        require(len(snapshot.encode())<=MAX_BYTES and len(candidate.encode())<=MAX_BYTES,'必要材料超过64KiB，禁止静默降级')
        (sample/'business-snapshot.patch').write_text(snapshot);dump(sample/'redactions.json',redactions)
        for path in source['source_files']:source_hashes[str(path.resolve())]=sha(path)
        dump(sample/'original-grading.json',source['old_grading'])
        old_gated=h.expect_gate_failed({'grading':source['old_grading']})
        material_status='expect_only' if missing and old_gated else ('UNSCORABLE' if missing else 'ready')
        row={'trial_id':trial,'cohort':source['cohort'],'source_trial':source['source_trial'],'arm':source['arm'],
             'original_status':source['old_status'],'candidate_sha256':digest(candidate),'business_snapshot_sha256':digest(snapshot),
             'business_files':[r for r in redactions],'missing_referenced_artifacts':missing,'material_status':material_status,
             'material_complete_for_business_criteria':not missing,
             'expect_only_limit':'Original expect already fails; unavailable business material is not scored or fabricated; semantic criteria remain native SKIP.' if material_status=='expect_only' else None}
        mapping.append(row)
        if material_status!='UNSCORABLE':
            phase=root/'trials'/trial/'J'
            prepare_j(h,phase,trial,case,candidate,snapshot,files,iso,original['defaults'],original['retry'],frozen)
            h.run_cli(frozen/'skill-up',phase,validate_only=True)
    dump(root/'source-mapping-host-only.json',mapping)
    manifest={'context_version':'batch-business-state-v1','student_model_executions':0,'judge_model_executions':0,'models_started':False,
        'sample_count':6,'case_id':'batch-goal','model':h.MODEL,'effort':'xhigh','judge_model':h.MODEL,'judge_effort':'xhigh',
        'original_case_sha256':sha(frozen/'cases/batch-goal.yaml'),'source_sha256':sha(root/'rejudge-business-state.py'),
        'helper_sha256':sha(root/'frozen-harness.py'),'dependencies_sha256_manifest':sha(frozen/'sha256.json'),
        'source_files_sha256':source_hashes,'mapping_sha256':sha(root/'source-mapping-host-only.json'),
        'original_final_and_grades_preserved':True,'no_student_or_old_judge_rerun':True,
        'representation':'rebuilt captured business-file snapshots, explicitly not original VCS diff or action trace',
        'limits':'New Judge context, not Skill improvement. Natural main cohorts and explicit version-pair cohort stay separate. Style may reveal version; no absolute blinding claim.'}
    manifest['prepared_files_sha256']={str(p.relative_to(root)):sha(p) for p in root.rglob('*') if p.is_file()}
    dump(root/'manifest.json',manifest)
    return h,manifest,mapping,original,iso,case

def smoke(root,h,manifest,mapping,original,iso,case):
    h.snapshot_broker(root,iso,start=True);rows=[];frozen=root/'dependencies'
    for row in mapping:
        if row['material_status']=='UNSCORABLE':continue
        trial=row['trial_id'];sample=root/'samples'/trial;candidate=(sample/'candidate.txt').read_text();snapshot=(sample/'business-snapshot.patch').read_text()
        files=[(r['relative_path'],(sample/'projected-business'/r['relative_path']).read_text()) for r in row['business_files']]
        phase=root/'zero-model'/trial/'J';prepare_j(h,phase,trial,case,candidate,snapshot,files,iso,original['defaults'],original['retry'],frozen,mock=True)
        h.run_cli(frozen/'skill-up',phase,validate_only=True);native=h.run_cli(frozen/'skill-up',phase);audit_j(h,phase,sample,mock=True)
        require(load(next((phase/'reports').glob('iteration-*/result.json')))['overall_tokens']==0,'零模型产生tokens')
        rows.append({'trial_id':trial,'protocol_passed':True,'mock_status_not_quality':native['status'],'expect_gate_failed':h.expect_gate_failed(native),'model_calls':0})
    h.snapshot_broker(root,iso);require(not any(e.get('event')=='accepted' for e in map(json.loads,(root/'broker-events.jsonl').read_text().splitlines())),'零模型期间出现真实API请求')
    dump(root/'zero-model-validation.json',{'passed':True,'student_calls':0,'judge_model_calls':0,'quality_claim':False,'rows':rows,'broker_events_delta_sha256':sha(root/'broker-events.jsonl')})
    manifest['zero_model_protocol_passed']=True;dump(root/'manifest.json',manifest)
    # These are zero-window evidence; actual replay preserves them and starts
    # a new suffix without overwriting any prior audit/log.
    for name in ('broker-events-before.jsonl','broker-events.jsonl'):shutil.move(root/name,root/('zero-model-'+name))

def dispatch(root):
    manifest=load(root/'manifest.json');require(not manifest['models_started'] and manifest.get('zero_model_protocol_passed'),'须先完成零模型验证且禁止重复派发')
    for relative,expected in manifest['prepared_files_sha256'].items():require(sha(root/relative)==expected,'准备材料变化: '+relative)
    for path,expected in manifest['source_files_sha256'].items():require(sha(Path(path))==expected,'原始证据变化: '+path)
    h=helper(root/'frozen-harness.py');h.assert_frozen(root/'dependencies');iso=load(root/'isolation.json')
    mapping=load(root/'source-mapping-host-only.json');require(sha(root/'source-mapping-host-only.json')==manifest['mapping_sha256'],'样本映射变化')
    manifest['models_started']=True;dump(root/'manifest.json',manifest);h.snapshot_broker(root,iso,start=True);rows=[]
    for row in mapping:
        if row['material_status']=='UNSCORABLE':rows.append({**row,'status':'UNSCORABLE_MISSING_ARTIFACT','judge_model_sessions':0});continue
        trial=row['trial_id'];phase=root/'trials'/trial/'J';require(not (phase/'run.log').exists(),'拒绝重复J')
        native=h.run_cli(root/'dependencies/skill-up',phase);native,count=audit_j(h,phase,root/'samples'/trial)
        manifest['judge_model_executions']+=count
        rows.append({**row,'status':native['status'],'judge_model_sessions':count,'expect_gate_failed':h.expect_gate_failed(native)})
        dump(root/'rejudged-results.json',rows);dump(root/'manifest.json',manifest)
    manifest['cases_finished_utc']=__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat();dump(root/'manifest.json',manifest)
    h.snapshot_broker(root,iso);h.final_request_audits(root,manifest)
    manifest['completed_utc']=manifest['cases_finished_utc'];dump(root/'manifest.json',manifest)
    print('state-aware新上下文重判已终止；新student调用0，原context和原成绩保留')

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--stage2',type=Path,default=REPO/'.eval-work/luna-failed-pairs-stage2-v1-20261030')
    parser.add_argument('--main-with',type=Path,default=REPO/'.eval-work/luna-with-skill-v2-20261030')
    parser.add_argument('--main-without',type=Path,default=REPO/'.eval-work/luna-xhigh-control-v4-20261030')
    parser.add_argument('--recovered-without',type=Path,default=REPO/'.goal-task/luna-with-skill/state-evidence-recovery/main-without-migration-blocked-evidence.md')
    parser.add_argument('--recovery-receipt',type=Path,default=REPO/'.goal-task/luna-with-skill/state-evidence-recovery/recovery.json')
    mode=parser.add_mutually_exclusive_group(required=True);mode.add_argument('--prepare-only',action='store_true');mode.add_argument('--zero-model-smoke',action='store_true');mode.add_argument('--dispatch',action='store_true')
    args=parser.parse_args();root=args.output.resolve()
    if args.dispatch:dispatch(root);return
    h,manifest,mapping,original,iso,case=prepare(root,args)
    if args.zero_model_smoke:smoke(root,h,manifest,mapping,original,iso,case)
    print('6份冻结原final/state材料准备完成，无新student；未派真实Judge')

if __name__=='__main__':main()
