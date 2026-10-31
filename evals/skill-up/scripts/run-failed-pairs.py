#!/usr/bin/env python3
"""Luna失败样本的冻结两阶段版本对照；prepare/mock不调用模型，真实派发须主30例完成。"""
from pathlib import Path
from collections import Counter
import argparse
import copy
import datetime as dt
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import uuid
import yaml

REPO=Path(__file__).resolve().parents[3]
MODEL='gpt-6-luna'
BEFORE=REPO/'.eval-work/controlled-before-v2/snapshot/target/goal-prompt'
PREFIX_SOURCE=REPO/'.eval-work/controlled-before-v2/manifest.json'
PROTOCOL=REPO/'.goal-task/luna-with-skill/failed-comparison-protocol.md'
CASES=('stage1-long-running',)
# Only these single-turn, output-only rubrics have been checked for final-only
# scoring. Expanding to process/multi-turn cases requires another evidence path.
ENVIRONMENT_CASES=('research-goal','no-fabrication')
FINAL_ONLY_CASES=('stage1-long-running','batch-goal','preauthorized-permissions',*ENVIRONMENT_CASES)
INITIAL_ENVIRONMENT_FACTS={'observation_phase':'initial_task_environment','provided_project_material_files':0,
    'provided_repository_source_files':0,'provided_test_material_files':0,
    'project_test_commands_verified':False,'business_implementation_behavior_verified':False}
INITIAL_ENVIRONMENT_HEADER='初始环境事实数据（非VCS diff，非业务实现调查结果）。\n'
MINIMAL={'profile':'minimal','final_message':'include','transcript':'omit','workspace_diff':'omit','generated_files':'omit'}
ENGINE={'name':'codex','version':'0.164.0','model':{'provider':'openai','name':MODEL}}

def require(condition,message):
    if not condition:raise RuntimeError(message)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def load(path):return json.loads(path.read_text())
def dump(path,value):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def safe(root,relative):
    p=(root/relative).resolve();require(p.is_relative_to(root),'路径越界');return p

def child_env(phase):
    env=os.environ.copy()
    for key in ('SKILL_UP_WITHOUT_SKILL_ONLY','CODEX_THREAD_ID','CODEX_INTERNAL_ORIGINATOR_OVERRIDE'):env.pop(key,None)
    env['PATH']=str(phase/'bin')+os.pathsep+env['PATH'];env['LUNA_CONTROL_DIR']=str(phase)
    return env

def assert_frozen(frozen):
    for relative,expected in load(frozen/'sha256.json').items():
        require(sha(safe(frozen,relative))==expected,'实验冻结依赖已变化: '+relative)

def phase_base(root,iso,defaults,retry,frozen):
    assert_frozen(frozen)
    root.mkdir(parents=True);(root/'bin').mkdir();(root/'snapshot/evals').mkdir(parents=True)
    shutil.copy2(frozen/'scripts/baseline-docker.py',root/'bin/docker');(root/'bin/docker').chmod(0o755)
    (root/'empty-user.yaml').write_text('{}\n')
    spec=copy.deepcopy(iso);spec['docker_binary']=shutil.which('docker');spec.pop('target_skill',None)
    for key in ('skill_bundle_sha256','skill_runtime_sha256','with_skill_method'):spec.pop(key,None)
    dump(root/'isolation.json',spec)
    config={'schema_version':'v1alpha1','environment':{'type':'docker','image':spec['image_id']},'skills':[],
            'engine':copy.deepcopy(ENGINE),'cases':{'files':['evals/case.yaml'],'parallelism':1,'defaults':copy.deepcopy(defaults),'retry_policy':copy.deepcopy(retry)},
            'benchmark':{'enabled':False},'report':{'formats':['json','html'],'artifacts':['transcript']}}
    return spec,config

def save_config(root,config,case):
    (root/'snapshot/evals/case.yaml').write_text(yaml.safe_dump(case,allow_unicode=True,sort_keys=False))
    (root/'snapshot/evals/eval.yaml').write_text(yaml.safe_dump(config,allow_unicode=True,sort_keys=False))

def prepare_generation(phase,trial,arm_dir,bundle,case,prefix,iso,defaults,retry,frozen,mock=False):
    spec,config=phase_base(phase,iso,defaults,retry,frozen)
    target=phase/'snapshot/target/goal-prompt';target.mkdir(parents=True)
    for relative in bundle:
        source=safe(arm_dir,relative);require(sha(source)==bundle[relative],'冻结实验臂已变化: '+relative)
        destination=target/relative;destination.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,destination)
    runtime={p:h for p,h in bundle.items() if not p.startswith('evals/')}
    require(len(bundle)==9 and len(runtime)==7,'源9文件/运行7文件不符')
    spec['target_skill']={'path':'/workspace/.codex/skills/goal-prompt','files':runtime};dump(phase/'isolation.json',spec)
    capture=phase/'snapshot/evals/capture-only.sh'
    capture.write_text('#!/usr/bin/env bash\nset -euo pipefail\n[ -n "${EVAL_FINAL_MESSAGE//[[:space:]]/}" ] || { echo "no captured final response" >&2; exit 1; }\nprintf "capture-only: not a quality verdict\\n"\n')
    generation={'id':trial,'title':'冻结输出采集','description':'状态仅表示采集成功，不是完整case判分。',
                'input':{'prompt':prefix+case['input']['prompt']},'expect':{'exit_code':0},
                'judge':{'type':'script','script_path':'evals/capture-only.sh'}}
    config['skills']=[{'source':'local_path','path':'target/goal-prompt'}]
    if mock:
        config['skills'][0]['target']='.codex/skills/goal-prompt'
        response={
            'batch-goal':'/goal 按 migration-list.yaml 固定8模块完成迁移；各项运行 validate-module，最后运行 validate-all。',
            'preauthorized-permissions':'/goal 完成账户导入功能。',
        }.get(case['id'],'待确认简报：范围是迁移实现、测试和CI；以兼容测试、CI和独立审查为完成证据。慢CI与暂时故障先有限重试或重排，全部剩余工作共同受阻才整体停止。请确认范围与完成证据。')
        code="from pathlib import Path;import json;assert Path('/workspace/.codex/skills/goal-prompt/SKILL.md').is_file();Path('/workspace/generation-only.txt').write_text('GENERATION_ONLY_TRACE_SENTINEL STUDENT_VERSION_SECRET ARM_SECRET_AAA');print(json.dumps({'final_message':"+repr(response)+",'exit_code':0}))"
        config['engine']={'name':'mock-capture','custom':{'transport':'local','response_format':'session_result','local':{'command':'python3','args':['-c',code]}}}
    save_config(phase,config,generation)
    dump(phase/'manifest.json',{'role':'student_generation_capture_only','configuration':'with_skill','skill_sha256':bundle,'skill_runtime_sha256':runtime,
         'skill_snapshot':'snapshot/target/goal-prompt','capture_pass_is_not_quality_pass':True,'mock_zero_model':mock})
    return config

