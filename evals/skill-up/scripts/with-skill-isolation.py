#!/usr/bin/env python3
"""Restore the frozen Luna test isolation and probe with-Skill installation, without model calls."""
from pathlib import Path
import argparse
import os
import shutil
import sys

REPO=Path(__file__).resolve().parents[3]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',type=Path,default=REPO/'.eval-work/luna-with-isolation')
args=parser.parse_args()
OUTPUT=args.output.resolve()
IMAGE='sha256:a2c44b0a32d802aa8a9d807844bfbbe573430b97947e9ad9e5a9b9686efb9963'
NETWORK='goal-prompt-luna-control-internal'
EGRESS='goal-prompt-luna-control-egress'
BROKER='goal-prompt-luna-control-proxy'
PROBE='goal-prompt-luna-control-probe'

def require(condition,message='Isolation invariant failed'):
    if not condition:raise RuntimeError(message)

import json,subprocess,hashlib,io,tarfile
os.chdir(REPO)
require(not OUTPUT.exists(),'Refuse to overwrite probe evidence')
OUTPUT.mkdir(parents=True,mode=0o700)
(OUTPUT/'isolation.json').write_text(json.dumps({'ready_for_model_execution':False,'model_called':False})+'\n')
def docker(*argv,check=True):
    result=subprocess.run(['docker',*argv],capture_output=True,text=True)
    if check and result.returncode:raise RuntimeError('Docker setup command failed: '+argv[0]+'; '+result.stderr)
    return result
for name in (BROKER,PROBE):require(docker('container','inspect',name,check=False).returncode!=0,'Task container already exists')
for name in (NETWORK,EGRESS):require(docker('network','inspect',name,check=False).returncode!=0,'Task network already exists')
require(docker('image','inspect',IMAGE,'--format','{{.Id}}').stdout.strip()==IMAGE,'Frozen image missing')
auth=Path('/Users/zhu/.codex/auth.json')
require(auth.is_file(),'Existing auth file missing; do not fabricate credentials')
business_before=docker('ps','--no-trunc','--format','{{.ID}} {{.Names}}').stdout
(OUTPUT/'unrelated-containers-before.txt').write_text(business_before)
docker('network','create','--internal','--subnet','192.168.117.0/24','--label','codex-task=luna-with-skill',NETWORK)
docker('network','create','--label','codex-task=luna-with-skill',EGRESS)
docker('create','--name',BROKER,'--label','codex-task=luna-with-skill','--network',NETWORK,'--ip','192.168.117.2',
       '--cap-drop','ALL','--security-opt','no-new-privileges','--read-only',
       '--mount','type=bind,source='+str(auth)+',target=/run/secrets/codex-auth.json,readonly',
       '--env','UPSTREAM_CONNECT_PROXY=http://proxy.orb.internal:8305',
       IMAGE,'python3','/opt/baseline/api-broker.py')
docker('network','connect','--gw-priority','1',EGRESS,BROKER)
docker('start',BROKER)

import json, subprocess, pathlib, hashlib, io, tarfile
root=OUTPUT
image=IMAGE;network=NETWORK;broker=BROKER
def run(args,check=True,timeout=60):
 r=subprocess.run(args,text=True,capture_output=True,timeout=timeout)
 if check and r.returncode:raise RuntimeError((args,r.returncode,r.stdout,r.stderr))
 return r
info=json.loads(run(['docker','inspect',broker]).stdout)[0]
ip=info['NetworkSettings']['Networks'][network]['IPAddress'];base=f'http://{ip}:3128/v1'
extra=['--network',network,'--cap-drop','ALL','--security-opt','no-new-privileges','--read-only',
       '--tmpfs','/tmp:rw,exec,nosuid,size=128m','--tmpfs','/workspace:rw,nosuid,size=512m',
       '--tmpfs','/root/.codex:rw,nosuid,mode=700,size=256m',
       '--tmpfs','/root/.codex/skills:ro,nosuid,mode=555,size=1m','--env','BASELINE_API_BASE_URL='+base]
for key in ['HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','http_proxy','https_proxy','all_proxy']:
 extra+=['--env',key+'=']
