#!/usr/bin/env python3
"""Reconcile successful responses and explicitly logged, recovered broker 502s.

Unknown errors, missing terminal events, unarchived sessions, and unexplained
token counts remain failures. This does not rewrite the original strict audit.
"""
from pathlib import Path
from collections import Counter
import argparse
import hashlib
import json

def require(value,message):
    if not value:raise RuntimeError(message)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def reconcile(events,starting_counter=0):
    accepted=[e for e in events if e.get('event')=='accepted']
    require(accepted,'no accepted requests')
    terminals=[e for e in events if e.get('event')=='completed'];failed=[]
    for event in accepted:
        require(event['model']=='gpt-6-luna' and event['effort']=='xhigh','wrong model/effort')
        require(event['thread_sha256']==event['session_sha256'],'unexpected subthread')
    require(all(e.get('status')==200 for e in terminals),'unexpected upstream status')
    # Completed streams may overlap the next request. Successes use full
    # session/request multisets; the five observed failures have a stricter
    # local accepted -> URLError -> terminal502 -> identical retry chain.
    for index,event in enumerate(events):
        if event.get('event')!='broker_error':continue
        require(event.get('error_type')=='URLError' and index>0 and index+2<len(events),'unexplained broker outcome')
        attempt=events[index-1];denied=events[index+1];retry=events[index+2]
        require(attempt.get('event')=='accepted','ambiguous failed attempt ownership')
        require(event['counts']==attempt['counts'] and event['request_sha256']==attempt['request_sha256'],'broker error identity mismatch')
        require(denied.get('event')=='denied' and denied.get('status')==502 and denied.get('reason')=='broker_request_failed','no explicit terminal 502')
        require(denied['request_sha256']==attempt['request_sha256'] and denied['counts']['allowed']==attempt['counts']['allowed'],'502 identity mismatch')
        require(retry.get('event')=='accepted','recorded error not followed by retry')
        for key in ('request_sha256','session_sha256','thread_sha256','model','effort'):
            require(retry[key]==attempt[key],'retry changed request/session/config')
        failed.append({**attempt,'terminal_status':502,'error_type':'URLError','retry_allowed_counter':retry['counts']['allowed']})
    key=lambda e:(e['session_sha256'],e['request_sha256'])
    require(Counter(map(key,accepted))==Counter(map(key,terminals))+Counter(map(key,failed)),'request terminal multiset not closed')
    require([e['counts']['allowed'] for e in accepted]==list(range(starting_counter+1,starting_counter+1+len(accepted))),'missing/duplicate/reordered attempt counter')
    require(all(e['counts']['upstream_requests']==e['counts']['allowed'] for e in accepted),'upstream counter mismatch')
    success_keys=set(map(key,terminals))
    require(all(key(e) in success_keys for e in failed),'retry never succeeded')
    require(sum(e.get('event')=='denied' and e.get('status')==502 for e in events)==len(failed),'orphan 502')
    return accepted,terminals,failed

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('run',type=Path);ap.add_argument('--output',type=Path);a=ap.parse_args();root=a.run.resolve()
    output=a.output or root/'request-outcomes.json';require(not output.exists(),'refuse overwriting an existing audit')
    prefix=root/'broker-events-before.jsonl';starting_counter=0
    if prefix.exists():
        before=[json.loads(x) for x in prefix.read_text().splitlines()]
        starting_counter=max((e.get('counts',{}).get('allowed',0) for e in before),default=0)
        if starting_counter:
            prefix_accepted,_,_=reconcile(before)
            require(prefix_accepted[-1]['counts']['allowed']==starting_counter,'prefix counter is not a closed complete history')
    accepted,completed,failed=reconcile([json.loads(x) for x in (root/'broker-events.jsonl').read_text().splitlines()],starting_counter)
    counts=Counter(e['session_sha256'] for e in accepted);success=Counter(e['session_sha256'] for e in completed);failures=Counter(e['session_sha256'] for e in failed)
    sessions={}
    for path in root.rglob('rollout-*.jsonl'):
        data=[json.loads(x) for x in path.read_text().splitlines()];meta=next(e['payload'] for e in data if e.get('type')=='session_meta')
        key=hashlib.sha256(meta['id'].encode()).hexdigest();require(key not in sessions,'duplicate archived session')
        records=sum(e.get('type')=='token_usage_record' for e in data)
        require(records==success[key] and counts[key]==records+failures[key],'unexplained per-session request count')
        sessions[key]={'rollout':str(path.relative_to(root)),'sha256':sha(path),'accepted_requests':counts[key],
                       'completed_200_requests':success[key],'recorded_failed_attempts':failures[key],'native_token_usage_records':records}
    require(set(sessions)==set(counts),'unarchived or unexpected session')
    value={'valid':True,'phase':'final','accepted_requests':len(accepted),'completed_200_requests':len(completed),
           'native_token_usage_records':sum(v['native_token_usage_records'] for v in sessions.values()),
           'recorded_failed_attempts':len(failed),'failed_attempts':failed,'sessions':sessions,'findings':[],
           'starting_allowed_counter':starting_counter,'ending_allowed_counter':starting_counter+len(accepted),
           'prefix_input':{'path':str(prefix),'sha256':sha(prefix),'closed_history_verified':True} if prefix.exists() else None,
           'broker_events_sha256':sha(root/'broker-events.jsonl'),'auditor_sha256':sha(Path(__file__)),
           'limits':'Only observed serial URLError->explicit502->identical request retry->200 is accounted; transport failure is not proven model capacity. Original strict audit retained. Session headers are not strong authentication against malicious root.'}
    output.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:value[k] for k in ('valid','accepted_requests','completed_200_requests','native_token_usage_records','recorded_failed_attempts')}))

if __name__=='__main__':main()