def mock_judge_code(criteria,candidate,environment_sha256=None,environment_inline=None):
    grade={'results':[{'criterion_id':f'criterion-{i+1}','passed':False,'evidence':['mock protocol only; no scoring-quality claim'],'failures':['intentional mock verdict']} for i in range(len(criteria))]}
    # The mock sees the exact SDK-built Judge prompt and the fresh container.
    return """from pathlib import Path
import json,sys
messages=json.loads(sys.argv[1]);text='\\n'.join(m['content'] for m in messages)
candidate=CANDIDATE
if candidate not in text:raise RuntimeError('final output missing/truncated')
rest=text.replace(candidate,'')
for marker in ('GENERATION_ONLY_TRACE_SENTINEL','STUDENT_VERSION_SECRET','ARM_SECRET_AAA','$goal-prompt'):
 if marker in rest:raise RuntimeError('generation identity/trace leaked to Judge')
if Path('/workspace/generation-only.txt').exists() or Path('/workspace/.codex/skills/goal-prompt').exists():raise RuntimeError('G filesystem reached J')
if list(Path('/root/.codex/skills').rglob('SKILL.md')):raise RuntimeError('home Skill reached J')
environment_sha=ENVIRONMENT_SHA
environment_inline=ENVIRONMENT_INLINE
if environment_sha is not None:
 import hashlib
 material=Path('/workspace/.skill-up/judge/context/attachments/01-initial-environment.json')
 if hashlib.sha256(material.read_bytes()).hexdigest()!=environment_sha:raise RuntimeError('runtime environment attachment bytes changed')
 if environment_inline not in text:raise RuntimeError('initial environment facts not fully inline in Judge prompt')
print(json.dumps({'final_message':GRADE,'exit_code':0}))
""".replace('CANDIDATE',repr(candidate)).replace('ENVIRONMENT_SHA',repr(environment_sha256)).replace('ENVIRONMENT_INLINE',repr(environment_inline)).replace('GRADE',repr(json.dumps(grade,ensure_ascii=False)))

def prepare_scoring(phase,trial,case,candidate,iso,defaults,retry,frozen,mock=False):
    spec,config=phase_base(phase,iso,defaults,retry,frozen)
    code="import json;print(json.dumps({'final_message':"+repr(candidate)+",'exit_code':0}))"
    config['engine']={'name':'frozen-output-replay','custom':{'transport':'local','response_format':'session_result','local':{'command':'python3','args':['-c',code]}}}
    scoring=copy.deepcopy(case);scoring['id']=trial;scoring['title']='冻结候选评分'
    if case['judge']['type']=='agent_judge':
        scoring['judge']['engine']=copy.deepcopy(ENGINE);scoring['judge'].pop('model',None);scoring['judge']['context']=copy.deepcopy(MINIMAL);scoring['judge']['skills']=[]
        if case['id'] in ENVIRONMENT_CASES:
            facts=frozen/'environment/initial-environment.json'
            require(load(facts)==INITIAL_ENVIRONMENT_FACTS,'缺少可信共同初始环境事实')
            shutil.copy2(facts,phase/'snapshot/evals/initial-environment.json')
            inline=INITIAL_ENVIRONMENT_HEADER+facts.read_text()
            require(len(inline.encode())<=65536 and len(candidate.encode())<=65536,'初始事实或候选超过64KiB')
            code="import json;print(json.dumps({'final_message':"+repr(candidate)+",'exit_code':0,'artifacts':{'workspace_diff':"+repr(inline)+"}}))"
            config['engine']['custom']['local']['args']=['-c',code]
            scoring['judge']['context']['workspace_diff']='include';scoring['judge']['context']['limits']={'max_bytes':65536}
            scoring['judge']['context']['attachments']=[{'path':'evals/initial-environment.json','label':'initial_environment'}]
        if mock:
            scoring['judge']['engine']={'name':'mock-final-only-judge','model':{'provider':'openai','name':MODEL},'custom':{'transport':'local','response_format':'session_result',
               'local':{'command':'python3','args':['-c',mock_judge_code(case['judge']['criteria'],candidate,sha(facts) if case['id'] in ENVIRONMENT_CASES else None,inline if case['id'] in ENVIRONMENT_CASES else None),'${messages_json}']}}}
            scoring['judge'].pop('model',None)
    else:
        source=safe(frozen/'evals',case['judge']['script_path']);destination=safe(phase/'snapshot',case['judge']['script_path'])
        destination.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,destination)
    save_config(phase,config,scoring)
    dump(phase/'candidate-envelope.json',{'sha256':hashlib.sha256(candidate.encode()).hexdigest(),'bytes':len(candidate.encode()),'data':candidate})
    metadata={'role':'score_only_frozen_replay','native_configuration_label':'with_skill','skills':[],
        'student_model_calls':0,'mock_zero_model':mock,'candidate_sha256':hashlib.sha256(candidate.encode()).hexdigest(),
        'candidate_is_unmodified_final_message':True,'source_identity_not_uploaded':True,'absolute_blinding_claim':False}
    if case['judge']['type']=='script':
        metadata['script_judge_source_sha256']=sha(source);metadata['script_judge_path']=case['judge']['script_path']
    if case['id'] in ENVIRONMENT_CASES:metadata['initial_environment_sha256']=sha(frozen/'environment/initial-environment.json')
    dump(phase/'manifest.json',metadata)
    return config

def run_cli(binary,phase,validate_only=False):
    config=phase/'snapshot/evals/eval.yaml';env=child_env(phase)
    if validate_only:
        commands=[([str(binary),'--config',str(phase/'empty-user.yaml'),'validate',str(config)],'validate.log'),
                  ([str(binary),'--config',str(phase/'empty-user.yaml'),'run',str(config),'--dry-run'],'dry-run.log')]
    else:
        commands=[([str(binary),'--config',str(phase/'empty-user.yaml'),'run',str(config),'--output-dir',str(phase/'reports'),'--event-log',str(phase/'events.jsonl')],'run.log')]
    for command,name in commands:
        require(not (phase/name).exists(),'拒绝覆盖阶段证据')
        with (phase/name).open('w') as log:result=subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT)
        require(result.returncode in ((0,) if validate_only else (0,1)),'SDK基础设施调用失败')
    if validate_only:return None
    paths=list((phase/'reports').glob('iteration-*/result.json'));require(len(paths)==1,'阶段缺少唯一原始result')
    cases=load(paths[0])['case_results'];require(len(cases)==1,'阶段必须只有一个case');return cases[0]