extra+=['--env','NO_PROXY=*','--env','no_proxy=*']
name='goal-prompt-luna-control-probe'
cid=run(['docker','create','--name',name,'--label','codex-task=luna-xhigh-control','--workdir','/workspace',*extra,image,'sleep','infinity']).stdout.strip();run(['docker','start',cid]);run(['docker','exec','--privileged',cid,'/opt/baseline/lock-network.sh',ip])
# Match the framework upload path without Docker cp into the read-only rootfs.
archive=io.BytesIO()
with tarfile.open(fileobj=archive,mode="w") as tar:
 for fixture in ("check-stage2-doc.sh", "check-stage2-migration.sh", "check-goal-char-limit.py"):
  tar.add(pathlib.Path("evals/skill-up/fixtures/scripts")/fixture, arcname=fixture)
 data=b"#!/usr/bin/env bash\nset -euo pipefail\nprintf 'PASS uploaded executable script\\n'\n"
 entry=tarfile.TarInfo("execution-smoke.sh");entry.size=len(data);entry.mode=0o700;tar.addfile(entry,io.BytesIO(data))
upload=subprocess.run(["docker","exec","-i",cid,"tar","--no-same-owner","-xf","-","-C","/tmp"],input=archive.getvalue(),capture_output=True)
require(upload.returncode==0, upload.stderr.decode())
script_probe="""import os, pathlib, subprocess
paths=['execution-smoke.sh','check-stage2-doc.sh','check-stage2-migration.sh','check-goal-char-limit.py']
for name in paths:pathlib.Path('/tmp',name).chmod(0o700)
subprocess.run(['/tmp/execution-smoke.sh'],check=True)
samples={'check-stage2-doc.sh':'/goal 更新文档并验证示例。', 'check-stage2-migration.sh':'/goal 完成全部兼容迁移。入口 .goal-task/auth-migration/state.md；CI通过，独立审查后复审。继续其余独立工作；全部剩余工作真实阻塞才blocked。', 'check-goal-char-limit.py':'/goal 核查实现并记录验证结果。'}
for name,message in samples.items():
 result=subprocess.run(['/tmp/'+name],env={**os.environ,'EVAL_FINAL_MESSAGE':message},capture_output=True,text=True)
 assert result.returncode==0,(name,result.returncode,result.stderr)
 invalid=subprocess.run(['/tmp/'+name],env={**os.environ,'EVAL_FINAL_MESSAGE':'invalid response'},capture_output=True,text=True)
 assert invalid.returncode==1,(name,invalid.returncode)
 print('PASS actual fixture judge executable + positive/negative:',name)
"""
mount_probe="""from pathlib import Path
mounts={parts[1]:set(parts[3].split(',')) for line in Path('/proc/mounts').read_text().splitlines() if (parts:=line.split())}
assert {'rw','nosuid','nodev'}<=mounts['/tmp'] and 'noexec' not in mounts['/tmp'],mounts['/tmp']
assert 'ro' in mounts['/root/.codex/skills'],mounts['/root/.codex/skills']
for path in ['/tmp','/workspace','/root/.codex','/root/.codex/skills']:print(path,','.join(sorted(mounts[path])))
"""
invalid_other=json.dumps({'model':'gpt-6.1-sol','reasoning':{'effort':'xhigh'},'stream':True})
invalid_effort=json.dumps({'model':'gpt-6-luna','reasoning':{'effort':'high'},'stream':True})
invalid_external=json.dumps({'model':'gpt-6-luna','reasoning':{'effort':'xhigh'},'stream':True,'tools':[{'type':'web_search'}]})
commands={
 'script_execution':['python3','-c',script_probe],
 'tmp_execution_mount':['python3','-c',mount_probe],
 'host_paths_hidden':['python3','-c',"from pathlib import Path; p=['/Users/zhu','/var/run/docker.sock','/root/.codex/auth.json','/run/secrets/codex-auth.json','/root/.agents/skills']; assert all(not Path(x).exists() for x in p); print('PASS host source/Skill/Memory/results/socket and credentials absent')"],
 'credentials_absent':['python3','-c',"from pathlib import Path; assert not any(Path(p).exists() for p in ['/root/.codex/auth.json','/run/secrets/codex-auth.json']); print('PASS case credentials absent; no file content read')"],
 'catalog':['codex','debug','prompt-input','本轮只检查空 Skill catalog，不请求模型。'],
 'no_materialized_skills':['python3','-c',"from pathlib import Path; assert not list(Path('/root/.codex/skills').rglob('SKILL.md')); print('PASS no materialized Skill')"],
 'top_level_generate_command_denied':['codex','review'],
 'network_rules':['python3','-c',"from pathlib import Path; print([l for l in Path('/proc/self/status').read_text().splitlines() if l.startswith(('CapEff','NoNewPrivs'))])"],
 'proxy_github_denied':['curl','--noproxy','','--proxy',f'http://{ip}:3128','--max-time','15','-I','https://github.com'],
 'direct_public_denied':['curl','--noproxy','*','--connect-timeout','3','--max-time','5','-I','https://1.1.1.1'],
 'host_gateway_denied':['curl','--noproxy','*','--connect-timeout','3','--max-time','5','-I','http://192.168.117.1:8305'],
 'identity_missing_denied':['curl','-sS','--fail','--max-time','15','-H','Content-Type: application/json','--data-binary',json.dumps({'model':'gpt-6-luna','reasoning':{'effort':'xhigh'},'stream':True}),base+'/responses'],
 'identity_bad_uuid_denied':['curl','-sS','--fail','--max-time','15','-H','Content-Type: application/json','-H','session-id: bad','-H','thread-id: bad','--data-binary',json.dumps({'model':'gpt-6-luna','reasoning':{'effort':'xhigh'},'stream':True}),base+'/responses'],
 'ripgrep':['rg','--version'],
 'other_model_denied':['curl','-sS','--fail','--max-time','15','-H','Content-Type: application/json','--data-binary',invalid_other,base+'/responses'],
 'other_effort_denied':['curl','-sS','--fail','--max-time','15','-H','Content-Type: application/json','--data-binary',invalid_effort,base+'/responses'],
 'unknown_remote_tool_denied':['curl','-sS','--fail','--max-time','15','-H','Content-Type: application/json','--data-binary',json.dumps({'model':'gpt-6-luna','reasoning':{'effort':'xhigh'},'stream':True,'tools':[{'type':'future_remote_tool'}]}),base+'/responses'],
 'remote_tool_denied':['curl','-sS','--fail','--max-time','15','-H','Content-Type: application/json','--data-binary',invalid_external,base+'/responses'],
 'other_route_denied':['curl','-sS','--fail','--max-time','15','-H','Content-Type: application/json','--data-binary','{}',base+'/chat/completions'],
 'broker_policy':['python3','/opt/baseline/api-broker.py','--self-test'],
}
checks={}
for key,cmd in commands.items():
 r=run(['docker','exec',cid,*cmd],False)
 (root/('broker-'+key+'.stdout')).write_text(r.stdout);(root/('broker-'+key+'.stderr')).write_text(r.stderr)
 checks[key]={'exit_code':r.returncode,'stdout_sha256':hashlib.sha256(r.stdout.encode()).hexdigest(),'stderr_sha256':hashlib.sha256(r.stderr.encode()).hexdigest()}
 if key.endswith('_denied'):require(r.returncode!=0, (key,r.stdout,r.stderr))
 else:require(r.returncode==0, (key,r.stdout,r.stderr))
