#!/usr/bin/env python3
"""仅运行原30例Luna xhigh with-Skill；先冻结、pilot精确审计，再执行其余29例。"""
from pathlib import Path
import argparse
from collections import Counter
import datetime as dt
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import yaml

REPO=Path(__file__).resolve().parents[3]
MODEL='gpt-6-luna'
CONTROL=REPO/'.eval-work/luna-xhigh-control-v4-20261030'
HELPER_PATH=Path(__file__).with_name('run-baseline.py')
HELPER_SOURCE=HELPER_PATH.read_bytes()
helper_spec=importlib.util.spec_from_file_location('baseline_helpers',HELPER_PATH)
helpers=importlib.util.module_from_spec(helper_spec)
exec(compile(HELPER_SOURCE,str(HELPER_PATH),'exec'),helpers.__dict__)
require,sha,dump=helpers.require,helpers.sha,helpers.dump

def child_env(root):
    env=os.environ.copy()
    env.pop('SKILL_UP_WITHOUT_SKILL_ONLY',None)
    env.pop('CODEX_THREAD_ID',None)
    env.pop('CODEX_INTERNAL_ORIGINATOR_OVERRIDE',None)
    env['LUNA_CONTROL_DIR']=str(root)
    env['PATH']=str(root/'bin')+os.pathsep+env['PATH']
    return env

def copy_preflight(source,root,iso):
    dest=root/'preflight';dest.mkdir()
    extra={'workspace_target_catalog':('workspace-target-catalog.json','workspace-target-catalog.stderr'),
           'judge_empty_catalog':('judge-empty-catalog.json','judge-empty-catalog.stderr')}
    for key,check in iso['checks'].items():
        if key=='with_skill_pipeline':
            source_file=source/'pipeline/results/iteration-1/result.json'
            require(sha(source_file)==check['result_sha256'],'预检pipeline结果已变化')
            shutil.copy2(source_file,dest/'with-skill-pipeline-result.json')
            continue
        names=extra.get(key,(f'broker-{key}.stdout',f'broker-{key}.stderr'))
        for stream,name in zip(('stdout','stderr'),names):
            src=source/name
            require(sha(src)==check[stream+'_sha256'],'预检证据SHA变化: '+name)
            shutil.copy2(src,dest/name)
    for name in ('broker-guard-events.jsonl','workspace-skill-hashes.json','broker-boundary.json','iptables-broker.txt'):
        shutil.copy2(source/name,dest/name)
    for name in ('evals/eval.yaml','evals/protocol.yaml','evals/check.sh','run.log'):
        src=source/'pipeline'/name;target=dest/'pipeline'/name
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,target)

def check_isolation(iso):
    positive=('script_execution','tmp_execution_mount','host_paths_hidden','credentials_absent','catalog',
              'no_materialized_skills','network_rules','ripgrep','broker_policy',
              'workspace_target_catalog','judge_empty_catalog','with_skill_pipeline')
    http_reject=('identity_missing_denied','identity_bad_uuid_denied','other_model_denied',
                 'other_effort_denied','unknown_remote_tool_denied','remote_tool_denied','other_route_denied')
    require(iso.get('ready_for_model_execution') is True and iso.get('model_called') is False,'隔离未ready或预检发生模型调用')
    require(iso.get('upstream_requests_during_all_probes')==0,'预检上游调用非0')
    for key in positive:require(iso['checks'][key]['exit_code']==0,'正探针未通过: '+key)
    for key in http_reject:require(iso['checks'][key]['exit_code']==22,'真实HTTP拒绝探针未通过: '+key)
    for key in ('top_level_generate_command_denied','proxy_github_denied','direct_public_denied','host_gateway_denied'):
        require(iso['checks'][key]['exit_code']!=0,'拒绝探针失效: '+key)

def run_batch(root,binary,config,name,selected):
    reports=root/name;require(not reports.exists(),'拒绝覆盖已有模型证据')
    command=[str(binary),'--config',str(root/'empty-user.yaml'),'run',str(config),
             '--output-dir',str(reports),'--event-log',str(root/(name+'-events.jsonl'))]
    for case in selected:command+=['--include-case-name',case]
    dump(root/(name+'-command.json'),command)
    print(f'真实with-Skill：{name} / {len(selected)}例',flush=True)
    with (root/(name+'.log')).open('w') as log:
        result=subprocess.run(command,env=child_env(root),stdout=log,stderr=subprocess.STDOUT)
    require(result.returncode in (0,1),'评测框架基础设施失败')
    helpers.audit(root,reports,configuration='with_skill')
    helpers.audit_broker(root)
    subprocess.run([sys.executable,str(root/'audit-baseline-requests.py'),str(root),'--partial'],check=True)
    shutil.copy2(root/'request-coverage.json',root/(name+'-request-coverage.json'))
    shutil.copy2(root/'broker-events.jsonl',root/(name+'-broker-events.jsonl'))
    return reports

