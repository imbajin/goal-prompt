#!/usr/bin/env python3
"""Match every accepted broker request to archived native token usage records."""
from pathlib import Path
from collections import Counter
import argparse
import hashlib
import json


def require(condition, message):
    if not condition:
        raise RuntimeError(message)

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('run',type=Path);ap.add_argument('--partial',action='store_true');a=ap.parse_args();root=a.run.resolve()
    manifest=json.loads((root/'manifest.json').read_text());require(a.partial or manifest.get('completed_utc') or manifest.get('cases_finished_utc'), 'cohort still incomplete')
    events=[json.loads(line) for line in (root/'broker-events.jsonl').read_text().splitlines()]
    accepted=[e for e in events if e.get('event')=='accepted'];counts=Counter(e['session_sha256'] for e in accepted)
    require(accepted, 'no real accepted requests')
    completed=[e for e in events if e.get('event')=='completed' and e.get('status')==200]
    request_key=lambda e:(e.get('session_sha256'),e.get('request_sha256'))
    findings=[];sessions={}
    if Counter(map(request_key,accepted))!=Counter(map(request_key,completed)):
        findings.append({'reason':'accepted_completed_request_hash_mismatch'})
    for path in root.rglob('rollout-*.jsonl'):
        data=[json.loads(line) for line in path.read_text().splitlines()]
        meta=next(e['payload'] for e in data if e.get('type')=='session_meta')
        key=hashlib.sha256(meta['id'].encode()).hexdigest()
        require(key not in sessions, 'duplicate archived session; review cumulative rollout before counting')
        records=sum(e.get('type')=='token_usage_record' for e in data)
        sessions[key]={'rollout':str(path.relative_to(root)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                       'accepted_requests':counts[key],'native_token_usage_records':records}
        if counts[key]!=records:findings.append({'session_sha256':key,'reason':'request_count_mismatch'})
    for key in counts:
        if key not in sessions:findings.append({'session_sha256':key,'reason':'unarchived_session'})
    if any(e.get('model')!='gpt-6-luna' or e.get('effort')!='xhigh' for e in accepted):findings.append({'reason':'wrong_model_or_effort'})
    if any(e.get('thread_sha256')!=e.get('session_sha256') for e in accepted):findings.append({'reason':'unexpected_subthread'})
    value={'valid':not findings,'phase':'partial' if a.partial else 'final','accepted_requests':len(accepted),'native_token_usage_records':sum(s['native_token_usage_records'] for s in sessions.values()),
           'completed_200_requests':len(completed),'auditor_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
           'broker_events_sha256':hashlib.sha256((root/'broker-events.jsonl').read_bytes()).hexdigest(),
           'sessions':sessions,'findings':findings,
           'limits':'Exact count/session reconciliation plus transcript command audit; session headers are not strong authentication against malicious in-container root.'}
    (root/'request-coverage.json').write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    require(value['valid'], 'request coverage mismatch: preserve evidence and investigate before using cohort')
    print(json.dumps({'valid':True,'requests':len(accepted),'sessions':len(sessions)}))
if __name__=='__main__':main()
