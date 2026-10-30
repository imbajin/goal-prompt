#!/usr/bin/env python3
"""宿主 Docker 启动守卫：只操作当前评测拥有的容器，不记录模型执行 argv 或凭据。"""
import json
import io
import hashlib
import os
from pathlib import Path
import posixpath
import re
import shlex
import subprocess
import sys
import tarfile

root = Path(os.environ['LUNA_CONTROL_DIR']).resolve()
spec = json.loads((root / 'isolation.json').read_text())
real = spec['docker_binary']
args = sys.argv[1:]
registry = root / 'containers.json'
owned = json.loads(registry.read_text()) if registry.exists() else []

def require(condition, message):
    if not condition:
        raise RuntimeError(message)

def call(argv):
    return subprocess.run([real, *argv], capture_output=True, text=True)

def emit(result):
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    raise SystemExit(result.returncode)

def record(kind, ident, **data):
    with (root / 'docker-events.jsonl').open('a') as f:
        f.write(json.dumps({'event': kind, 'container': ident, **data})+'\n')

def skill_phase_probe(ident, installed):
    target=spec.get('target_skill')
    if not target:return
    require(target['path']=='/workspace/.codex/skills/goal-prompt', '目标Skill路径必须固定')
    code="""import json,hashlib,pathlib,sys
p=pathlib.Path(sys.argv[1]);found={}
if p.exists():
 for f in p.rglob('*'):
  if f.is_symlink(): raise RuntimeError('symlink in Skill')
  if f.is_file(): found[str(f.relative_to(p))]=hashlib.sha256(f.read_bytes()).hexdigest()
print(json.dumps(found))
"""
    result=call(['exec',ident,'python3','-c',code,target['path']])
    require(result.returncode==0,'Skill hash probe失败')
    files=json.loads(result.stdout)
    require(files==(target['files'] if installed else {}),'Skill bytes或Judge清除状态不一致')
    probe=call(['exec','--workdir','/workspace',ident,'codex','debug','prompt-input','检查当前可用工具。'])
    require(probe.returncode==0,'Skill catalog probe失败')
    values=json.loads(probe.stdout)
    text='\n'.join(b.get('text','') for item in values for b in item.get('content',[]) if isinstance(b,dict))
    catalog='\n'.join(re.findall(r'<skills_instructions>(.*?)</skills_instructions>',text,re.S))
    names=re.findall(r'(?m)^- ([\w-]+): ',catalog)
    require(names==(['goal-prompt'] if installed else []),'runner/Judge catalog不符合隔离预期')
    folder=root/('skill-install-audits' if installed else 'skill-cleanup-audits');folder.mkdir(exist_ok=True)
    (folder/(ident+'.json')).write_text(json.dumps({'container':ident,'files':files,'catalog_names':names,
        'catalog_sha256':hashlib.sha256(probe.stdout.encode()).hexdigest(),'model_called':False},indent=2)+'\n')
    record('skill_installed' if installed else 'skill_removed_before_judge',ident)

def validate_policy():
    require(spec['network']=='goal-prompt-luna-control-internal', '必须使用指定专用隔离网络')
    network=call(['network','inspect',spec['network']])
    require(network.returncode==0 and json.loads(network.stdout)[0]['Internal'] is True, '网络必须internal')
    require(spec['after_start_command']==['docker','exec','--privileged','{container_id}','/opt/baseline/lock-network.sh',spec['broker_ip']], '禁止覆盖可信网络锁命令')
    expected_tmpfs={'/tmp:rw,exec,nosuid,size=128m','/workspace:rw,nosuid,size=512m',
                    '/root/.codex:rw,nosuid,mode=700,size=256m',
                    '/root/.codex/skills:ro,nosuid,mode=555,size=1m'}
    expected_env={'BASELINE_API_BASE_URL='+spec['api_base_url'],
                  *[k+'=' for k in ('HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','http_proxy','https_proxy','all_proxy')],
                  'NO_PROXY=*','no_proxy=*'}
    values=iter(spec['create_extra_args']);seen={};tmpfs=set();environment=set()
    for option in values:
        require(option in ('--network','--cap-drop','--security-opt','--read-only','--tmpfs','--env'), '未知容器策略参数')
        if option=='--read-only':seen[option]=True;continue
        value=next(values)
        if option=='--tmpfs':require(value not in tmpfs,'重复tmpfs');tmpfs.add(value)
        elif option=='--env':require(value not in environment,'重复env');environment.add(value)
        else:require(option not in seen,'重复容器策略');seen[option]=value
    require(seen=={'--network':spec['network'],'--cap-drop':'ALL','--security-opt':'no-new-privileges','--read-only':True}, '隔离参数不匹配')
    require(tmpfs==expected_tmpfs and environment==expected_env, '禁止额外挂载或环境参数')

if not args:
    raise SystemExit('缺少 Docker 命令')
