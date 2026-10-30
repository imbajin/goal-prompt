#!/usr/bin/env python3
"""冻结并仅运行原30例 GPT-6 Luna xhigh without-Skill；先首例审计再其余29。"""
from pathlib import Path
import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import shlex
import re
import subprocess
import sys
import yaml

REPO = Path(__file__).resolve().parents[3]
MODEL = 'gpt-6-luna'

def require(condition, message):
    if not condition:
        raise RuntimeError(message)

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,v): Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')

def audit_broker(root):
    spec=json.loads((root/'isolation.json').read_text())
    value=subprocess.check_output([spec['docker_binary'],'logs',spec['broker_container']],text=True)
    records=[json.loads(line) for line in value.splitlines() if line.strip()]
    accepted=[r for r in records if r.get('event')=='accepted']
    sessions=set()
    for path in root.rglob('rollout-*.jsonl'):
        for line in path.read_text(errors='replace').splitlines():
            try: item=json.loads(line)
            except ValueError: continue
            if item.get('type')=='session_meta' and item.get('payload',{}).get('id'):
                sessions.add(hashlib.sha256(item['payload']['id'].encode()).hexdigest())
    require(accepted, '没有真实代理请求证据')
    require(all(r.get('model')==MODEL and r.get('effort')=='xhigh' for r in accepted), 'Required evaluation invariant failed')
    (root/'broker-events.jsonl').write_text(value)
    unmatched=[r for r in accepted if r.get('session_sha256') not in sessions]
    require(not unmatched, '发现未归属已归档rollout的模型请求，禁止继续')
    dump(root/'broker-audit.json',{'valid':True,'accepted_requests':len(accepted),
         'archived_sessions':len(sessions),'unmatched_requests':len(unmatched),
         'completed_requests':sum(r.get('event')=='completed' for r in records),
         'upstream_errors':sum(r.get('event') in ('upstream_error','broker_error') for r in records),
         'limits':'代理只记录白名单元数据，不包含请求正文、上游响应正文或认证。'})

def filename_discovery(command):
    """Only metadata commands; never exempt file-content reads or shell expansion."""
    try:
        outer=shlex.split(command)
        if len(outer)!=3 or Path(outer[0]).name not in ('bash','sh') or outer[1] not in ('-lc','-c'):return False
        body=outer[2]
        if any(c in body for c in ('$','`','<','>')):return False
        lexer=shlex.shlex(body.replace('\n',';'),posix=True,punctuation_chars='|&;');lexer.whitespace_split=True
        pieces=[[]]; separators=[]
        for token in lexer:
            if token in ('&&','||','|',';'):separators.append(token);pieces.append([])
            elif token and all(c in '|&;' for c in token):return False
            else:pieces[-1].append(token)
        for index,part in enumerate(pieces):
            if not part:return False
            name=part[0];args=part[1:]
            if name=='pwd' and not args:continue
            if name=='ls':continue
            if name=='rg' and args and args[0]=='--files':
                rest=args[1:]
                if len(rest)%2==0 and all(rest[i] in ('-g','--glob') for i in range(0,len(rest),2)):continue
            if name=='find' and all(not a.startswith('-') or a in ('-name','-iname','-o','-a','-maxdepth','-mindepth','-type') for a in args):continue
            if name=='head' and all(a.lstrip('-').isdigit() or a=='-n' for a in args):continue
            if name=='sort' and not args:continue
            # Only a numeric print range over metadata from the preceding pipe.
            # No filename, extra expression, read/write/exec, or shell expansion.
            if name=='sed' and index and separators[index-1]=='|' and len(args)==2 and args[0]=='-n' and re.fullmatch(r'[1-9][0-9]*(?:,[1-9][0-9]*)?p',args[1]):continue
            return False
        return bool(pieces)
    except ValueError:return False

