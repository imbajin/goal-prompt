import copy
import importlib.util
from pathlib import Path
import unittest
import json
import hashlib
import subprocess
import sys
import tempfile

spec=importlib.util.spec_from_file_location('outcomes',Path(__file__).with_name('audit-request-outcomes.py'))
outcomes=importlib.util.module_from_spec(spec);spec.loader.exec_module(outcomes)

def attempt(number,key='same'):
    return {'event':'accepted','counts':{'allowed':number,'upstream_requests':number},'request_sha256':key,'session_sha256':'s',
            'thread_sha256':'s','model':'gpt-6-luna','effort':'xhigh'}
def success(a):return {**a,'event':'completed','status':200}
def recovered():
    a=attempt(1);b=attempt(2)
    return [a,{'event':'broker_error','error_type':'URLError','counts':a['counts'],'request_sha256':'same'},
            {'event':'denied','status':502,'reason':'broker_request_failed','request_sha256':'same','counts':a['counts']},b,success(b)]

class Outcomes(unittest.TestCase):
    def test_recovered_failure(self):
        a,s,f=outcomes.reconcile(recovered());self.assertEqual((len(a),len(s),len(f)),(2,1,1))
    def test_overlapping_success_streams(self):
        a,b=attempt(1,'a'),attempt(2,'b');self.assertEqual(len(outcomes.reconcile([a,b,success(a),success(b)])[1]),2)
    def test_missing_or_changed_evidence_is_rejected(self):
        mutations=[]
        events=recovered();mutations.append(events[:-1])
        # Dropping the whole failed chain must not hide an unaccounted attempt.
        mutations.append(recovered()[3:])
        for index,key,value in ((1,'error_type','UnknownError'),(2,'status',403),(2,'request_sha256','other'),
                                (3,'request_sha256','other'),(3,'session_sha256','other'),(3,'effort','high'),(4,'status',500)):
            events=recovered();events[index][key]=value;mutations.append(events)
        events=recovered();events.append(success(attempt(3,'untracked')));mutations.append(events)
        for events in mutations:
            with self.subTest(events=events):
                with self.assertRaises(RuntimeError):outcomes.reconcile(events)
    def test_suffix_counter(self):
        a=attempt(219);self.assertEqual(len(outcomes.reconcile([a,success(a)],218)[0]),1)
    def test_archive_closure(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);a=attempt(1)
            a['thread_sha256']=a['session_sha256']=hashlib.sha256(b'native-id').hexdigest()
            (root/'broker-events.jsonl').write_text('\n'.join(json.dumps(e) for e in (a,success(a)))+'\n')
            command=[sys.executable,str(Path(outcomes.__file__)),str(root)]
            self.assertNotEqual(subprocess.run(command,capture_output=True).returncode,0)
            rollout=root/'rollout-test.jsonl';meta={'type':'session_meta','payload':{'id':'native-id'}}
            rollout.write_text(json.dumps(meta)+'\n')
            self.assertNotEqual(subprocess.run(command,capture_output=True).returncode,0)
            rollout.write_text(json.dumps(meta)+'\n'+json.dumps({'type':'token_usage_record'})+'\n')
            self.assertEqual(subprocess.run(command,capture_output=True).returncode,0)

if __name__=='__main__':unittest.main()
