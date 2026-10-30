#!/usr/bin/env python3
"""Archive completed Luna xhigh controls without replaying or changing verdicts."""
from pathlib import Path
from collections import Counter
import argparse
import hashlib
import json
import re
import shutil

REPO=Path(__file__).resolve().parents[3]
SECRET=re.compile(rb'(?:sk-(?:ant-)?[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,})')

def require(condition, message):
    if not condition:
        raise RuntimeError(message)

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def dump(path,value):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--invalid-run',type=Path,action='append',default=[])
    a=ap.parse_args();run=a.run.resolve();out=a.output.resolve();require(not out.exists(), 'Refusing to overwrite evidence')
    manifest=json.loads((run/'manifest.json').read_text());require(manifest.get('completed_utc') and manifest.get('all_isolation_audits_pass'), 'Required evaluation invariant failed')
    require(manifest['model']==manifest['judge_model']=='gpt-6-luna' and manifest['effort']==manifest['judge_effort']=='xhigh', 'Required evaluation invariant failed')
    require(manifest['with_skill_executed'] is False and manifest['skills']==[], 'Required evaluation invariant failed')
    spec=json.loads((run/'isolation.json').read_text())
    require(sha(run/'isolation.json')==manifest['isolation_sha256'], 'frozen isolation changed')
    require(all(spec['checks'][k]['exit_code']==0 for k in ('script_execution','tmp_execution_mount')), 'Required evaluation invariant failed')
    require(sha(run/'run-baseline.py')==manifest['runner_sha256'], 'Required evaluation invariant failed')
    require(sha(run/'bin/docker')==manifest['docker_wrapper_sha256'], 'Required evaluation invariant failed')
    if 'request_auditor_sha256' in manifest:
        require(sha(run/'audit-baseline-requests.py')==manifest['request_auditor_sha256'], 'frozen request auditor changed')
    for key,filename in (('pilot_gate_sha256','pilot-request-coverage.json'),('pilot_broker_events_sha256','pilot-broker-events.jsonl')):
        if key in manifest:require(sha(run/filename)==manifest[key], 'pilot gate evidence changed')
    for rel,expected in manifest['snapshot_sha256'].items():require(sha(run/'snapshot'/rel)==expected, rel)
    cases=json.loads((run/'cases-combined.json').read_text());require(len(cases)==30 and {c['case_id'] for c in cases}==set(manifest['case_ids']), 'Required evaluation invariant failed')
    native=[]
    for batch in ('pilot','remaining'):
        for source in sorted((run/batch).glob('iteration-*/result.json')):
            native.extend(json.loads(source.read_text())['case_results'])
    require(native==cases, 'combined cases differ from native raw result.json')
    require(all(c['configuration']=='without_skill' for c in cases), 'Required evaluation invariant failed')
    for batch in ('pilot','remaining'):
        audit_name=manifest.get('isolation_audit_files',{}).get(batch,'isolation-audit.json')
        require(audit_name in ('isolation-audit.json','isolation-audit-reviewed.json'),'unexpected audit path')
        require(json.loads((run/batch/audit_name).read_text())['valid'], 'Required evaluation invariant failed')
    require(json.loads((run/'broker-audit.json').read_text())['valid'], 'Required evaluation invariant failed')
    coverage=json.loads((run/'request-coverage.json').read_text())
    require(coverage['valid'] and coverage['phase']=='final', 'final request coverage invalid or incomplete')
    require(sha(run/'broker-events.jsonl')==coverage['broker_events_sha256'], 'broker events changed after audit')
    require(sha(run/'audit-baseline-requests.py')==coverage['auditor_sha256'], 'auditor source changed after audit')
    old={m[0]:m[1] for m in re.findall(r'^\| ([a-z0-9-]+) \| (?:PASS|FAIL) \| (PASS|FAIL|ERROR) \|$',(REPO/'evals/skill-up/README.md').read_text(),re.M)}
    require(set(old)==set(manifest['case_ids']) and Counter(old.values())==Counter(PASS=6,FAIL=23,ERROR=1), 'Required evaluation invariant failed')
    out.mkdir(parents=True);files=[]
    allowed_roots=[run,*[p.resolve() for p in a.invalid_run]]
    def archive(source,rel):
        source=source.resolve();require(any(source.is_relative_to(p) for p in allowed_roots) and source.is_file(), 'Required evaluation invariant failed')
        data=source.read_bytes();require(len(data)<4*1024*1024 and not SECRET.search(data), str(source))
        target=out/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
        files.append({'archive':str(rel),'original_path':str(source),'sha256':sha(source),'bytes':len(data)})
    for rel in ('manifest.json','isolation.json','broker-audit.json','broker-events.jsonl','request-coverage.json','audit-baseline-requests.py','cases-combined.json','docker-events.jsonl','without-only.patch','run-baseline.py','bin/docker','validate.log','dry-run.log'):
        archive(run/rel,Path('run')/rel)
    for rel in ('manifest-before-audit-correction.json','finalize-reviewed-audit.py','reviewed-audit-source.py','request-audit.log'):
        if (run/rel).is_file():archive(run/rel,Path('run')/rel)
    for source in sorted((run/'snapshot').rglob('*')):
        if source.is_file():archive(source,Path('run')/source.relative_to(run))
    for source in sorted((run/'container-audits').glob('*.json')):archive(source,Path('run')/source.relative_to(run))
    for source in sorted((run/'preflight').glob('*')):
        if source.is_file():archive(source,Path('run')/source.relative_to(run))
    for batch in ('pilot','remaining'):
        for suffix in ('-request-coverage.json','-broker-events.jsonl'):
            source=run/(batch+suffix)
            if source.is_file():archive(source,Path('run')/source.name)
    invalid=[]
    for attempt in a.invalid_run:
        attempt=attempt.resolve();require(attempt!=run and not json.loads((attempt/'manifest.json').read_text()).get('completed_utc'), 'Required evaluation invariant failed')
        for source in attempt.rglob('*'):
            if source.is_file() and (source.name in ('manifest.json','isolation.json','result.json','grading.json','evaluation.json','response.md','stdout.json','broker-events-at-stop.jsonl','broker-events-all-invalid.jsonl','broker-events.jsonl') or source.name.endswith('-events.jsonl') or source.name in ('pilot.log','remaining.log')):
                archive(source,Path('invalid-attempts')/attempt.name/source.relative_to(attempt))
        invalid_rollouts=[{'original_path':str(p),'sha256':sha(p),'bytes':p.stat().st_size}
                          for p in attempt.rglob('rollout-*.jsonl')]
        invalid.append({'directory':str(attempt),'excluded_from_quality_counts':True,
                        'raw_rollouts_local':invalid_rollouts,
                        'limits':'Startup/download errors may have no captured rollout; never count them as quality cases.'})
    raw_transcripts=[]
    for batch in ('pilot','remaining'):
        for rel in (batch+'-command.json',batch+'-events.jsonl',batch+'.log',batch+'/isolation-audit.json'):
            archive(run/rel,Path('run')/rel)
        source=run/batch/'isolation-audit-reviewed.json'
        if source.is_file():archive(source,Path('run')/source.relative_to(run))
        for source in (run/batch).glob('iteration-*/result.json'):archive(source,Path('run')/source.relative_to(run))
        for source in (run/batch).rglob('rollout-*.jsonl'):
            raw_transcripts.append({'original_path':str(source),'sha256':sha(source),'bytes':source.stat().st_size})
        for source in (run/batch).rglob('*'):
            if source.is_file() and (source.name in ('grading.json','evaluation.json','eval_metadata.json','response.md','stdout.json') or '/outputs/workspace/.goal-task/' in str(source)):
                archive(source,Path('run')/source.relative_to(run))
    rows=[]
    for c in cases:
        rel=Path('cases')/c['case_id'];dump(out/rel/'result.json',c)
        (out/rel/'response.md').write_text(c.get('response','')+'\n')
        failed=[x for x in (c.get('grading') or {}).get('assertion_results',[]) if not x.get('passed')]
        rows.append({'case_id':c['case_id'],'historical_5_6_luna_high':old[c['case_id']],'gpt_6_luna_xhigh':c['status'],
                     'failed_assertions':failed,'error':c.get('error'),'evidence':str(rel/'result.json')})
    counts=dict(Counter(c['status'] for c in cases));transitions=dict(Counter(old[c['case_id']]+' -> '+c['status'] for c in cases))
    summary={'run':str(run),'status_counts':counts,'historical_status_counts':dict(Counter(old.values())),
             'invalid_attempts':invalid,
             'audit_correction':manifest.get('audit_correction'),
             'transitions':transitions,'cases':rows,'raw_rollouts_local':raw_transcripts,
             'limits':'Descriptive comparison only: model, effort, judge, tool, deterministic graders and isolation differ; no new with-Skill group. No verdict replay or override.'}
    dump(out/'summary.json',summary)
    lines=['# Luna xhigh without-Skill 原始结果','',f'原30例：{counts}。原始判分保留，未重判、未覆盖FAIL。','',
           '历史5.6 Luna high为6 PASS / 23 FAIL / 1 ERROR；模型、深度、Judge、工具和隔离方式不同，仅作描述性比较。','',
           '| Case | 5.6 Luna high | 6 Luna xhigh | 原始输出与判分 |','| --- | --- | --- | --- |']
    for r in rows:lines.append(f"| {r['case_id']} | {r['historical_5_6_luna_high']} | {r['gpt_6_luna_xhigh']} | [证据]({r['evidence']}) / [输出](cases/{r['case_id']}/response.md) |")
    lines+=['','完整rollout保存在本地运行目录，路径和哈希见 [summary.json](summary.json)。',
            '运行配置、实际输出、确定性Judge脚本、代理元数据和逐容器审计均随 [归档清单](archive-integrity.json) 保留。',
            '', '无效尝试的本地rollout路径、哈希及未捕获限制也列于summary.json；未将它们拼入最终30例。']
    (out/'summary.md').write_text('\n'.join(lines)+'\n');print(json.dumps({'counts':counts,'transitions':transitions,'archived_files':len(files)},ensure_ascii=False))
    copied={x['archive'] for x in files}
    generated=[{'archive':str(p.relative_to(out)),'sha256':sha(p),'bytes':p.stat().st_size}
               for p in out.rglob('*') if p.is_file() and str(p.relative_to(out)) not in copied]
    dump(out/'archive-integrity.json',{'files':files,'generated_files':generated,'raw_rollouts_local':raw_transcripts})
if __name__=='__main__':main()