def audit(root, reports, output_name='isolation-audit.json', configuration='without_skill'):
    require(configuration in ('with_skill','without_skill'),'未知组')
    findings=[]; contexts=[]; states=[]; discovery=[]; result_files=list(reports.glob('iteration-*/result.json'))
    skill_source=root/'snapshot/target/goal-prompt/SKILL.md'
    skill_text=skill_source.read_text().rstrip() if configuration=='with_skill' else ''
    coverage={}
    for p in result_files:
        for c in json.loads(p.read_text())['case_results']:
            require(c['configuration']==configuration, '发现额外组')
            require(c['status'] in ('PASS','FAIL','ERROR','SKIP'), '未知结果状态')
            case_dir=p.parent/c['case_id']/configuration
            coverage[c['case_id']]={'catalog_seen':False,'native_full_injection':False,'full_file_read':False,'target_read_commands':[]}
            agent_rollouts=list((case_dir/'outputs/agent/run').glob('rollout-*.jsonl'))
            observed=[]
            for path in agent_rollouts:
                for line in path.read_text(errors='replace').splitlines():
                    try: item=json.loads(line)
                    except ValueError: continue
                    if item.get('type')=='turn_context':
                        observed.append((item['payload'].get('model'),item['payload'].get('effort')))
            if c['status'] in ('PASS','FAIL') and (not observed or not str(c.get('response','')).strip()):
                findings.append(c['case_id']+':missing-scorable-context-or-response')
            states.append({'case_id':c['case_id'],'status':c['status'],
                           'scorable':c['status'] in ('PASS','FAIL'),
                           'runner_contexts':observed,'error':c.get('error')})
    for p in reports.rglob('rollout-*.jsonl'):
        runner='/outputs/agent/' in str(p)
        case_id=p.relative_to(reports).parts[1]
        for line in p.read_text(errors='replace').splitlines():
            try: e=json.loads(line)
            except ValueError: continue
            d=e.get('payload',{})
            if e.get('type')=='turn_context':
                contexts.append({'file':str(p.relative_to(root)),'model':d.get('model'),'effort':d.get('effort')})
                if d.get('model')!=MODEL or d.get('effort')!='xhigh': findings.append(str(p)+':wrong-model-or-effort')
            if e.get('type')=='response_item' and d.get('role') in ('developer','user'):
                text='\n'.join(x.get('text','') for x in d.get('content',[]) if isinstance(x,dict))
                if '<skills_instructions>' in text or '<skill>' in text:
                    if configuration!='with_skill' or not runner:findings.append(str(p)+':skill-context')
                    else:
                        for block in re.findall(r'<skills_instructions>(.*?)</skills_instructions>',text,re.S):
                            names=re.findall(r'(?m)^- ([\w-]+): ',block)
                            if names!=['goal-prompt']:findings.append(str(p)+':unexpected-catalog')
                            else:coverage[case_id]['catalog_seen']=True
                        for block in re.findall(r'<skill>(.*?)</skill>',text,re.S):
                            if '<name>goal-prompt</name>' not in block or '<path>/workspace/.codex/skills/goal-prompt/SKILL.md</path>' not in block or skill_text not in block:
                                findings.append(str(p)+':unexpected-skill-injection')
                            else:coverage[case_id]['native_full_injection']=True
    def inspect_command(p,cmd,output,exit_code):
        if any(s in cmd for s in ['codex-upstream exec','/v1/responses','192.168.117.2','urllib.request','requests.post']):
            findings.append(str(p)+':untracked-model-call-command:'+cmd)
        if exit_code!=0:return
        permitted=(configuration=='with_skill' and '/outputs/agent/' in str(p)
                   and '.codex/skills/goal-prompt/' in cmd
                   and not any(s in cmd for s in ['/Users/zhu/','/memories/','github.com/imbajin/goal-prompt','codex-upstream exec']))
        if permitted:
            case_id=p.relative_to(reports).parts[1]
            if cmd not in coverage[case_id]['target_read_commands']:coverage[case_id]['target_read_commands'].append(cmd)
            if skill_text in output:coverage[case_id]['full_file_read']=True
        if output and any(s in cmd for s in ['/Users/zhu/','/memories/','SKILL.md','github.com/imbajin/goal-prompt','codex-upstream exec']):
            if permitted:return
            elif filename_discovery(cmd):discovery.append({'file':str(p.relative_to(root)),'command':cmd,'output':output,'classification':'filename_discovery_not_content_read'})
            else:findings.append(str(p)+':suspicious-successful-read:'+cmd)
    # stdout.json is overwritten on multi-turn resume; native rollouts retain
    # commands from every turn. Inspect both sources, including earlier reads.
    for p in reports.rglob('rollout-*.jsonl'):
        for line in p.read_text(errors='replace').splitlines():
            try:e=json.loads(line)
            except ValueError:continue
            d=e.get('payload',{});i=d.get('item',{})
            if e.get('type')!='event_msg' or d.get('type')!='item_completed' or i.get('type')!='CommandExecution':continue
            command=i.get('command',[])
            cmd=shlex.join(command) if isinstance(command,list) else command
            inspect_command(p,cmd,i.get('aggregated_output',''),i.get('exit_code'))
    for p in reports.rglob('stdout.json'):
        for line in p.read_text(errors='replace').splitlines():
            try:e=json.loads(line)
            except ValueError:continue
            i=e.get('item',{})
            if e.get('type')=='item.completed' and i.get('type')=='command_execution':
                inspect_command(p,i.get('command',''),i.get('aggregated_output',''),i.get('exit_code'))
    require(states, '没有结果，不能将此批次记为完成')
    if configuration=='with_skill':
        for cid,row in coverage.items():
            if not row['catalog_seen']:findings.append(cid+':target-not-in-runner-catalog')
            row['actual_full_load_observed']=row['native_full_injection'] or row['full_file_read']
    value={'contexts':contexts,'cases':states,'findings':findings,'filename_discovery':discovery,'valid':not findings,
           'configuration':configuration,'skill_coverage':coverage if configuration=='with_skill' else {},
           'limits':'实际加载与目录可见分开；未观测到完整加载不冒称已加载。原始FAIL不改为PASS。'}
    dump(reports/output_name,value)
    if findings: raise RuntimeError('隔离或模型审计失败，禁止继续/使用此cohort')