values=json.loads((root/'broker-catalog.stdout').read_text());texts='\n'.join(b.get('text','') for item in values for b in item.get('content',[]) if isinstance(b,dict));require('<skills_instructions>' not in texts and '<skill>' not in texts, 'Probe invariant failed')
inspected=json.loads(run(['docker','inspect',cid]).stdout)[0];require(not inspected['Mounts'], 'Probe invariant failed');require(inspected['HostConfig']['CapDrop']==['ALL'], 'Probe invariant failed');require(inspected['HostConfig']['ReadonlyRootfs'], 'Probe invariant failed');require('ro' in inspected['HostConfig']['Tmpfs']['/root/.codex/skills'].split(','), 'Probe invariant failed')
(root/'probe-inspect-broker.json').write_text(json.dumps(inspected,indent=2)+'\n');(root/'iptables-broker.txt').write_text(run(['docker','exec','--privileged',cid,'iptables-save']).stdout)
logs=run(['docker','logs',broker]).stdout
(root/'broker-guard-events.jsonl').write_text(logs)
events=[json.loads(l) for l in logs.splitlines() if l.strip()];require(events and all(e['counts']['upstream_requests']==0 for e in events), 'Probe invariant failed');require(all(e['event']=='denied' for e in events), 'Probe invariant failed')
manifest={'image':image,'image_id':run(['docker','image','inspect',image,'--format','{{.Id}}']).stdout.strip(),'network':network,'proxy_container':broker,'broker_container':broker,'proxy_ip':ip,'broker_ip':ip,'api_base_url':base,'create_extra_args':extra,'after_start_command':['docker','exec','--privileged','{container_id}','/opt/baseline/lock-network.sh',ip],'checks':checks,'model_called':False,'ready_for_model_execution':False,'credential_boundary':'Agent容器无bind/凭据；只有可信broker把既有auth文件RO挂在/run/secrets/codex-auth.json，模型不能读到。broker仅Luna xhigh Responses转发，秘密仅在内存与合法上游Authorization使用，不记录/持久化。','broker_upstream_requests_during_preflight':0,'limits':'零模型仅证明隔离与请求白名单；首正式case才验证原生Responses/ChatGPT兼容。每case新容器；不挂全配置/criteria/历史数据。','upstream_connect_proxy':'http://proxy.orb.internal:8305'}
(root/'isolation.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v['exit_code'] for k,v in checks.items()}));print('PASS broker/credential/network/catalog isolation; upstream/model calls=0')

# The target is installed in workspace; the home catalog stays empty/read-only.
import re
skill=REPO/'skills/goal-prompt'
skill_files=sorted(p for p in skill.rglob('*') if p.is_file() and '__pycache__' not in p.parts)
require(len(skill_files)==9,'Expected the unchanged nine-file Skill bundle')
skill_hashes={str(p.relative_to(skill)):hashlib.sha256(p.read_bytes()).hexdigest() for p in skill_files}
runtime_files=[p for p in skill_files if p.relative_to(skill).parts[0]!='evals']
runtime_hashes={str(p.relative_to(skill)):skill_hashes[str(p.relative_to(skill))] for p in runtime_files}
run(['docker','exec',cid,'mkdir','-p','/workspace/.codex/skills/goal-prompt'])
archive=io.BytesIO()
with tarfile.open(fileobj=archive,mode='w') as tar:
    for path in runtime_files:tar.add(path,arcname=str(path.relative_to(skill)))
upload=subprocess.run(['docker','exec','-i',cid,'tar','--no-same-owner','-xf','-','-C','/workspace/.codex/skills/goal-prompt'],input=archive.getvalue(),capture_output=True)
require(upload.returncode==0,'Skill upload failed')
proof_code="from pathlib import Path;import hashlib,json;root=Path('/workspace/.codex/skills/goal-prompt');actual={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()};print(json.dumps(actual,sort_keys=True));assert not list(Path('/root/.codex/skills').rglob('SKILL.md'))"
proof=run(['docker','exec',cid,'python3','-c',proof_code]);(root/'workspace-skill-hashes.json').write_text(proof.stdout)
require(json.loads(proof.stdout)==runtime_hashes,'Installed runtime Skill bytes differ')
def catalog_text(text):
    values=json.loads(text)
    return '\n'.join(block.get('text','') for item in values for block in item.get('content',[]) if isinstance(block,dict))
def probe_catalog(stem):
    result=run(['docker','exec',cid,'codex','debug','prompt-input','只检查当前可用Skill目录，不调用模型。'])
    (root/(stem+'.json')).write_text(result.stdout);(root/(stem+'.stderr')).write_text(result.stderr)
    return result,catalog_text(result.stdout)
cat_result,text=probe_catalog('workspace-target-catalog')
roots=dict(re.findall(r'- `([^`]+)` = `([^`]+)`',text))
entries=re.findall(r'\(file: ([^)]+)\)',text)
paths=set()
for entry in entries:
    alias,slash,relative=entry.partition('/')
    paths.add(str(Path(roots[alias])/relative) if alias in roots else entry)
require(paths=={'/workspace/.codex/skills/goal-prompt/SKILL.md'},'Runner catalog is not target-only: '+repr(paths))
require('goal-prompt' in text,'Target absent from runner catalog')
checks['workspace_target_catalog']={'exit_code':0,'stdout_sha256':hashlib.sha256(cat_result.stdout.encode()).hexdigest(),'stderr_sha256':hashlib.sha256(cat_result.stderr.encode()).hexdigest()}
# This is the exact POSIX operation used by removeDefaultRunSkillsBeforeJudge.
run(['docker','exec','--workdir','/workspace',cid,'sh','-c',"rm -rf -- '.codex/skills/goal-prompt'"])
judge_result,text=probe_catalog('judge-empty-catalog')
require('<skills_instructions>' not in text and '<skill>' not in text,'Judge catalog still contains target')
checks['judge_empty_catalog']={'exit_code':0,'stdout_sha256':hashlib.sha256(judge_result.stdout.encode()).hexdigest(),'stderr_sha256':hashlib.sha256(judge_result.stderr.encode()).hexdigest()}
run(['docker','rm','-f',cid])

# A deterministic custom engine exercises actual skill-up's shared installer,
# Docker upload/download, target catalog, script Judge, and Judge cleanup.
pipeline=root/'pipeline';pipeline.mkdir();(pipeline/'bin').mkdir();(pipeline/'evals').mkdir()
shutil.copytree(skill,pipeline/'goal-prompt')
pipeline_spec={**manifest,'docker_binary':shutil.which('docker')}
(pipeline/'isolation.json').write_text(json.dumps(pipeline_spec,ensure_ascii=False,indent=2)+'\n')
shutil.copy2(REPO/'evals/skill-up/scripts/baseline-docker.py',pipeline/'bin/docker');(pipeline/'bin/docker').chmod(0o755)
(pipeline/'empty-user.yaml').write_text('{}\n')
(pipeline/'evals/protocol.yaml').write_text(json.dumps({'id':'with-install-protocol','input':{'prompt':'零模型安装与评分管线探针。'},'expect':{'exit_code':0}}))
engine_code="""from pathlib import Path
import hashlib,json,subprocess
p=Path('/workspace/.codex/skills/goal-prompt/SKILL.md')
if not p.is_file():raise RuntimeError('Skill missing')
if hashlib.sha256(p.read_bytes()).hexdigest()!=EXPECTED:raise RuntimeError('Skill differs')
r=subprocess.run(['codex','debug','prompt-input','仅检查目录。'],capture_output=True,text=True)
if r.returncode or 'goal-prompt' not in r.stdout:raise RuntimeError('Target catalog missing')
Path('/workspace/pipeline-catalog.json').write_text(r.stdout)
print(json.dumps({'final_message':'protocol-ok','exit_code':0}))
""".replace('EXPECTED',repr(skill_hashes['SKILL.md']))
judge_script="""#!/usr/bin/env bash
set -euo pipefail
[ "$EVAL_FINAL_MESSAGE" = protocol-ok ]
python3 - <<'INNER'
from pathlib import Path
import json,subprocess
p=Path('/workspace/.codex/skills/goal-prompt/SKILL.md')
if not p.is_file():raise RuntimeError('Installed target missing before script judge')
subprocess.run(['sh','-c',"rm -rf -- '.codex/skills/goal-prompt'"],cwd='/workspace',check=True)
r=subprocess.run(['codex','debug','prompt-input','仅检查空目录。'],capture_output=True,text=True)
if r.returncode:raise RuntimeError('Catalog command failed')
values=json.loads(r.stdout)
text='\\n'.join(block.get('text','') for item in values for block in item.get('content',[]) if isinstance(block,dict))
if '<skills_instructions>' in text or '<skill>' in text:raise RuntimeError('Judge catalog is not empty')
if list(Path('/root/.codex/skills').rglob('SKILL.md')):raise RuntimeError('Home Skill materialized')
print('PASS installed exact target; shared installer; script Judge execution; target removal; empty Judge catalog; no model calls')
INNER
"""
(pipeline/'evals/check.sh').write_text(judge_script)
config={'schema_version':'v1alpha1','environment':{'type':'docker','image':IMAGE},
        'skills':[{'source':'local_path','path':'goal-prompt','target':'.codex/skills/goal-prompt'}],
        'engine':{'name':'protocol-only','custom':{'transport':'local','response_format':'session_result','local':{'command':'python3','args':['-c',engine_code]}}},
        'cases':{'files':['evals/protocol.yaml'],'parallelism':1},
        'judge':{'type':'script','script_path':'evals/check.sh'},'benchmark':{'enabled':False},'report':{'formats':['json']}}
(pipeline/'evals/eval.yaml').write_text(json.dumps(config,ensure_ascii=False,indent=2)+'\n')
env=os.environ.copy();env['PATH']=str(pipeline/'bin')+os.pathsep+env['PATH'];env['LUNA_CONTROL_DIR']=str(pipeline);env['PYTHONOPTIMIZE']='1'
for key in ('SKILL_UP_WITHOUT_SKILL_ONLY','CODEX_THREAD_ID','CODEX_INTERNAL_ORIGINATOR_OVERRIDE'):env.pop(key,None)
cli=REPO/'.eval-work/bin/skill-up'
command=[str(cli),'--config',str(pipeline/'empty-user.yaml'),'run',str(pipeline/'evals/eval.yaml'),'--output-dir',str(pipeline/'results')]
result=subprocess.run(command,env=env,capture_output=True,text=True)
(pipeline/'run.log').write_text(result.stdout+result.stderr)
require(result.returncode==0,'Deterministic Docker with-Skill pipeline failed; see run.log')
report=json.loads((pipeline/'results/iteration-1/result.json').read_text())
require([(c['configuration'],c['status']) for c in report['case_results']]==[('with_skill','PASS')],'Pipeline variant or grade mismatch')
require(report['total_tokens']==report['judge_tokens']==0,'Deterministic pipeline unexpectedly used model tokens')
checks['with_skill_pipeline']={'exit_code':0,'result_sha256':hashlib.sha256((pipeline/'results/iteration-1/result.json').read_bytes()).hexdigest(),'model_calls':0}
logs=run(['docker','logs',broker]).stdout
(root/'broker-guard-events.jsonl').write_text(logs)
events=[json.loads(line) for line in logs.splitlines() if line.strip()]
require(events and all(e['counts']['upstream_requests']==0 for e in events),'Unexpected upstream request during no-model probes')
broker_info=json.loads(run(['docker','inspect',broker]).stdout)[0]
mounts=broker_info['Mounts']
require(len(mounts)==1 and mounts[0]['Destination']=='/run/secrets/codex-auth.json' and not mounts[0]['RW'],'Broker credential mount mismatch')
(root/'broker-boundary.json').write_text(json.dumps({'image':broker_info['Image'],'mount_destinations':[{'destination':m['Destination'],'readonly':not m['RW']} for m in mounts],'networks':sorted(broker_info['NetworkSettings']['Networks']),'agent_credentials':False},indent=2)+'\n')
manifest.update({'checks':checks,'ready_for_model_execution':True,'model_called':False,'skill_bundle_sha256':skill_hashes,
                 'skill_runtime_sha256':runtime_hashes,'native_install_excludes':['evals/'],
                 'pipeline':'pipeline/results/iteration-1/result.json','upstream_requests_during_all_probes':0,
                 'with_skill_method':'Native default target is workspace .codex/skills/goal-prompt; home/system skills remain empty read-only. Real semantic-Judge catalog isolation must also be checked in the first formal case.',
                 'probe_script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                 'previous_without_image_id':IMAGE,'same_container_image_as_without':True})
(root/'isolation.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
print('PASS restored frozen isolation, 20 original + 3 with-Skill checks, zero upstream/model calls; ready=true')