def capture_seal(phase,result,require_real):
    valid=result['status']=='PASS' and bool(result.get('response','').strip())
    if not valid:return None
    response=result['response'];path=phase/'sealed-final-message.txt';path.write_text(response)
    rollouts=[{'path':str(p.relative_to(phase)),'sha256':sha(p),'bytes':p.stat().st_size} for p in phase.rglob('rollout-*.jsonl')]
    if require_real:require(rollouts,'真实student没有原生trace，不能封存为成功')
    seal={'final_message_sha256':hashlib.sha256(response.encode()).hexdigest(),'bytes':len(response.encode()),'source_result_status':'PASS',
          'meaning':'capture_only_not_quality_pass','raw_rollouts':rollouts,'model_trace_copied_to_J':False}
    dump(phase/'seal.json',seal);return response

def snapshot_broker(root,iso,start=False):
    raw=subprocess.check_output([iso['docker_binary'],'logs',iso['broker_container']],text=True)
    if start:(root/'broker-events-before.jsonl').write_text(raw);return
    prefix=(root/'broker-events-before.jsonl').read_text();require(raw.startswith(prefix),'broker日志前缀被重置，停止')
    (root/'broker-events.jsonl').write_text(raw[len(prefix):])

def audit_generation(root,phase,trial):
    helper_path=root/'frozen-run-baseline.py';spec=importlib.util.spec_from_file_location('experiment_baseline',helper_path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.audit(phase,phase/'reports',configuration='with_skill')
    audit=load(phase/'reports/isolation-audit.json')
    require(audit['skill_coverage'][trial]['actual_full_load_observed'],'显式调用未完整加载Skill，不能判为有效student样本')

def judge_rollouts(phase):
    return sorted(p for p in (phase/'reports').rglob('rollout-*.jsonl') if '/outputs/judge/' in str(p))

def expect_gate_failed(result):
    return any(a.get('text','').startswith('expect.') and a.get('passed') is False and not a.get('skipped')
               for a in result.get('grading',{}).get('assertion_results',[]))

def native_process_event(event):
    """Project native execution/write events without judging their effects."""
    payload=event.get('payload',{});item=payload.get('item',{}) if isinstance(payload,dict) else {}
    if event.get('type')!='event_msg' or not isinstance(item,dict):return None,[]
    kind=item.get('type')
    if kind not in ('CommandExecution','FileChange'):return None,[]
    output_hashes={key:hashlib.sha256(item[key].encode()).hexdigest() for key in ('aggregated_output','stdout','stderr') if isinstance(item.get(key),str)}
    common={'event_type':payload.get('type'),'item_id':item.get('id'),'status':item.get('status'),
            'timestamp':event.get('timestamp'),'output_fields_sha256':output_hashes}
    if kind=='CommandExecution':
        return {**common,'command':item.get('command'),'cwd':item.get('cwd'),'exit_code':item.get('exit_code'),
                'output_sha256':output_hashes.get('aggregated_output')},[]
    changes=item.get('changes',{});rows=[]
    if not isinstance(changes,dict):
        return None,[{**common,'parse_status':'unsupported_changes_shape','raw_item_sha256':hashlib.sha256(json.dumps(item,ensure_ascii=False,sort_keys=True).encode()).hexdigest()}]
    for path,change in changes.items():
        value=change if isinstance(change,dict) else {}
        content=value.get('content')
        rows.append({**common,'file_path':path,'change_type':value.get('type'),'move_path':value.get('move_path'),
                     'content_present':isinstance(content,str),'content_sha256':hashlib.sha256(content.encode()).hexdigest() if isinstance(content,str) else None,
                     'parse_status':'parsed' if isinstance(change,dict) else 'unsupported_change_shape'})
    return None,rows

def audit_student_process(phase,case_id):
    """Separate process evidence from brief scoring; never infer no writes."""
    calls=[];artifacts=[];commands=[];file_changes=[]
    for path in sorted((phase/'reports').rglob('rollout-*.jsonl')):
        artifacts.append({'path':str(path.relative_to(phase)),'sha256':sha(path)})
        for number,line in enumerate(path.read_text().splitlines(),1):
            event=json.loads(line);item=event.get('payload',{})
            if event.get('type')=='response_item' and item.get('type') in ('function_call','custom_tool_call'):
                calls.append({'tool':item.get('name'),'call_id':item.get('call_id'),
                              'arguments':item.get('arguments',item.get('input',''))})
            command,changes=native_process_event(event)
            location={'rollout':str(path.relative_to(phase)),'line':number,'ordinal':event.get('ordinal')}
            if command is not None:commands.append({**location,**command})
            file_changes.extend({**location,**change} for change in changes)
    require(artifacts,'过程审计缺真实G trace')
    dump(phase/'student-process-audit.json',{'case_id':case_id,'source_rollouts':artifacts,'tool_calls':calls,
        'native_command_events':commands,'native_file_change_events':file_changes,
        'review_status':'requires_independent_command_and_write_review','readonly_verified':False,
        'business_investigation_completed':False,
        'limits':'Host-only process evidence, never sent to Judge. Native content/output SHA identifies event text, not a reconstructed final filesystem. Status includes failed/pending attempts; absence of observed writes is not proof of no filesystem effects. Independent review required.'})

def audit_scoring(phase,case,candidate,mock=False,audit_output=None):
    data=load(next((phase/'reports').glob('iteration-*/result.json')));result=data['case_results'][0]
    require(result.get('response')==candidate,'replay改变了final_message')
    gated=expect_gate_failed(result);rollouts=judge_rollouts(phase)
    if case['judge']['type']=='script':
        metadata=load(phase/'manifest.json');source=phase/'snapshot'/case['judge']['script_path']
        require(sha(source)==metadata['script_judge_source_sha256'],'冻结script Judge发生变化')
    if gated:
        assertions=result['grading']['assertion_results'];criteria=[a for a in assertions if not a.get('text','').startswith('expect.')]
        require(result['status']==result['grading']['status']=='FAIL','expect失败却未保留质量FAIL')
        require(criteria and all(a.get('skipped') is True and a.get('passed') is False
                and a.get('evidence')=='not evaluated: expect gate failed' for a in criteria),'Judge跳过证据不完整')
        require(not result['grading'].get('judge_context') and not rollouts,'expect短路仍出现Judge context/模型trace')
    elif case['judge']['type']=='agent_judge':
        context=result.get('grading',{}).get('judge_context',{})
        require(context.get('profile')=='minimal','Judge不是minimal profile')
        materials={m['key']:m for m in context['manifest']['materials']}
        require(materials['final_message']['mode']=='include','候选被截断/改为引用')
        omitted=('transcript','generated_files') if case['id'] in ENVIRONMENT_CASES else ('transcript','workspace_diff','generated_files')
        for key in omitted:require(materials[key]['mode']=='omit','Judge收到未许可材料')
        final_files=list((phase/'reports').rglob('context/final_message.txt'));require(final_files and all(p.read_text()==candidate for p in final_files),'final材料字节不同')
        require(not list((phase/'reports').rglob('context/transcript.json')),'Judge导出了G/replay transcript')
    else:
        assertions=result.get('grading',{}).get('assertion_results',[])
        require(any(a.get('text','').startswith('script: ') and a['text'].endswith(source.name) and not a.get('skipped') for a in assertions),'script Judge未实际执行')
    for p in (phase/'reports').rglob('rollout-*.jsonl'):
        for line in p.read_text().splitlines():
            event=json.loads(line);payload=event.get('payload',{})
            if event.get('type')=='turn_context':require(payload.get('model')==MODEL and payload.get('effort')=='xhigh','Judge使用其他模型/深度')
            if event.get('type')=='response_item' and payload.get('role') in ('developer','user'):
                text='\n'.join(b.get('text','') for b in payload.get('content',[]) if isinstance(b,dict))
                require('<skills_instructions>' not in text and '<skill>' not in text,'Judge原生加载了Skill')
    environment=None
    if case['id'] in ENVIRONMENT_CASES and not gated:
        metadata=load(phase/'manifest.json');facts=phase/'snapshot/evals/initial-environment.json'
        attachments=[m for m in result['grading']['judge_context']['manifest']['materials'] if m['key']=='attachment']
        require(len(attachments)==1 and attachments[0]['label']=='initial_environment' and attachments[0]['mode']=='file_ref','共同附件配置不同')
        files=list((phase/'reports').rglob('context/attachments/01-initial-environment.json'))
        require(files and all(sha(p)==metadata['initial_environment_sha256']==sha(facts) for p in files),'SDK materialized环境附件不是冻结同字节')
        inline=INITIAL_ENVIRONMENT_HEADER+facts.read_text();material=materials['workspace_diff']
        require(material['mode']=='include' and not material.get('truncated') and material['original_bytes']==len(inline.encode()),'初始环境事实未完整inline')
        diffs=list((phase/'reports').rglob('context/workspace.diff'))
        require(diffs and all(p.read_text()==inline for p in diffs),'初始环境inline事实字节不同')
        if not mock:
            texts=[]
            for path in rollouts:
                for line in path.read_text().splitlines():
                    event=json.loads(line);value=event.get('payload',{})
                    if event.get('type')=='response_item' and value.get('role')=='user':texts.append('\n'.join(v.get('text','') for v in value.get('content',[]) if isinstance(v,dict)))
            require(any(inline in t and candidate in t for t in texts),'实际Judge输入缺完整初始事实或原final')
        observed=[];needle=facts.read_text().strip()
        for path in (phase/'reports').rglob('stdout.json'):
            if '/outputs/judge/' not in str(path):continue
            for line in path.read_text().splitlines():
                try:event=json.loads(line)
                except ValueError:continue
                item=event.get('item',{});command=item.get('command','')
                if event.get('type')=='item.completed' and item.get('exit_code')==0 and any(s in command for s in ('initial_environment','initial-environment','attachments')) and needle in item.get('aggregated_output',''):
                    observed.append(command)
        environment={'available':True,'facts_sha256':sha(facts),'actual_read_observed':bool(observed),
                     'read_commands':observed,'mock_runtime_attachment_read_verified':bool(mock),
                     'direct_inline_facts_verified':True,'inline_sha256':hashlib.sha256(inline.encode()).hexdigest(),
                     'limits':'Availability and observed reading are separate. No reading evidence is not silently treated as proof the Judge used environment facts.'}
    require(not (phase/'skill-install-audits').exists(),'Judge容器发生Skill安装')
    dump(audit_output or phase/'scoring-isolation-audit.json',{'valid':True,'fresh_replay_container':True,'skills':[],
        'final_message_sha256':hashlib.sha256(candidate.encode()).hexdigest(),'model_quality_verified_by_mock':False,
        'expect_gate_failed':gated,'judge_skipped_by_expect':gated,'judge_evaluation':'skipped_by_expect_gate' if gated else 'executed',
        'judge_model_sessions':len(rollouts),'judge_rollouts':[{'path':str(p.relative_to(phase)),'sha256':sha(p)} for p in rollouts],
        'initial_environment':environment,
        'limits':'不复制G source/home/stdout/arm；不保证从输出风格无法猜测版本。'})
    return result

def dispatch_ready(main_root,eligibility,selected):
    manifest=load(main_root/'manifest.json')
    require(manifest.get('completed_utc') and manifest.get('all_isolation_audits_pass'),'主30例未完成，禁止真实派发')
    native=load(main_root/'cases-combined.json');raw={c['case_id']:c for c in native}
    require(eligibility is not None,'真实派发前必须有失败分诊记录')
    decision=load(eligibility);require(decision.get('confirmed_true_failures') is True,'分诊尚未确认')
    require(decision.get('main_manifest_sha256')==sha(main_root/'manifest.json'),'分诊对应的主批次manifest已变化')
    require(decision.get('main_cases_sha256')==sha(main_root/'cases-combined.json'),'分诊对应的原始结果已变化')
    require(set(decision['cases'])==set(selected),'分诊集合不同于冻结case')
    for batch in ('pilot','remaining'):
        audit_name=manifest.get('isolation_audit_files',{}).get(batch,'isolation-audit.json')
        require(audit_name in ('isolation-audit.json','isolation-audit-reviewed.json'),'未知主批次审计文件')
        path=main_root/batch/audit_name;audit=load(path)
        require(audit['valid'] and not audit['findings'],'主批次隔离审计未通过')
        require(decision.get('isolation_audit_sha256',{}).get(batch)==sha(path),'分诊对应的隔离审计已变化')
    for cid in selected:
        row=decision['cases'][cid]
        require(raw[cid]['status']=='FAIL' and row.get('judge_or_collection_error') is False and bool(row.get('evidence')),'不是已确认真实FAIL: '+cid)
        require(row.get('response_sha256')==hashlib.sha256(raw[cid]['response'].encode()).hexdigest(),'分诊对应输出已变化: '+cid)

def completed_batch_ready(root,expected_cases):
    require(root is not None,'扩围前必须提供对应已完成批次')
    root=root.resolve();m=load(root/'manifest.json')
    count=4*len(expected_cases)
    require(m.get('completed_utc') and m.get('request_outcome_coverage_valid'),'前序批次尚未完成或请求outcome未闭环，禁止扩围')
    require(m['case_ids']==list(expected_cases) and m['trial_count']==count,'不是登记的前序case/数量')
    require([(r['case_id'],r['arm']) for r in m['order']]==[(cid,arm) for cid in expected_cases for arm in ('before','current','current','before')],'前序平衡顺序变化')
    require(m['model']==m['judge_model']==MODEL and m['effort']==m['judge_effort']=='xhigh','前序模型协议不符')
    require(m['student_model_executions']==count,'前序G未完成')
    require(sha(root/'dependencies/sha256.json')==m['dependency_manifest_sha256'],'前序冻结依赖manifest变化');assert_frozen(root/'dependencies')
    results=load(root/'trial-results.json');require(len(results)==count,'前序结果数量不完整')
    require([r['trial_id'] for r in results]==[r['trial_id'] for r in m['order']],'前序实际结果顺序不同')
    outcome=load(root/'request-outcomes.json')
    require(outcome['valid'] and not outcome['findings'],'首批请求outcome未通过')
    require(sha(root/'request-outcomes.json')==m['request_audits']['explicit_request_outcomes']['report_sha256'],'首批请求报告变化')
    require(sha(root/'broker-events.jsonl')==outcome['broker_events_sha256'],'首批代理日志变化')
    evidence={name:sha(root/name) for name in ('manifest.json','trial-results.json','request-outcomes.json','broker-events.jsonl')}
    model_sessions=0;judge_types=Counter()
    for row in results:
        require(row['quality_status'] in ('PASS','FAIL') and row['J_dispatched'],'首批仍有不可判分trial，先处理再扩围')
        g=root/'trials'/row['trial_id']/'G';j=root/'trials'/row['trial_id']/row.get('judge_phase','J')
        for phase in (g,j):
            paths=list((phase/'reports').glob('iteration-*/result.json'));require(len(paths)==1,'首批缺原始G/J结果')
            native=load(paths[0])['case_results'];require(len(native)==1,'首批G/J case数量不符')
            require(native[0]['status']==('PASS' if phase==g else row['quality_status']),'首批native与汇总状态不同')
            require(hashlib.sha256(native[0]['response'].encode()).hexdigest()==row['final_message_sha256'],'首批G/J响应摘要不同')
            evidence[str(paths[0].relative_to(root))]=sha(paths[0])
            if phase==g:require(list((phase/'reports').rglob('rollout-*.jsonl')),'前序缺真实G原生模型trace')
        case=yaml.safe_load((root/'dependencies/cases'/f"{row['case_id']}.yaml").read_text());kind=case['judge']['type'];judge_types[kind]+=1
        j_result=load(next((j/'reports').glob('iteration-*/result.json')))['case_results'][0];rollouts=judge_rollouts(j)
        if expect_gate_failed(j_result):
            criteria=[a for a in j_result['grading']['assertion_results'] if not a.get('text','').startswith('expect.')]
            require(j_result['status']==j_result['grading']['status']=='FAIL' and criteria and not rollouts and not j_result['grading'].get('judge_context'),'前序expect短路证据错误')
            require(all(a.get('skipped') and a.get('passed') is False and a.get('evidence')=='not evaluated: expect gate failed' for a in criteria),'前序未评Judge被误作已评分')
        elif kind=='agent_judge':require(rollouts and j_result['grading'].get('judge_context'),'前序语义Judge缺真实模型证据')
        else:
            require(not rollouts and any(a.get('text','').startswith('script: ') and not a.get('skipped') for a in j_result['grading']['assertion_results']),'前序script Judge缺实际执行证据')
        model_sessions+=len(rollouts)
    require(m['judge_model_executions']==model_sessions,'前序声明的Judge模型次数与真实rollout不同')
    for session in outcome['sessions'].values():
        require(sha(safe(root,session['rollout']))==session['sha256'],'首批归档trace变化')
    return {'directory':str(root),'completed_utc':m['completed_utc'],'valid':True,'evidence_sha256':evidence,
            'configured_judge_types':dict(judge_types),'actual_judge_model_sessions':model_sessions}

def prior_batch_ready(root):return completed_batch_ready(root,('stage1-long-running',))
def prior_stage2_ready(root):return completed_batch_ready(root,('batch-goal','preauthorized-permissions'))

def probe_initial_environment(root,isolation_path,main_root,prior_stage2):
    prior=prior_stage2_ready(prior_stage2)
    original=load(main_root/'manifest.json');iso=load(isolation_path)
    require(sha(isolation_path)==original['isolation_original_sha256'],'环境probe配置不同于原隔离预检')
    iso['docker_binary']=shutil.which('docker');require(iso['docker_binary'],'Docker不可用')
    root.mkdir(parents=True,mode=0o700);shutil.copy2(Path(__file__),root/'probe-source.py');shutil.copy2(isolation_path,root/'isolation.json')
    snapshot_broker(root,iso,start=True);cid=None
    def docker(*args):
        result=subprocess.run([iso['docker_binary'],*args],capture_output=True,text=True,timeout=60)
        require(result.returncode==0,'环境probe Docker失败: '+args[0]+' '+result.stderr)
        return result.stdout
    try:
        cid=docker('create','--label','codex-task=luna-initial-environment','--workdir','/workspace',
                   *iso['create_extra_args'],iso['image_id'],'sleep','infinity').strip()
        docker('start',cid);docker('exec','--privileged',cid,'/opt/baseline/lock-network.sh',iso['broker_ip'])
        inspect=json.loads(docker('inspect',cid))[0]
        require(inspect['Image']==iso['image_id'] and not inspect['Mounts'] and inspect['HostConfig']['ReadonlyRootfs'],'probe镜像/只读/mount不符')
        require(inspect['HostConfig']['CapDrop']==['ALL'] and 'no-new-privileges' in inspect['HostConfig']['SecurityOpt'],'probe权限不符')
        require(list(inspect['NetworkSettings']['Networks'])==[iso['network']],'probe网络不同')
        code="from pathlib import Path;import json;entries=sorted(p.name for p in Path('/workspace').iterdir());print(json.dumps({'initial_entries':entries}));assert not entries,'unexpected initial project material'"
        (root/'project-probe.py').write_text(code+'\n')
        raw=docker('exec',cid,'python3','-c',code);(root/'project-probe.stdout').write_text(raw)
        observations=json.loads(raw);require(observations=={'initial_entries':[]},'初始环境有未解释项目资料')
        dump(root/'container-policy.json',{'image_id':inspect['Image'],'readonly':True,'bind_mounts':[],
            'cap_drop':inspect['HostConfig']['CapDrop'],'security_opt':inspect['HostConfig']['SecurityOpt'],
            'tmpfs':inspect['HostConfig']['Tmpfs'],'networks':list(inspect['NetworkSettings']['Networks'])})
    finally:
        if cid is not None:docker('rm','-f',cid)
    snapshot_broker(root,iso)
    require(not any(e.get('event')=='accepted' for e in map(json.loads,(root/'broker-events.jsonl').read_text().splitlines())),'环境probe期间出现真实模型请求')
    dump(root/'initial-environment.json',INITIAL_ENVIRONMENT_FACTS)
    dump(root/'environment-evidence.json',{'valid':True,'evidence_kind':'actual_initial_docker_probe','model_requests_generated':0,'image_id':iso['image_id'],
        'isolation_sha256':sha(isolation_path),'observations':observations,'prior_stage2':prior,
        'facts_sha256':sha(root/'initial-environment.json'),'source_sha256':sha(root/'probe-source.py'),
        'probe_stdout_sha256':sha(root/'project-probe.stdout'),'container_policy_sha256':sha(root/'container-policy.json'),
        'broker_events_delta_sha256':sha(root/'broker-events.jsonl'),
        'limits':'Fresh base workspace plus original cases with no project fixture. Facts describe initial supplied project material only; no business implementation or cache investigation is verified.'})
    print('初始环境事实probe通过，业务项目资料0；新增模型请求0；未调查业务实现')

def initial_environment_ready(path,main_root):
    require(path is not None,'研究/证据缺口case须提供 --initial-environment 实际probe证据')
    path=path.resolve();e=load(path/'environment-evidence.json');m=load(main_root/'manifest.json');iso=load(main_root/'isolation.json')
    require(e['valid'] and e.get('evidence_kind')=='actual_initial_docker_probe' and e['model_requests_generated']==0 and e['observations']=={'initial_entries':[]},'环境probe未通过')
    require(e['image_id']==iso['image_id'] and e['isolation_sha256']==m['isolation_original_sha256'],'环境probe与实际运行策略不同')
    require(load(path/'initial-environment.json')==INITIAL_ENVIRONMENT_FACTS,'环境附件含非共同初始事实')
    for name,key in (('initial-environment.json','facts_sha256'),('probe-source.py','source_sha256'),
                     ('project-probe.stdout','probe_stdout_sha256'),('container-policy.json','container_policy_sha256'),
                     ('broker-events.jsonl','broker_events_delta_sha256')):
        require(sha(path/name)==e[key],'环境证据SHA变化: '+name)
    require(load(path/'project-probe.stdout')=={'initial_entries':[]},'probe原始输出不同')
    policy=load(path/'container-policy.json')
    require(policy['image_id']==e['image_id'] and policy['readonly'] and policy['bind_mounts']==[] and policy['cap_drop']==['ALL'],'probe实际容器策略不同')
    require(not any(event.get('event')=='accepted' for event in map(json.loads,(path/'broker-events.jsonl').read_text().splitlines())),'环境probe发生模型调用')
    return {'directory':str(path),'evidence_sha256':sha(path/'environment-evidence.json'),'facts_sha256':e['facts_sha256']}

def final_request_audits(root,manifest):
    """Retain the original all-200 gate and separately reconcile known retries."""
    for filename in ('request-coverage.json','request-outcomes.json','strict-request-audit.log','request-outcomes-audit.log'):
        require(not (root/filename).exists(),'拒绝覆盖已有请求审计: '+filename)
    with (root/'strict-request-audit.log').open('w') as log:
        strict=subprocess.run([sys.executable,str(root/'audit-baseline-requests.py'),str(root)],stdout=log,stderr=subprocess.STDOUT)
    strict_path=root/'request-coverage.json'
    strict_report=load(strict_path) if strict_path.exists() else None
    strict_valid=strict.returncode==0 and bool(strict_report and strict_report.get('valid'))
    record={'strict_all_http_200_gate':{'exit_code':strict.returncode,'passed':strict_valid,
        'log':'strict-request-audit.log','log_sha256':sha(root/'strict-request-audit.log'),
        'report':'request-coverage.json' if strict_report is not None else None,
        'report_sha256':sha(strict_path) if strict_report is not None else None,
        'auditor_sha256':sha(root/'audit-baseline-requests.py')}}
    manifest['strict_all_http_200_gate_passed']=strict_valid
    manifest['request_coverage_valid']=strict_valid
    manifest['request_audits']=record
    dump(root/'manifest.json',manifest)
    with (root/'request-outcomes-audit.log').open('w') as log:
        outcome=subprocess.run([sys.executable,str(root/'audit-request-outcomes.py'),str(root)],stdout=log,stderr=subprocess.STDOUT)
    outcome_path=root/'request-outcomes.json'
    outcome_report=load(outcome_path) if outcome_path.exists() else None
    outcome_valid=outcome.returncode==0 and bool(outcome_report and outcome_report.get('valid'))
    record['explicit_request_outcomes']={'exit_code':outcome.returncode,'passed':outcome_valid,
        'log':'request-outcomes-audit.log','log_sha256':sha(root/'request-outcomes-audit.log'),
        'report':'request-outcomes.json' if outcome_report is not None else None,
        'report_sha256':sha(outcome_path) if outcome_report is not None else None,
        'auditor_sha256':sha(root/'audit-request-outcomes.py')}
    manifest['request_outcome_coverage_valid']=outcome_valid
    dump(root/'request-audit-status.json',record);dump(root/'manifest.json',manifest)
    require(strict.returncode in (0,1) and strict_report is not None,'strict审计未正常生成原报告，不能采用fallback')
    require(sha(strict_path)==record['strict_all_http_200_gate']['report_sha256'],'outcome流程改写了原strict报告')
    require((strict.returncode==0)==bool(strict_report.get('valid')),'strict退出状态与原报告不一致')
    require(outcome_valid,'请求outcome未闭环，保留失败证据，禁止标完成')
    require(outcome_report['accepted_requests']==outcome_report['completed_200_requests']+outcome_report['recorded_failed_attempts'],
            'accepted不等于200+已解释失败attempt')
    require(outcome_report['native_token_usage_records']==outcome_report['completed_200_requests'],'原生token记录与200数量不同')
    require(outcome_report['broker_events_sha256']==sha(root/'broker-events.jsonl')
            and outcome_report['auditor_sha256']==sha(root/'audit-request-outcomes.py'),'outcome输入或源码SHA不同')
    return record

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--isolation',type=Path,required=True)
    parser.add_argument('--main-with',type=Path,default=REPO/'.eval-work/luna-with-skill-v2-20261030');parser.add_argument('--eligibility',type=Path)
    parser.add_argument('--case',action='append',choices=FINAL_ONLY_CASES,help='显式扩围；默认只long-running；每case需独立失败分诊')
    parser.add_argument('--candidate',type=Path,help='后续显式加入候选第三臂；默认不加入，源文件与另外两臂同契约')
    parser.add_argument('--prior-batch',type=Path,help='显式扩围/候选前必须完成首4trial并验证其原始结果及请求闭环')
    parser.add_argument('--prior-stage2',type=Path,help='研究/证据缺口case及环境probe前必须完成第二批8trial')
    parser.add_argument('--initial-environment',type=Path,help='提供同镜像初始环境probe生成的共同事实JSON及证据目录')
    mode=parser.add_mutually_exclusive_group(required=True);mode.add_argument('--prepare-only',action='store_true');mode.add_argument('--zero-model-smoke',action='store_true');mode.add_argument('--dispatch',action='store_true');mode.add_argument('--probe-initial-environment',action='store_true')
    args=parser.parse_args();root=args.output.resolve();main_root=args.main_with.resolve();require(not root.exists(),'拒绝覆盖实验')
    if args.probe_initial_environment:
        probe_initial_environment(root,args.isolation,main_root,args.prior_stage2);return
    selected=tuple(args.case or CASES);require(len(selected)==len(set(selected)),'重复case')
    prior=None;stage2=None;environment=None
    if args.dispatch:
        dispatch_ready(main_root,args.eligibility,selected)
        if selected!=CASES or args.candidate:prior=prior_batch_ready(args.prior_batch)
        if set(selected)&set(ENVIRONMENT_CASES):stage2=prior_stage2_ready(args.prior_stage2)
    if set(selected)&set(ENVIRONMENT_CASES):environment=initial_environment_ready(args.initial_environment,main_root)
    main_manifest=load(main_root/'manifest.json');iso=load(args.isolation);iso['docker_binary']=shutil.which('docker')
    require(main_manifest['model']==main_manifest['judge_model']==MODEL and main_manifest['effort']==main_manifest['judge_effort']=='xhigh','主模型协议不符')
    require(sha(args.isolation)==main_manifest['isolation_original_sha256'],'预检隔离配置不同于主30冻结原件')
    require(iso['image_id']==load(main_root/'isolation.json')['image_id'],'镜像不同于主30例')
    binary=REPO/'.eval-work/luna-control-tool/skill-up-without-only';require(sha(binary)==main_manifest['binary_sha256'],'二进制不同')
    prefix=load(PREFIX_SOURCE)['invocation_prefix'];require(prefix.startswith('$goal-prompt\n'),'旧显式prefix缺失')
    current=main_root/main_manifest['skill_snapshot'];arms={'before':BEFORE,'current':current};arm_hashes={}
    if args.candidate:arms['candidate']=args.candidate.resolve()
    files=list(main_manifest['skill_sha256'])
    for arm,path in arms.items():
        require(len(files)==9,'预期9源文件');hashes={r:sha(safe(path,r)) for r in files}
        if arm=='before':
            for relative in files:
                raw=subprocess.check_output(['git','show','1d7622c:skills/goal-prompt/'+relative],cwd=REPO)
                require(hashlib.sha256(raw).hexdigest()==hashes[relative],'before不等于历史真实版本')
        elif arm=='current':require(hashes==main_manifest['skill_sha256'],'current不等于主30冻结版本')
        arm_hashes[arm]=hashes
    cases={cid:yaml.safe_load((REPO/'evals/skill-up/cases'/f'{cid}.yaml').read_text()) for cid in selected}
    require(all('judges' not in case for case in cases.values()),
            '本入口仅供历史单Judge协议；当前语义多Judge案例请使用新协议或原冻结runner，不得改写旧成绩。')
    for cid,case in cases.items():require(set(case['input'])=={'prompt'} and sha(REPO/'evals/skill-up/cases'/f'{cid}.yaml')==main_manifest['original_case_sha256'][cid],'case输入/原rubric已变')
    root.mkdir(parents=True,mode=0o700)
    # Freeze every dependency before preparing the first arm. Later J phases must
    # never copy a live repository checker or wrapper after earlier arms ran.
    frozen=root/'dependencies';(frozen/'scripts').mkdir(parents=True)
    for filename in ('baseline-docker.py','run-baseline.py','audit-baseline-requests.py','audit-request-outcomes.py'):
        shutil.copy2(REPO/'evals/skill-up/scripts'/filename,frozen/'scripts'/filename)
    shutil.copytree(REPO/'evals/skill-up/fixtures',frozen/'evals/skill-up/fixtures')
    if environment:
        shutil.copytree(args.initial_environment.resolve(),frozen/'environment',ignore=shutil.ignore_patterns('__pycache__'))
    (frozen/'cases').mkdir()
    for cid in cases:
        destination=frozen/'cases'/f'{cid}.yaml'
        shutil.copy2(REPO/'evals/skill-up/cases'/f'{cid}.yaml',destination)
        require(sha(destination)==main_manifest['original_case_sha256'][cid],'case冻结过程中变化')
        require(yaml.safe_load(destination.read_text())==cases[cid],'case对象不同于冻结源')
    shutil.copy2(binary,frozen/'skill-up');binary=frozen/'skill-up'
    require(sha(binary)==main_manifest['binary_sha256'],'二进制冻结过程中变化')
    shutil.copy2(PREFIX_SOURCE,frozen/'prefix-source.json')
    require(load(frozen/'prefix-source.json')['invocation_prefix']==prefix,'prefix冻结过程中变化')
    for arm,path in list(arms.items()):
        destination=frozen/'arms'/arm
        for relative,expected in arm_hashes[arm].items():
            source=safe(path,relative);require(sha(source)==expected,'实验臂冻结前已变化')
            target=destination/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
        arms[arm]=destination
    dependencies={str(p.relative_to(frozen)):sha(p) for p in frozen.rglob('*') if p.is_file()}
    dump(frozen/'sha256.json',dependencies)
    for filename in ('run-baseline.py','audit-baseline-requests.py','audit-request-outcomes.py'):
        shutil.copy2(frozen/'scripts'/filename,root/('frozen-'+filename if filename=='run-baseline.py' else filename))
    shutil.copy2(Path(__file__),root/'run-failed-pairs.py');shutil.copy2(PROTOCOL,root/'prospective-protocol.md');shutil.copy2(args.isolation,root/'isolation-base.json')
    sequence=[];repetitions={}
    order=[(cid,arm) for cid in selected for arm in (*arms,*reversed(arms))]
    for index,(cid,arm) in enumerate(order,1):
        key=(cid,arm);repetitions[key]=repetitions.get(key,0)+1;trial='x'+uuid.uuid4().hex[:16]
        row={'order':index,'trial_id':trial,'case_id':cid,'arm':arm,'repetition':repetitions[key]};sequence.append(row)
        prepare_generation(root/'trials'/trial/'G',trial,arms[arm],arm_hashes[arm],cases[cid],prefix,iso,main_manifest['defaults'],main_manifest['retry'],frozen)
        run_cli(binary,root/'trials'/trial/'G',validate_only=True)
        # Validate the real semantic-Judge branch before any student runs.
        # A mock engine must not hide schema conflicts in the real engine.
        judge_preflight=root/'real-judge-preflight'/trial
        prepare_scoring(judge_preflight,trial,cases[cid],'仅用于配置预检，不作质量证据。',iso,main_manifest['defaults'],main_manifest['retry'],frozen)
        run_cli(binary,judge_preflight,validate_only=True)
    dump(root/'arm-mapping-host-only.json',sequence)
    manifest={'created_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'experiment_kind':'zero_model_protocol' if args.zero_model_smoke else 'prospective_failed_version_pairs',
        'main_completed_at_prepare':bool(main_manifest.get('completed_utc')),'case_ids':list(selected),'trial_count':len(sequence),'student_executions_planned':len(sequence),
        'model':MODEL,'effort':'xhigh','judge_model':MODEL,'judge_effort':'xhigh','prefix':prefix,'prefix_source_sha256':sha(PREFIX_SOURCE),
        'main_reference':{'manifest_sha256':sha(main_root/'manifest.json'),'cases_sha256':sha(main_root/'cases-combined.json') if (main_root/'cases-combined.json').exists() else None},
        'prior_batch':prior or {'directory':str(args.prior_batch.resolve()) if args.prior_batch else None,'verified_completed_for_dispatch':False},
        'prior_stage2':stage2,'initial_environment':environment,
        'arms':arm_hashes,'order':sequence,'binary_sha256':sha(binary),'image_id':iso['image_id'],'defaults':main_manifest['defaults'],'retry':main_manifest['retry'],
        'protocol_sha256':sha(root/'prospective-protocol.md'),'runner_sha256':sha(root/'run-failed-pairs.py'),
        'dependency_manifest_sha256':sha(frozen/'sha256.json'),'dependencies_sha256':dependencies,
        'treatment':'overall_version_net_effect; both shortening and prior behavior fixes differ, not pure length',
        'generation_pass_means':'capture_only_not_quality_pass','scoring':'fresh Skill-free final-only replay; original rubric; no absolute style blinding',
        'models_started':False,'student_model_executions':0,'judge_model_executions':0}
    if args.eligibility:shutil.copy2(args.eligibility,root/'eligibility.json')
    dump(root/'manifest.json',manifest)
    if args.prepare_only:print(f'已准备{len(sequence)}个平衡G配置；主30完成并分诊前禁止派发；模型调用0');return
    if args.zero_model_smoke:
        snapshot_broker(root,iso,start=True)
        results=[]
        for row in (next(r for r in sequence if r['case_id']==cid and r['arm']==arm) for cid in selected for arm in arms):
            cid,trial=row['case_id'],row['trial_id'];g=root/'zero-model'/trial/'G';j=root/'zero-model'/trial/'J'
            prepare_generation(g,trial,arms[row['arm']],arm_hashes[row['arm']],cases[cid],prefix,iso,main_manifest['defaults'],main_manifest['retry'],frozen,mock=True)
            captured=run_cli(binary,g);candidate=capture_seal(g,captured,require_real=False);require(candidate is not None,'mock采集失败')
            prepare_scoring(j,trial,cases[cid],candidate,iso,main_manifest['defaults'],main_manifest['retry'],frozen,mock=True)
            score=run_cli(binary,j);audit_scoring(j,cases[cid],candidate,mock=True)
            require(load(next((g/'reports').glob('iteration-*/result.json')))['overall_tokens']==0 and load(next((j/'reports').glob('iteration-*/result.json')))['overall_tokens']==0,'mock管线产生模型token')
            g_ids=load(g/'containers.json');j_ids=load(j/'containers.json')
            require(len(g_ids)==len(j_ids)==1 and not set(g_ids)&set(j_ids),'G/J复用了容器')
            results.append({'case_id':cid,'arm':row['arm'],'judge_type':cases[cid]['judge']['type'],'protocol_verified':True,'capture_status_only':captured['status'],'mock_judge_status_not_quality':score['status'],'model_calls':0})
        snapshot_broker(root,iso)
        events=[json.loads(line) for line in (root/'broker-events.jsonl').read_text().splitlines() if line.strip()]
        require(not any(e.get('event')=='accepted' for e in events),'零模型测试期间出现了真实模型请求')
        dump(root/'zero-model-validation.json',{'passed':True,'tests':results,'quality_claim':False,'accepted_model_requests_generated':0,
             'broker_events_delta_sha256':sha(root/'broker-events.jsonl'),'dependency_manifest_sha256':sha(frozen/'sha256.json')})
        print('零模型G/J材料隔离与SDK字段协议通过；不证明真实评分质量');return
    manifest['models_started']=True;manifest['started_utc']=dt.datetime.now(dt.timezone.utc).isoformat();dump(root/'manifest.json',manifest)
    snapshot_broker(root,iso,start=True);trial_results=[]
    for row in sequence:
        cid,trial=row['case_id'],row['trial_id'];g=root/'trials'/trial/'G';j=root/'trials'/trial/'J'
        assert_frozen(frozen)
        captured=run_cli(binary,g);manifest['student_model_executions']+=1;candidate=capture_seal(g,captured,require_real=True)
        if candidate is None:
            trial_results.append({**row,'generation_capture_status':captured['status'],'quality_status':'UNSCORABLE','error':captured.get('error'),'J_dispatched':False})
            dump(root/'trial-results.json',trial_results);dump(root/'manifest.json',manifest);continue
        audit_generation(root,g,trial)
        if cid in ENVIRONMENT_CASES:audit_student_process(g,cid)
        prepare_scoring(j,trial,cases[cid],candidate,iso,main_manifest['defaults'],main_manifest['retry'],frozen)
        run_cli(binary,j,validate_only=True)
        scored=run_cli(binary,j);audit_scoring(j,cases[cid],candidate)
        g_ids=load(g/'containers.json');j_ids=load(j/'containers.json')
        require(len(g_ids)==len(j_ids)==1 and not set(g_ids)&set(j_ids),'真实G/J未使用各自独立新容器')
        manifest['judge_model_executions']+=len(judge_rollouts(j))
        trial_results.append({**row,'generation_capture_status':captured['status'],'quality_status':scored['status'],'error':scored.get('error'),'J_dispatched':True,
                              'configured_judge_type':cases[cid]['judge']['type'],'judge_model_sessions':len(judge_rollouts(j)),
                              'expect_gate_failed':expect_gate_failed(scored),
                              'judge_skipped_by_expect':expect_gate_failed(scored),
                              'final_message_sha256':hashlib.sha256(candidate.encode()).hexdigest()})
        dump(root/'trial-results.json',trial_results);dump(root/'manifest.json',manifest)
    dump(root/'trial-results.json',trial_results);manifest['cases_finished_utc']=dt.datetime.now(dt.timezone.utc).isoformat();dump(root/'manifest.json',manifest)
    snapshot_broker(root,iso)
    assert_frozen(frozen);final_request_audits(root,manifest)
    manifest['completed_utc']=dt.datetime.now(dt.timezone.utc).isoformat();dump(root/'manifest.json',manifest)
    print(f'{len(sequence)}个版本对照trial已终止；质量状态只取J阶段，capture PASS不算质量通过')

if __name__=='__main__':main()