def run_batch(root, binary, config, name, selected):
    reports=root/name
    require(not reports.exists(), '拒绝覆盖已有模型证据')
    cmd=[str(binary),'--config',str(root/'empty-user.yaml'),'run',str(config),
         '--output-dir',str(reports),'--event-log',str(root/(name+'-events.jsonl'))]
    for case in selected: cmd += ['--include-case-name',case]
    dump(root/(name+'-command.json'),cmd)
    env=os.environ.copy();env['SKILL_UP_WITHOUT_SKILL_ONLY']='1';env['LUNA_CONTROL_DIR']=str(root)
    env['PATH']=str(root/'bin')+os.pathsep+env['PATH']
    env.pop('CODEX_THREAD_ID',None);env.pop('CODEX_INTERNAL_ORIGINATOR_OVERRIDE',None)
    print('真实without组：'+name+' / '+str(len(selected))+'例',flush=True)
    with (root/(name+'.log')).open('w') as log:
        r=subprocess.run(cmd,env=env,stdout=log,stderr=subprocess.STDOUT)
    if r.returncode not in (0,1): raise RuntimeError('框架基础设施失败')
    audit(root,reports)
    audit_broker(root)
    subprocess.run([sys.executable,str(root/'audit-baseline-requests.py'),str(root),'--partial'],check=True)
    shutil.copy2(root/'request-coverage.json',root/(name+'-request-coverage.json'))
    shutil.copy2(root/'broker-events.jsonl',root/(name+'-broker-events.jsonl'))
    return r.returncode

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--isolation',type=Path,required=True);ap.add_argument('--prepare-only',action='store_true')
    a=ap.parse_args();root=a.output.resolve();require(not root.exists(), '输出目录已存在')
    iso=json.loads(a.isolation.read_text());require(iso['model_called'] is False, 'Required evaluation invariant failed')
    require(iso.get('ready_for_model_execution') is True, '隔离尚未通过，禁止派发')
    require(all(iso['checks'][s]['exit_code']==0 for s in ['catalog','credentials_absent','host_paths_hidden','network_rules','broker_policy','script_execution','tmp_execution_mount']), 'Required evaluation invariant failed')
    require(all(iso['checks'][s]['exit_code']!=0 for s in ['proxy_github_denied','direct_public_denied','host_gateway_denied']), 'Required evaluation invariant failed')
    require(all(iso['checks'][s]['exit_code']==22 for s in ['other_model_denied','other_effort_denied','remote_tool_denied','unknown_remote_tool_denied','other_route_denied','identity_missing_denied','identity_bad_uuid_denied']), '真实HTTP拒绝探针缺失或未返回拒绝')
    iso['docker_binary']=shutil.which('docker');require(iso['docker_binary'], 'Required evaluation invariant failed')
    root.mkdir(parents=True,mode=0o700);dump(root/'isolation.json',iso)
    (root/'bin').mkdir();shutil.copy2(REPO/'evals/skill-up/scripts/baseline-docker.py',root/'bin/docker');(root/'bin/docker').chmod(0o755)
    snapshot=root/'snapshot';snapshot.mkdir();(snapshot/'evals').mkdir();(snapshot/'skill-up').mkdir()
    shutil.copytree(REPO/'evals/skill-up/fixtures',snapshot/'skill-up/fixtures')
    (snapshot/'skill-up/cases').mkdir();cfg=yaml.safe_load((REPO/'evals/skill-up/eval.yaml').read_text())
    files=[];ids=[];history={}
    for rel in cfg['cases']['files']:
        p=REPO/'evals'/rel;c=yaml.safe_load(p.read_text())
        if c['id']=='host-recovery-boundary': continue
        require('engine' not in c and 'model' not in c.get('judge',{}), '禁止case覆盖模型')
        prior=subprocess.check_output(['git','show','1d7622c:evals/'+rel],cwd=REPO)
        require(prior==p.read_bytes(), '原30例内容变化需另记，禁止静默更改')
        shutil.copy2(p,snapshot/rel);files.append(rel);ids.append(c['id']);history[c['id']]=sha(p)
    require(len(ids)==len(set(ids))==30, 'Required evaluation invariant failed')
    cfg['skills']=[];cfg['environment']={'type':'docker','image':iso['image_id']}
    cfg['engine']={'name':'codex','version':'0.164.0','model':{'provider':'openai','name':MODEL}}
    cfg['judge']={'model':MODEL};cfg['benchmark']={'enabled':False};cfg['cases']['files']=files
    cfg['cases']['parallelism']=1;config=snapshot/'evals/eval.yaml';config.write_text(yaml.safe_dump(cfg,allow_unicode=True,sort_keys=False))
    (root/'empty-user.yaml').write_text('{}\n')
    binary=REPO/'.eval-work/luna-control-tool/skill-up-without-only';require(binary.is_file(), 'Required evaluation invariant failed')
    shutil.copy2(REPO/'evals/skill-up/scripts/without-only.patch',root/'without-only.patch')
    shutil.copy2(Path(__file__),root/'run-baseline.py')
    shutil.copy2(REPO/'evals/skill-up/scripts/audit-baseline-requests.py',root/'audit-baseline-requests.py')
    manifest={'created_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'scope':'30 original cases, without_skill only',
        'model':MODEL,'effort':'xhigh','judge_model':MODEL,'judge_effort':'xhigh','with_skill_executed':False,
        'skills':[],'case_ids':ids,'original_case_sha256':history,'prefix':None,
        'skill_up_version':subprocess.check_output([str(binary),'--version'],text=True).strip(),
        'upstream_commit':'53f6daecf4ac79e4e53ea53f3fe17dac3114debb','local_patch_sha256':sha(root/'without-only.patch'),
        'binary_sha256':sha(binary),'runner_sha256':sha(Path(__file__)),'docker_wrapper_sha256':sha(root/'bin/docker'),
        'request_auditor_sha256':sha(root/'audit-baseline-requests.py'),
        'container_source_sha256':{p.name:sha(p) for p in (REPO/'evals/skill-up/scripts/baseline-container').glob('*') if p.is_file()},
        'isolation_sha256':sha(root/'isolation.json'),'snapshot_sha256':{str(p.relative_to(snapshot)):sha(p) for p in snapshot.rglob('*') if p.is_file()},
        'defaults':cfg['cases']['defaults'],'retry':cfg['cases']['retry_policy'],'parallelism':1,
        'historical_comparison':'5.6 Luna high baseline 6PASS/23FAIL/1ERROR; different tool, judge and effort; descriptive only'}
    dump(root/'manifest.json',manifest)
    for cmd,name in [([str(binary),'--config',str(root/'empty-user.yaml'),'validate',str(config)],'validate'),
                     ([str(binary),'--config',str(root/'empty-user.yaml'),'run',str(config),'--dry-run'],'dry-run')]:
        env=os.environ.copy();env['SKILL_UP_WITHOUT_SKILL_ONLY']='1'
        r=subprocess.run(cmd,capture_output=True,text=True,env=env);(root/(name+'.log')).write_text(r.stdout+r.stderr);require(r.returncode==0, r.stdout+r.stderr)
    if a.prepare_only: print('冻结30例完成，未调用模型');return
    manifest['started_utc']=dt.datetime.now(dt.timezone.utc).isoformat();dump(root/'manifest.json',manifest)
    run_batch(root,binary,config,'pilot',[ids[0]])
    manifest['pilot_gate_sha256']=sha(root/'pilot-request-coverage.json')
    manifest['pilot_broker_events_sha256']=sha(root/'pilot-broker-events.jsonl')
    dump(root/'manifest.json',manifest)
    pilot_results=json.loads(next((root/'pilot').glob('iteration-*/result.json')).read_text())['case_results']
    require(len(pilot_results)==1 and pilot_results[0]['status'] in ('PASS','FAIL'), '首例尚不可判分，须先修环境/错误再继续29例')
    run_batch(root,binary,config,'remaining',ids[1:])
    results=[]
    for name in ['pilot','remaining']:
        for p in (root/name).glob('iteration-*/result.json'): results.extend(json.loads(p.read_text())['case_results'])
    require(len(results)==30 and {x['case_id'] for x in results}==set(ids), 'Required evaluation invariant failed')
    require(all(x['configuration']=='without_skill' for x in results), 'Required evaluation invariant failed')
    from collections import Counter
    manifest['case_status_counts']=dict(Counter(x['status'] for x in results))
    manifest['scorable_cases']=sum(x['status'] in ('PASS','FAIL') for x in results)
    manifest['cases_finished_utc']=dt.datetime.now(dt.timezone.utc).isoformat()
    dump(root/'manifest.json',manifest);dump(root/'cases-combined.json',results)
    subprocess.run([sys.executable,str(root/'audit-baseline-requests.py'),str(root)],check=True)
    manifest['completed_utc']=dt.datetime.now(dt.timezone.utc).isoformat();manifest['all_isolation_audits_pass']=True
    dump(root/'manifest.json',manifest)
    print('30例已终止；原始状态计数 '+str(manifest['case_status_counts'])+'；ERROR/SKIP不计可判分通过或失败',flush=True)
if __name__=='__main__': main()