def audit_lifecycle(root,cases):
    """Exactly one guarded/install container per serial case; Judge cleanup set."""
    ids=json.loads((root/'containers.json').read_text())
    require(len(ids)==len(set(ids))==len(cases),'容器/case一一覆盖不符')
    groups={name:{p.stem:json.loads(p.read_text()) for p in (root/name).glob('*.json')}
            for name in ('container-audits','skill-install-audits','skill-cleanup-audits')}
    require(set(ids)==set(groups['container-audits'])==set(groups['skill-install-audits']),'安装/守卫ID集合不完整')
    spec=json.loads((root/'isolation.json').read_text());runtime=spec['target_skill']['files']
    expected_cleanups=set();mapping=[]
    for ident,case in zip(ids,cases):
        row=groups['container-audits'][ident]
        require(row['image']==spec['image_id'] and row['readonly'] and row['cap_drop']==['ALL'] and not row['bind_mounts'],'容器策略错误')
        require(row['network_locked'] and row['catalog_empty'] and row['networks']==[spec['network']] and 'no-new-privileges' in row['security_opt'],'守卫错误')
        row=groups['skill-install-audits'][ident]
        require(row['container']==ident and row['files']==runtime and row['catalog_names']==['goal-prompt'] and row['model_called'] is False,'安装证据错误')
        directories=list(root.glob('*/iteration-*/'+case['case_id']+'/with_skill'))
        require(len(directories)==1,'case路径非唯一')
        has_judge=bool(list((directories[0]/'outputs/judge/run').glob('rollout-*.jsonl')))
        if has_judge:expected_cleanups.add(ident)
        mapping.append({'case_id':case['case_id'],'container':ident,'semantic_judge':has_judge})
    require(expected_cleanups==set(groups['skill-cleanup-audits']),'逐例Judge清理ID集合不符')
    for ident,row in groups['skill-cleanup-audits'].items():
        require(row['container']==ident and row['files']=={} and row['catalog_names']==[] and row['model_called'] is False,'Judge前未清除目标')
    value={'valid':True,'mapping_basis':'parallelism=1, exactly one created container per ordered native case; no environment retry','cases':mapping,
           'container_count':len(ids),'installation_count':len(ids),'cleanup_count':len(expected_cleanups),'model_calls':0}
    dump(root/'lifecycle-audit.json',value)
    return value

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',type=Path,required=True);ap.add_argument('--isolation',type=Path,required=True)
    ap.add_argument('--prepare-only',action='store_true')
    args=ap.parse_args();root=args.output.resolve();require(not root.exists(),'输出目录已存在')
    original_iso=json.loads(args.isolation.read_text());check_isolation(original_iso)
    reference=json.loads((CONTROL/'manifest.json').read_text())
    reference_iso=json.loads((CONTROL/'isolation.json').read_text())
    require(reference.get('completed_utc') and reference['model']==reference['judge_model']==MODEL,'原对照不是同一模型的完整批次')
    require(reference['effort']==reference['judge_effort']=='xhigh','原对照思考深度不符')
    require(original_iso['image_id']==reference_iso['image_id'],'镜像与原对照不同')
    require(original_iso['create_extra_args']==reference_iso['create_extra_args'],'容器策略与原对照不同')
    binary=REPO/'.eval-work/luna-control-tool/skill-up-without-only'
    require(binary.is_file() and sha(binary)==reference['binary_sha256'],'必须复用原对照同一patched binary')
    version=subprocess.check_output([str(binary),'--version'],text=True).strip()
    require(version==reference['skill_up_version'],'skill-up版本与原对照不一致')
    root.mkdir(parents=True,mode=0o700);(root/'bin').mkdir()
    shutil.copy2(args.isolation,root/'isolation-original.json')
    shutil.copy2(REPO/'evals/skill-up/scripts/baseline-docker.py',root/'bin/docker');(root/'bin/docker').chmod(0o755)
    snapshot=root/'snapshot';(snapshot/'evals').mkdir(parents=True);(snapshot/'skill-up/cases').mkdir(parents=True)
    shutil.copytree(REPO/'evals/skill-up/fixtures',snapshot/'skill-up/fixtures')
    source_skill=REPO/'skills/goal-prompt';skill_target=snapshot/'target/goal-prompt';skill_target.mkdir(parents=True)
    tracked=subprocess.check_output(['git','ls-files','skills/goal-prompt'],cwd=REPO,text=True).splitlines()
    skill_files={str(Path(p).relative_to('skills/goal-prompt')):sha(REPO/p) for p in tracked}
    require(len(skill_files)==9 and skill_files==original_iso['skill_bundle_sha256'],'Skill九文件与隔离预检不一致')
    for relative in skill_files:
        target=skill_target/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source_skill/relative,target)
    runtime_files={p:h for p,h in skill_files.items() if not p.startswith('evals/')}
    require(len(runtime_files)==7 and runtime_files==original_iso['skill_runtime_sha256'],'native installer excludes evals; expected7 runtime files')
    iso={**original_iso,'docker_binary':shutil.which('docker'),
         'target_skill':{'path':'/workspace/.codex/skills/goal-prompt','files':runtime_files}}
    require(iso['docker_binary'],'Docker命令不可用');dump(root/'isolation.json',iso)
    copy_preflight(args.isolation.resolve().parent,root,original_iso)
    cfg=yaml.safe_load((REPO/'evals/skill-up/eval.yaml').read_text());files=[];ids=[];case_hashes={}
    for relative in cfg['cases']['files']:
        path=REPO/'evals'/relative;case=yaml.safe_load(path.read_text())
        if case['id']=='host-recovery-boundary':continue
        require('engine' not in case and 'model' not in case.get('judge',{}),'case不得覆盖模型')
        history=subprocess.check_output(['git','show','1d7622c:evals/'+relative],cwd=REPO)
        require(history==path.read_bytes(),'原30例内容变化: '+relative)
        require(sha(path)==reference['original_case_sha256'][case['id']],'case与without对照不同')
        shutil.copy2(path,snapshot/relative);files.append(relative);ids.append(case['id']);case_hashes[case['id']]=sha(path)
    require(len(ids)==len(set(ids))==30 and ids==reference['case_ids'],'case集合或顺序与原对照不同')
    require(cfg['cases']['defaults']==reference['defaults'] and cfg['cases']['retry_policy']==reference['retry'],'默认门槛/重试策略不得变化')
    cfg['skills']=[{'source':'local_path','path':'target/goal-prompt'}]
    cfg['environment']={'type':'docker','image':iso['image_id']}
    cfg['engine']={'name':'codex','version':'0.164.0','model':{'provider':'openai','name':MODEL}}
    cfg['judge']={'model':MODEL};cfg['benchmark']={'enabled':False};cfg['cases']['files']=files;cfg['cases']['parallelism']=1
    config=snapshot/'evals/eval.yaml';config.write_text(yaml.safe_dump(cfg,allow_unicode=True,sort_keys=False))
    (root/'empty-user.yaml').write_text('{}\n')
    for name in ('run-with-skill.py','audit-baseline-requests.py'):
        shutil.copy2(Path(__file__).with_name(name),root/name)
    (root/'run-baseline.py').write_bytes(HELPER_SOURCE)
    shutil.copy2(REPO/'evals/skill-up/scripts/without-only.patch',root/'without-only.patch')
    fixture_hashes={str(p.relative_to(snapshot)):sha(p) for p in (snapshot/'skill-up/fixtures').rglob('*') if p.is_file()}
    old_fixtures={k:v for k,v in reference['snapshot_sha256'].items() if k.startswith('skill-up/fixtures/')}
    fixture_changes={k:{'without_sha256':old_fixtures.get(k),'with_sha256':fixture_hashes.get(k)}
                     for k in sorted(set(old_fixtures)|set(fixture_hashes)) if old_fixtures.get(k)!=fixture_hashes.get(k)}
    manifest={'created_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'scope':'30 original cases, with_skill only',
       'configuration':'with_skill','model':MODEL,'effort':'xhigh','judge_model':MODEL,'judge_effort':'xhigh',
       'with_skill_executed':False,'without_skill_executed':False,'with_skill_execution_planned':True,'prefix':None,
       'skills':cfg['skills'],'skill_sha256':skill_files,'skill_runtime_sha256':runtime_files,'native_install_excludes':['evals/'],'skill_snapshot':'snapshot/target/goal-prompt',
       'case_ids':ids,'original_case_sha256':case_hashes,'defaults':cfg['cases']['defaults'],'retry':cfg['cases']['retry_policy'],'parallelism':1,
       'skill_up_version':version,'binary_sha256':sha(binary),'upstream_commit':reference['upstream_commit'],
       'local_patch_sha256':sha(root/'without-only.patch'),'without_selector_unset':True,
       'runner_sha256':sha(root/'run-with-skill.py'),'baseline_helpers_sha256':sha(root/'run-baseline.py'),
       'docker_wrapper_sha256':sha(root/'bin/docker'),'request_auditor_sha256':sha(root/'audit-baseline-requests.py'),
       'isolation_original_sha256':sha(root/'isolation-original.json'),'isolation_sha256':sha(root/'isolation.json'),
       'snapshot_sha256':{str(p.relative_to(snapshot)):sha(p) for p in snapshot.rglob('*') if p.is_file()},
       'startup_flags':{'python_optimize_level':sys.flags.optimize,'PYTHONOPTIMIZE_present':'PYTHONOPTIMIZE' in os.environ,
                        'child_without_selector_removed':True,'child_parent_thread_vars_removed':True},
       'without_reference':{'directory':str(CONTROL),'manifest_sha256':sha(CONTROL/'manifest.json'),
                            'native_case_results_sha256':sha(CONTROL/'cases-combined.json'),'model_rerun':False},
       'fixture_changes_from_without':fixture_changes,
       'comparison_limits':'Same original inputs/model/effort/image/runtime policy; only Skill availability changes. Authorized Judge fix uses frozen-output replay for without; preserve raw and replay separately.'}
    dump(root/'manifest.json',manifest)
    for command,name in [([str(binary),'--config',str(root/'empty-user.yaml'),'validate',str(config)],'validate'),
                         ([str(binary),'--config',str(root/'empty-user.yaml'),'run',str(config),'--dry-run'],'dry-run')]:
        result=subprocess.run(command,env=child_env(root),capture_output=True,text=True)
        (root/(name+'.log')).write_text(result.stdout+result.stderr);require(result.returncode==0,result.stdout+result.stderr)
    if args.prepare_only:print('已冻结原30 with-Skill，未调用模型');return
    manifest['started_utc']=dt.datetime.now(dt.timezone.utc).isoformat();manifest['with_skill_executed']=True;dump(root/'manifest.json',manifest)
    run_batch(root,binary,config,'pilot',[ids[0]])
    pilot=json.loads(next((root/'pilot').glob('iteration-*/result.json')).read_text())['case_results']
    require(len(pilot)==1 and pilot[0]['status'] in ('PASS','FAIL'),'pilot尚不可判分，不派其余29例')
    pilot_audit=json.loads((root/'pilot/isolation-audit.json').read_text())
    require(pilot_audit['skill_coverage'][ids[0]]['actual_full_load_observed'], '首个正向case未实际完整加载Skill，先核查管线，不派其余29例')
    require(len(list((root/'skill-install-audits').glob('*.json')))==1, 'pilot安装阶段证据不完整')
    require(len(list((root/'skill-cleanup-audits').glob('*.json')))==1, 'pilot语义Judge前未核实清除Skill')
    manifest['pilot_gate_sha256']=sha(root/'pilot-request-coverage.json');manifest['pilot_broker_events_sha256']=sha(root/'pilot-broker-events.jsonl');dump(root/'manifest.json',manifest)
    run_batch(root,binary,config,'remaining',ids[1:])
    cases=[]
    for batch in ('pilot','remaining'):
        for path in sorted((root/batch).glob('iteration-*/result.json')):cases.extend(json.loads(path.read_text())['case_results'])
    require(len(cases)==30 and {c['case_id'] for c in cases}==set(ids),'原始结果集合不完整')
    require(all(c['configuration']=='with_skill' for c in cases),'发现额外configuration')
    audit_lifecycle(root,cases)
    manifest['case_status_counts']=dict(Counter(c['status'] for c in cases));manifest['scorable_cases']=sum(c['status'] in ('PASS','FAIL') for c in cases)
    manifest['cases_finished_utc']=dt.datetime.now(dt.timezone.utc).isoformat();dump(root/'manifest.json',manifest);dump(root/'cases-combined.json',cases)
    subprocess.run([sys.executable,str(root/'audit-baseline-requests.py'),str(root)],check=True)
    manifest['completed_utc']=dt.datetime.now(dt.timezone.utc).isoformat();manifest['all_isolation_audits_pass']=True;dump(root/'manifest.json',manifest)
    print('30例with-Skill已终止，原始状态 '+str(manifest['case_status_counts'])+'；ERROR/SKIP不计通过或失败',flush=True)

if __name__=='__main__':main()