if args[0] == 'create':
    validate_policy()
    framework=(len(args)==9 and args[1]=='--name' and re.fullmatch(r'skill-up-[a-f0-9]{12}',args[2])
               and args[3:]==['--workdir','/workspace','--entrypoint','sleep',spec['image_id'],'infinity'])
    smoke=args[1:]==[spec['image_id'],'sleep','infinity']
    require(framework or smoke, 'create只允许固定skill-up入口，禁止额外env-file/entrypoint/容器参数')
    result = call(['create', *spec['create_extra_args'], *args[1:]])
    if result.returncode == 0:
        ident = result.stdout.strip()
        owned.append(ident)
        registry.write_text(json.dumps(owned)+'\n')
        record('created', ident, image=spec['image_id'])
    emit(result)
elif args[0] == 'start':
    require(len(args)==2, 'start只允许一个容器ID')
    ident = args[-1]
    if ident not in owned:
        raise SystemExit('禁止启动不属于当前评测的容器')
    result = call(args)
    if result.returncode:
        emit(result)
    guard = [v.replace('{container_id}', ident) for v in spec['after_start_command']][1:]
    lock = call(guard)
    if lock.returncode:
        call(['rm','-f',ident])
        raise SystemExit('出站网络锁定失败，容器已删除')
    inspected = call(['inspect', ident])
    info = json.loads(inspected.stdout)[0]
    hc = info['HostConfig']
    require(not hc['Privileged'] and not hc.get('CapAdd') and not hc.get('Devices') and not hc.get('DeviceRequests'), '禁止额外权限或设备')
    require(not hc.get('PidMode') and hc.get('IpcMode')!='host' and not hc.get('UTSMode') and not hc.get('UsernsMode'), '禁止宿主namespace')
    require(not hc.get('PortBindings') and hc.get('NetworkMode')==spec['network'], '禁止端口暴露或额外网络')
    require(hc['ReadonlyRootfs'] and hc['CapDrop'] == ['ALL'], 'Required evaluation invariant failed')
    require(any('no-new-privileges' in v for v in hc['SecurityOpt']), 'Required evaluation invariant failed')
    require(set(info['NetworkSettings']['Networks']) == {spec['network']}, 'Required evaluation invariant failed')
    binds = [m for m in info['Mounts'] if m['Type'] == 'bind']
    require(not info['Mounts'] and not hc.get('VolumesFrom'), '禁止任何卷或额外挂载')
    require(not binds, '被测容器禁止任何宿主bind或凭据挂载')
    require('/root/.codex/skills' in hc['Tmpfs'] and 'ro' in hc['Tmpfs']['/root/.codex/skills'].split(','), 'Required evaluation invariant failed')
    probe = call(['exec', ident, 'codex', 'debug', 'prompt-input', '检查当前可用工具。'])
    require(probe.returncode == 0, 'catalog预检失败')
    values = json.loads(probe.stdout)
    texts = '\n'.join(b.get('text','') for item in values for b in item.get('content',[]) if isinstance(b,dict))
    require('<skills_instructions>' not in texts and '<skill>' not in texts, '发现Skill注入')
    path_probe = "import pathlib\npaths=['/Users/zhu','/var/run/docker.sock','/workspace/.codex/skills/goal-prompt','/root/.agents/skills','/root/.codex/auth.json']\nif any(pathlib.Path(p).exists() for p in paths): raise RuntimeError('host path visible')\nif list(pathlib.Path('/root/.codex/skills').rglob('SKILL.md')): raise RuntimeError('Skill materialized')\nprint('PASS')"
    paths = call(['exec',ident,'python3','-c',path_probe])
    require(paths.returncode == 0, '宿主路径或Skill文件可见')
    (root / 'container-audits').mkdir(exist_ok=True)
    (root / 'container-audits' / (ident+'.json')).write_text(json.dumps({
        'image': info['Image'], 'readonly': hc['ReadonlyRootfs'], 'cap_drop': hc['CapDrop'],
        'security_opt': hc['SecurityOpt'], 'networks': list(info['NetworkSettings']['Networks']),
        'bind_mounts': [{'destination': m['Destination'], 'readonly': not m['RW']} for m in binds],
        'tmpfs': hc['Tmpfs'], 'catalog_empty': True, 'host_paths_hidden': True,
        'network_locked': True, 'model_called_by_preflight': False}, indent=2)+'\n')
    record('guard_passed',ident)
    emit(result)
