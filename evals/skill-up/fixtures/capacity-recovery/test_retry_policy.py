import argparse
import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('retry', Path(__file__).with_name('retry_policy.py'))
retry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(retry)


class Clock:
    def __init__(self, change=None):
        self.now = 0
        self.change = change
    def monotonic(self): return self.now
    def sleep(self, seconds):
        self.now += seconds
        if self.change:
            change, self.change = self.change, None
            change()


class Host:
    def __init__(self):
        self.goal = {'threadId': 'test', 'objective': 'isolated fixture', 'createdAt': 1,
                     'updatedAt': 2, 'tokenBudget': 1000, 'tokensUsed': 0,
                     'timeUsedSeconds': 0, 'status': 'active'}
        self.turn = {'id': 'failure-0', 'status': 'inProgress', 'error': None}
        self.goal_reads = 0
        self.next_error = 'serverOverloaded'
        self.configuration = {'model': 'gpt-6-luna', 'modelProvider': 'fixture', 'reasoningEffort': 'xhigh'}
        self.runtime = 'idle'
        self.queued = []
        self.sets = []
        self.behavior = 'success'
        self.before_set = None
    def call(self, method, params):
        if method == 'thread/goal/get':
            self.goal_reads += 1
            if self.goal_reads == 2 and self.goal['status'] == 'active' and self.turn['status'] == 'inProgress':
                self.goal['status'] = 'blocked'
                self.turn = {'id': 'failure-0', 'status': 'failed', 'completedAt': 2,
                             'error': {'codexErrorInfo': self.next_error}}
            return {'goal': copy.deepcopy(self.goal)}
        if method == 'thread/read': return {'thread': {'status': {'type': self.runtime}, **self.configuration}}
        if method == 'thread/turns/list': return {'data': [copy.deepcopy(self.turn)]}
        if method == 'thread/queue/list':
            if self.behavior == 'queue_error': raise RuntimeError('unsupported')
            return {'data': copy.deepcopy(self.queued)}
        if method == 'thread/goal/set':
            if self.before_set: self.before_set()
            self.sets.append(copy.deepcopy(params))
            self.goal['status'] = 'active'
            if self.behavior != 'no_new_turn':
                self.turn = {'id': 'continued-' + str(len(self.sets)), 'status': 'completed', 'error': None}
            if self.behavior == 'repeated_capacity':
                self.goal['status'] = 'blocked'
                self.turn = {'id': 'failure-' + str(len(self.sets)), 'status': 'failed',
                             'completedAt': 2, 'error': {'codexErrorInfo': 'serverOverloaded'}}
            if self.behavior == 'lost_reply': raise TimeoutError('ack lost')
            return {'goal': copy.deepcopy(self.goal)}
        raise AssertionError(method)


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.ledger = Path(self.temp.name) / 'ledger.json'
        self.host = Host()
        self.args = argparse.Namespace(thread_id='test', socket=Path('/fixture.sock'),
            delay_seconds=1, max_delay_seconds=20, jitter=0, retry_after_seconds=0,
            max_attempts=3, max_elapsed_seconds=60, poll_seconds=.25,
            execute=True, one_recovery=True)
    def tearDown(self): self.temp.cleanup()
    def run_policy(self, clock=None):
        clock = clock or Clock()
        output = io.StringIO()
        with patch.object(retry.time, 'monotonic', clock.monotonic), \
             patch.object(retry.time, 'sleep', clock.sleep), contextlib.redirect_stdout(output):
            code = retry.run(self.args, self.host, self.ledger)
        return code, [json.loads(line) for line in output.getvalue().splitlines()]
    def test_recovery_preserves_objective_budget_and_observes_turn(self):
        original = copy.deepcopy(self.host.goal)
        code, events = self.run_policy()
        self.assertEqual(code, 0)
        self.assertEqual(self.host.sets, [{'threadId': 'test', 'status': 'active', 'origin': 'user'}])
        self.assertEqual(self.host.goal['objective'], original['objective'])
        self.assertEqual(self.host.goal['tokenBudget'], original['tokenBudget'])
        self.assertEqual(events[-1]['event'], 'recovery_observed')
    def test_noncapacity_blocked_never_resumes(self):
        self.host.next_error = 'usageLimitExceeded'
        self.assertEqual(self.run_policy()[0], 2)
        self.assertEqual(self.host.sets, [])
    def test_user_paused_never_resumes(self):
        self.host.goal['status'] = 'paused'
        self.assertEqual(self.run_policy()[0], 0)
        self.assertEqual(self.host.sets, [])
    def test_queued_input_never_resumes(self):
        self.host.queued = [{'id': 'user-work'}]
        self.assertEqual(self.run_policy()[0], 2)
        self.assertEqual(self.host.sets, [])
    def test_user_pause_during_backoff_cancels(self):
        clock = Clock(lambda: self.host.goal.update(status='paused'))
        self.assertEqual(self.run_policy(clock)[0], 2)
        self.assertEqual(self.host.sets, [])
    def test_replaced_goal_during_backoff_cancels(self):
        clock = Clock(lambda: self.host.goal.update(objective='new task'))
        self.assertEqual(self.run_policy(clock)[0], 2)
        self.assertEqual(self.host.sets, [])
    def test_observe_does_not_write_host(self):
        self.args.execute = False
        self.assertEqual(self.run_policy()[0], 0)
        self.assertEqual(self.host.sets, [])
    def test_lost_response_prevents_blind_retry_after_restart(self):
        self.host.behavior = 'lost_reply'
        self.assertEqual(self.run_policy()[0], 4)
        self.assertEqual(self.run_policy()[0], 4)
        self.assertEqual(len(self.host.sets), 1)
        self.assertEqual(json.loads(self.ledger.read_text())['status'], 'uncertain')
    def test_no_new_turn_is_not_reported_as_success(self):
        self.host.behavior = 'no_new_turn'
        code, events = self.run_policy()
        self.assertEqual(code, 4)
        self.assertFalse(any(e['event'] == 'recovery_observed' for e in events))
    def test_repeated_capacity_obeys_exponential_wait_and_count(self):
        self.args.one_recovery = False
        self.host.behavior = 'repeated_capacity'
        code, events = self.run_policy()
        self.assertEqual(code, 3)
        self.assertEqual(len(self.host.sets), 3)
        self.assertEqual([e['delay_seconds'] for e in events if e['event'] == 'planned'], [1, 3, 9])
    def test_deadline_does_not_shorten_configured_retry_hint(self):
        self.args.retry_after_seconds = 120
        code, _ = self.run_policy()
        self.assertEqual(code, 3)
        self.assertEqual(self.host.sets, [])
    def test_unknown_queue_capability_fails_closed(self):
        self.host.behavior = 'queue_error'
        with self.assertRaises(RuntimeError): self.run_policy()
        self.assertEqual(self.host.sets, [])
    def test_model_change_during_backoff_cancels(self):
        clock = Clock(lambda: self.host.configuration.update(model='changed-model'))
        self.assertEqual(self.run_policy(clock)[0], 2)
        self.assertEqual(self.host.sets, [])
    def test_existing_blocked_state_cannot_be_armed(self):
        self.host.goal['status'] = 'blocked'
        self.host.turn = {'id': 'old-capacity', 'status': 'failed', 'completedAt': 2,
                          'error': {'codexErrorInfo': 'serverOverloaded'}}
        self.assertEqual(self.run_policy()[0], 2)
        self.assertEqual(self.host.sets, [])
    def test_post_failure_goal_change_is_not_capacity_proof(self):
        self.host.goal['updatedAt'] = 200
        self.assertEqual(self.run_policy()[0], 2)
        self.assertEqual(self.host.sets, [])
    def test_defaults_are_exactly_5_15_30_minutes(self):
        self.host.behavior = 'repeated_capacity'
        self.args = retry.options('test', '/fixture.sock', execute=True)
        clock = Clock()
        code, events = self.run_policy(clock)
        self.assertEqual(code, 3)
        self.assertEqual([e['delay_seconds'] for e in events if e['event']=='planned'], [300,900,1800])
        self.assertEqual(len(self.host.sets), 3)
        self.assertEqual(clock.now, 3000)
    def test_invalid_time_limits_are_rejected_without_host_calls(self):
        for options in ({'delay_seconds': 0}, {'jitter': -1}, {'max_attempts': 0},
                        {'max_elapsed_seconds': float('inf')}):
            with self.assertRaises(ValueError):
                retry.options('test', '/fixture.sock', **options)
        self.assertEqual(self.host.sets, [])
    def test_known_get_set_race_is_exposed_not_claimed_fixed(self):
        self.host.before_set = lambda: self.host.goal.update(status='paused')
        code, _ = self.run_policy()
        self.assertEqual(code, 0)
        self.assertEqual(self.host.goal['status'], 'active')
        self.assertEqual(len(self.host.sets), 1)
        # This is a demonstrated limitation, not a passing safety guarantee.


if __name__ == '__main__':
    unittest.main()
