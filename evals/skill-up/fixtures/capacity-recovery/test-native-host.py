#!/usr/bin/env python3
"""Test native Goal recovery with injected capacity in a disposable Docker host.

The provider is a local scripted HTTP server, not a real model or online
capacity test. The image must contain Codex 0.164.0, Python and codex-upstream
(the baseline-container image does). No host binds, credentials or egress.
"""
import argparse
import hashlib
import importlib.util
import http.server
import json
from pathlib import Path
import queue
import sqlite3
import subprocess
import sys
import threading
import time
import uuid


def native(args):
    output=args.output;output.mkdir(parents=True,exist_ok=False)
    events=[];requests=[];lock=threading.Lock()
    first_release=threading.Event();second_release=threading.Event()
    first_request=threading.Event();second_request=threading.Event()
    def record(kind,value):
        row={'kind':kind,'monotonic':time.monotonic(),'value':value}
        with lock:
            events.append(row)
            with (output/'events.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
    class Provider(http.server.BaseHTTPRequestHandler):
        protocol_version='HTTP/1.1'
        def log_message(self,*args):pass
        def do_POST(self):
            body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            number=len(requests)+1
            requests.append({'path':self.path,'model':body.get('model'),'reasoning':body.get('reasoning'),'number':number})
            record('provider_request',requests[-1])
            if number==1:first_request.set();assert first_release.wait(15)
            else:second_request.set();assert second_release.wait(15)
            rows=[{'type':'response.created','response':{'id':'response_'+str(number)}}]
            if number==1:
                rows.append({'type':'response.failed','response':{'id':'response_1','status':'failed','error':{'type':'server_error','code':'insufficient_quota' if args.scenario=='quota' else 'server_is_overloaded','message':'Injected local capacity fixture'}}})
            else:
                item={'id':'message_'+str(number),'type':'message','role':'assistant','status':'completed','content':[{'type':'output_text','text':'CAPACITY_NATIVE_RECOVERY_OK','annotations':[]}]}
                rows += [{'type':'response.output_item.done','output_index':0,'item':item},{'type':'response.completed','response':{'id':'response_'+str(number),'status':'completed','output':[item],'usage':{'input_tokens':1,'output_tokens':1,'total_tokens':2}}}]
            data=''.join('event: '+r['type']+'\ndata: '+json.dumps(r)+'\n\n' for r in rows).encode()
            self.send_response(200);self.send_header('Content-Type','text/event-stream');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data);self.wfile.flush()
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Provider)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    command=[args.codex,'app-server','--listen','stdio://']
    config={'model_provider':'capacity_probe','model':'gpt-6-luna','model_reasoning_effort':'xhigh','features.goals':True,'model_providers.capacity_probe.name':'Local capacity fixture','model_providers.capacity_probe.base_url':'http://127.0.0.1:'+str(server.server_port)+'/v1','model_providers.capacity_probe.wire_api':'responses','model_providers.capacity_probe.requires_openai_auth':False,'model_providers.capacity_probe.supports_websockets':False,'model_providers.capacity_probe.request_max_retries':0,'model_providers.capacity_probe.stream_max_retries':0,'analytics.enabled':False}
    for key,value in config.items():command+=['-c',key+'='+json.dumps(value)]
    (output/'config.json').write_text(json.dumps(config,indent=2)+'\n')
    server_log=(output/'app-server.stderr').open('w')
    proc=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=server_log,text=True,bufsize=1)
    incoming=queue.Queue()
    def reader():
        for line in proc.stdout:
            try:message=json.loads(line)
            except json.JSONDecodeError:record('unparsed_stdout',line);continue
            record('rpc_in',message);incoming.put(message)
    threading.Thread(target=reader,daemon=True).start()
    seq=0;watcher_thread=None;watcher_result={}
    rpc_lock=threading.RLock()
    def rpc_impl(method,params):
        nonlocal seq
        seq+=1;ident=seq;message={'id':ident,'method':method,'params':params};record('rpc_out',message)
        proc.stdin.write(json.dumps(message)+'\n');proc.stdin.flush();until=time.monotonic()+20
        while time.monotonic()<until:
            try:row=incoming.get(timeout=.2)
            except queue.Empty:
                if proc.poll() is not None:raise RuntimeError('native proxy exited')
                continue
            if row.get('id')==ident and ('result' in row or 'error' in row):
                if 'error' in row:raise RuntimeError(json.dumps(row))
                return row['result']
        raise RuntimeError('RPC timeout '+method)
    def rpc(method,params):
        with rpc_lock:return rpc_impl(method,params)
    def goal(thread):return rpc('thread/goal/get',{'threadId':thread})['goal']
    def goal_id(thread):
        # This DB belongs only to this disposable fixture host; never host data.
        with sqlite3.connect('file:/root/.codex/goals_1.sqlite?mode=ro',uri=True) as connection:
            return connection.execute('SELECT goal_id FROM thread_goals WHERE thread_id=?',(thread,)).fetchone()[0]
    def wait_goal(thread,status):
        until=time.monotonic()+15
        while time.monotonic()<until:
            value=goal(thread)
            if value and value['status']==status:return value
            time.sleep(.025)
        raise RuntimeError('Goal did not become '+status)
    result={'injected_provider':True,'external_model_calls':0,'real_host_version':subprocess.check_output([args.codex,'--version'],text=True).strip(),'watcher_integrated':args.recovery_script is not None,'scenario':args.scenario}
    try:
        rpc('initialize',{'clientInfo':{'name':'capacity-native-fixture','title':'Disposable capacity native fixture','version':'0.1'},'capabilities':{'experimentalApi':True}})
        proc.stdin.write(json.dumps({'method':'initialized','params':{}})+'\n');proc.stdin.flush()
        thread=rpc('thread/start',{'model':'gpt-6-luna','modelProvider':'capacity_probe','cwd':'/workspace','approvalPolicy':'never','sandbox':'read-only','config':{'model_reasoning_effort':'xhigh'}})['thread']['id']
        result['thread_id']=thread
        initial=rpc('thread/goal/set',{'threadId':thread,'objective':'In this injected fixture return CAPACITY_NATIVE_RECOVERY_OK; do not use any tools.','status':'active','tokenBudget':10000,'origin':'user'})['goal']
        initial_id=goal_id(thread);result['initial_goal']=initial;result['goal_id_before']=initial_id
        assert first_request.wait(10),'No native first sampling request'
        if args.recovery_script:
            spec=importlib.util.spec_from_file_location('capacity_retry_under_test',args.recovery_script)
            recovery=importlib.util.module_from_spec(spec);spec.loader.exec_module(recovery)
            recovery.emit=lambda event,**fields:record('watcher_event',{'event':event,**fields})
            class Adapter:
                def call(self,method,params):return rpc(method,params)
            options=argparse.Namespace(socket=Path('/tmp/stdio-fixture-endpoint'),thread_id=thread,
                max_elapsed_seconds=30,poll_seconds=.025,delay_seconds=.25,max_delay_seconds=1,
                jitter=0,retry_after_seconds=0,max_attempts=2,execute=True,one_recovery=True)
            def invoke():
                try:watcher_result['exit_code']=recovery.run(options,Adapter(),output/'watcher-state.json')
                except Exception as error:watcher_result['error']=repr(error)
            watcher_thread=threading.Thread(target=invoke,daemon=True);watcher_thread.start()
            result['watcher_transport']='prototype.run with serialized native stdio RPC adapter; not CLI socket end-to-end'
            until=time.monotonic()+10
            while not (output/'watcher-state.json').exists():
                if not watcher_thread.is_alive() or time.monotonic()>until:raise RuntimeError('watcher failed to arm: '+str(watcher_result))
                time.sleep(.025)
            result['watcher_running_before_capacity']=watcher_thread.is_alive()
        first_release.set()
        blocked=wait_goal(thread,'usageLimited' if args.scenario=='quota' else 'blocked');result['failure_goal']=blocked
        if args.scenario!='quota':result['blocked_goal']=blocked
        result['thread_after_failure']=rpc('thread/read',{'threadId':thread,'includeTurns':False})['thread']
        if args.scenario in ('pause','quota'):
            assert watcher_thread is not None,'negative controls require a recovery prototype'
            if args.scenario=='pause':
                until=time.monotonic()+5
                while not any(r['kind']=='watcher_event' and r['value']['event']=='planned' for r in events):
                    assert time.monotonic()<until,'watcher did not reach capacity backoff'
                    time.sleep(.005)
                rpc('thread/goal/set',{'threadId':thread,'status':'paused','origin':'user'})
                result['pause_during_backoff']=True
            watcher_thread.join(timeout=5);result['watcher_result']=watcher_result
            assert watcher_result.get('exit_code') in (0,2),watcher_result
            result['final_goal']=goal(thread);result['goal_id_after']=goal_id(thread)
            result['provider_requests']=requests
            result['turns']=[r['value']['params']['turn'] for r in events if r['kind']=='rpc_in' and r['value'].get('method')=='turn/completed']
            assert len(requests)==1
            assert result['goal_id_after']==initial_id
            assert sum(r['kind']=='rpc_out' and r['value']['method']=='thread/goal/set' and r['value']['params'].get('status')=='active' for r in events)==1
            assert not any(r['kind']=='watcher_event' and r['value']['event']=='recovery_observed' for r in events)
            assert result['final_goal']['status']==('paused' if args.scenario=='pause' else 'usageLimited')
            result['passed']=True
            print(json.dumps({'passed':True,'scenario':args.scenario,'resume_mutations':0,'provider_requests':1,'external_model_calls':0}))
            return
        if args.recovery_script:
            result['watcher_running_after_capacity']=watcher_thread.is_alive()
        else:rpc('thread/goal/set',{'threadId':thread,'status':'active','origin':'user'})
        assert second_request.wait(10),'No automatic native continuation after activation'
        if args.recovery_script:
            watcher_thread.join(timeout=10);result['watcher_exit_code']=watcher_result.get('exit_code');result['watcher_result']=watcher_result
            assert result['watcher_exit_code']==0,'watcher did not confirm recovery: '+str(watcher_result)
        resumed=goal(thread);result['resumed_goal']=resumed;result['goal_id_after']=goal_id(thread)
        assert resumed['status']=='active'
        # The fixture controller now pauses its own Goal, then releases the success
        # response. This prevents an uncompleted synthetic Goal from looping.
        rpc('thread/goal/set',{'threadId':thread,'status':'paused','origin':'user'})
        result['fixture_cleanup_paused_goal']=True;second_release.set()
        until=time.monotonic()+10
        while time.monotonic()<until:
            if any(r['kind']=='rpc_in' and r['value'].get('method')=='turn/completed' and r['value']['params'].get('turn',{}).get('status')=='completed' for r in events):break
            rpc('thread/read',{'threadId':thread,'includeTurns':False});time.sleep(.025)
        result['final_goal']=goal(thread)
        turns=[r['value']['params']['turn'] for r in events if r['kind']=='rpc_in' and r['value'].get('method')=='turn/completed']
        result['turns']=turns;result['provider_requests']=requests
        assert blocked['status']=='blocked'
        assert resumed['objective']==blocked['objective']==initial['objective']
        assert result['goal_id_after']==initial_id
        assert resumed['tokenBudget']==initial['tokenBudget']==10000
        assert len(requests)==2
        assert len({t['id'] for t in turns})==2
        assert [t['status'] for t in turns]==['failed','completed'],turns
        assert turns[0]['error']['codexErrorInfo']=='serverOverloaded',turns[0]
        assert all(r['model']=='gpt-6-luna' and r['reasoning']['effort']=='xhigh' for r in requests)
        assert not any(r['kind']=='rpc_out' and r['value']['method']=='turn/start' for r in events)
        result['passed']=True
    except Exception as error:
        result['passed']=False;result['error']=repr(error);result['provider_requests']=requests
        raise
    finally:
        (output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        first_release.set();second_release.set()
        for child in [proc]:
            child.terminate()
            try:child.wait(timeout=3)
            except subprocess.TimeoutExpired:child.kill();child.wait()
        server.shutdown();server_log.close()
    print(json.dumps({'passed':result['passed'],'watcher_integrated':result['watcher_integrated'],'provider_requests':len(requests),'same_goal_id':result['goal_id_before']==result['goal_id_after'],'external_model_calls':0}))


def docker(args):
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=False)
    source=Path(__file__).read_bytes();(output/'test-native-host.py').write_bytes(source)
    name='goal-prompt-capacity-'+uuid.uuid4().hex[:10]
    command=['docker','create','--name',name,'--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--tmpfs','/tmp:rw,exec,nosuid,size=256m','--tmpfs','/workspace:rw,nosuid,size=128m','--tmpfs','/root/.codex:rw,nosuid,mode=700,size=128m','--workdir','/workspace',args.image,'sleep','infinity']
    ident=subprocess.check_output(command,text=True).strip()
    result=None
    try:
        (output/'container-id.txt').write_text(ident+'\n')
        subprocess.run(['docker','start',ident],check=True,stdout=subprocess.DEVNULL)
        inspect=json.loads(subprocess.check_output(['docker','inspect',ident]))[0]
        policy={'image':inspect['Image'],'network':inspect['HostConfig']['NetworkMode'],'read_only':inspect['HostConfig']['ReadonlyRootfs'],'binds':inspect['HostConfig']['Binds'],'cap_drop':inspect['HostConfig']['CapDrop'],'security_opt':inspect['HostConfig']['SecurityOpt'],'mounts':inspect['Mounts']}
        assert policy['network']=='none' and policy['read_only'] and not policy['binds']
        (output/'container-policy.json').write_text(json.dumps(policy,indent=2)+'\n')
        inside=['docker','exec','-i',ident,'python3','-','--inside','--output','/tmp/native-run','--codex',args.codex,'--scenario',args.scenario]
        if args.recovery_script:
            script=args.recovery_script.read_bytes();(output/'capacity-retry.py').write_bytes(script)
            (output/'recovery-script.sha256').write_text(hashlib.sha256(script).hexdigest()+'\n')
            subprocess.run(['docker','exec','-i',ident,'python3','-c','import sys,pathlib;pathlib.Path("/tmp/capacity_retry.py").write_bytes(sys.stdin.buffer.read())'],input=script,check=True)
            inside+=['--recovery-script','/tmp/capacity_retry.py']
        with (output/'stdout.log').open('wb') as stdout,(output/'stderr.log').open('wb') as stderr:
            result=subprocess.run(inside,input=source,stdout=stdout,stderr=stderr,timeout=100)
    finally:
        try:
            with (output/'native-evidence.tar').open('wb') as archive:
                subprocess.run(['docker','exec',ident,'tar','-C','/tmp','-cf','-','native-run'],stdout=archive,stderr=subprocess.DEVNULL,timeout=10)
            copied=subprocess.run(['docker','exec',ident,'cat','/tmp/native-run/result.json'],capture_output=True,timeout=10)
            if copied.returncode==0:(output/'result.json').write_bytes(copied.stdout)
            with (output/'native-rollouts.tar').open('wb') as archive:
                subprocess.run(['docker','exec',ident,'tar','-C','/root/.codex','-cf','-','sessions'],stdout=archive,stderr=subprocess.DEVNULL,timeout=10)
        finally:
            try:
                subprocess.run(['docker','rm','-f',ident],stdout=subprocess.DEVNULL,check=True,timeout=10)
            except Exception:
                print('Owned container removal failed; inspect container-id.txt and remove only '+ident, file=sys.stderr)
                raise
    assert result is not None and result.returncode==0,'native test failed; inspect preserved artifacts'
    print((output/'stdout.log').read_text().strip())


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--image',help='Docker image built from the baseline-container profile')
    parser.add_argument('--inside',action='store_true',help=argparse.SUPPRESS)
    parser.add_argument('--codex',default='codex-upstream')
    parser.add_argument('--recovery-script',type=Path)
    parser.add_argument('--scenario',choices=['recovery','pause','quota'],default='recovery')
    args=parser.parse_args()
    if args.inside:native(args)
    else:
        if not args.image:parser.error('--image is required')
        docker(args)