elif args[0] == 'cp' and len(args)==3 and ':' in args[1]:
    ident,source=args[1].split(':',1);target=Path(args[2])
    require(ident in owned, '下载来源必须属于本次评测')
    if source.endswith('/.'):
        result=subprocess.run([real,'exec',ident,'tar','-cf','-','-C',source[:-2],'.'],capture_output=True)
        if result.returncode:
            sys.stderr.buffer.write(result.stderr);raise SystemExit(result.returncode)
        target.mkdir(parents=True,exist_ok=True)
        with tarfile.open(fileobj=io.BytesIO(result.stdout),mode='r:') as archive:
            archive.extractall(target,filter='data')
    else:
        result=subprocess.run([real,'exec',ident,'cat',source],capture_output=True)
        if result.returncode:
            sys.stderr.buffer.write(result.stderr);raise SystemExit(result.returncode)
        target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(result.stdout)
    raise SystemExit(0)
elif args[0] == 'cp' and len(args)==3 and ':' in args[2]:
    # Docker daemon refuses cp into a read-only rootfs even when destination
    # is writable tmpfs. Stream only the requested fixture through exec tar.
    source=args[1]; ident,target=args[2].split(':',1)
    require(ident in owned, '上传目标必须属于本次评测')
    require(target.startswith(('/workspace/','/tmp/','/root/.codex/')) or target=='/workspace', 'Required evaluation invariant failed')
    skill=spec.get('target_skill');skill_relative=None
    if skill and target.startswith(skill['path']+'/'):
        skill_relative=target[len(skill['path'])+1:]
        require(skill_relative in skill['files'] and Path(source).is_file(), '禁止上传非冻结Skill文件')
        require(hashlib.sha256(Path(source).read_bytes()).hexdigest()==skill['files'][skill_relative], '上传Skill源字节变化')
    buf=io.BytesIO()
    with tarfile.open(fileobj=buf,mode='w') as archive:
        if source.endswith('/.'):
            archive.add(source[:-2],arcname='.')
            destination=target
        else:
            archive.add(source,arcname=posixpath.basename(target))
            destination=posixpath.dirname(target)
    result=subprocess.run([real,'exec','-i',ident,'tar','--no-same-owner','-xf','-','-C',destination],
                          input=buf.getvalue(),capture_output=True)
    sys.stdout.buffer.write(result.stdout);sys.stderr.buffer.write(result.stderr)
    if result.returncode==0 and spec.get('target_skill') and target==spec['target_skill']['path']:
        skill_phase_probe(ident,True)
    elif result.returncode==0 and skill_relative is not None:
        folder=root/'skill-install-progress';folder.mkdir(exist_ok=True);path=folder/(ident+'.json')
        progress=json.loads(path.read_text()) if path.exists() else {}
        progress[skill_relative]=skill['files'][skill_relative]
        path.write_text(json.dumps(progress,indent=2)+'\n')
        if progress==skill['files']:skill_phase_probe(ident,True)
    raise SystemExit(result.returncode)
elif args[0] == 'exec':
    index=1
    while index<len(args) and args[index].startswith('-'):
        require(args[index] in ('--workdir','--env') and index+1<len(args), '禁止覆盖exec权限或运行身份')
        if args[index]=='--workdir':require(args[index+1] in ('/workspace','/'), '工作目录仅允许容器workspace或原生CLI安装根目录')
        else:
            key,separator,value=args[index+1].partition('=')
            require(separator and key in ('PATH','SKILL_UP_CODEX_THREAD_ID','EVAL_TRANSCRIPT_PATH','EVAL_FINAL_MESSAGE','EVAL_EXIT_CODE'), '禁止隐式继承宿主env或注入凭据/配置')
            if key=='PATH':require(all(p.startswith('/') for p in value.split(':')), 'PATH必须来自容器绝对路径')
            elif key=='SKILL_UP_CODEX_THREAD_ID':require(bool(re.fullmatch(r'[a-f0-9-]{36}',value)), 'thread ID格式错误')
            elif key=='EVAL_TRANSCRIPT_PATH':require(not value or value.startswith('/tmp/'), 'transcript必须在容器tmp中')
            elif key=='EVAL_EXIT_CODE':require(bool(re.fullmatch(r'-?\d+',value)), 'exit code格式错误')
        index+=2
    require(index<len(args)-1 and args[index] in owned, 'exec必须属于本批次容器')
    # 不记录模型执行argv；实际输出由框架分别保留。
    result=call(args)
    command=args[index+1:]
    if result.returncode==0 and spec.get('target_skill') and command[:2]==['sh','-c']:
        try:words=shlex.split(command[2])
        except ValueError:words=[]
        if words==['rm','-rf','--','.codex/skills/goal-prompt']:
            skill_phase_probe(args[index],False)
    emit(result)
elif args[0] == 'rm':
    require(len(args)==3 and args[1]=='-f' and args[2] in owned, 'rm仅允许本批次单容器')
    emit(call(args))
elif args[0] == 'stop':
    require(len(args)==4 and args[1:3]==['--time','5'] and args[3] in owned, 'stop仅允许本批次单容器')
    emit(call(args))
else:
    raise SystemExit('禁止非评测Docker子命令')
