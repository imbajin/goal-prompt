"""Laboratory retry-policy fixture; not an installed Skill or Desktop client.

Use only through the disposable native-host fixture or the in-memory tests.
No transport, credentials, daemon startup, or model calls are provided here.
The host lacks CAS; the deliberately tested final GET/SET race remains.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import random
import time
from types import SimpleNamespace


def options(thread_id, endpoint, **overrides):
    """Return validated test-policy defaults: 5, 15, 30 minutes, three attempts."""
    policy = dict(delay_seconds=300, max_delay_seconds=1800, jitter=0,
                  retry_after_seconds=0, max_attempts=3, max_elapsed_seconds=3600,
                  poll_seconds=5, execute=False, one_recovery=False)
    if set(overrides) - policy.keys():
        raise ValueError('unknown policy option')
    policy.update(overrides)
    for key in ('delay_seconds','max_delay_seconds','max_elapsed_seconds','poll_seconds'):
        if not math.isfinite(policy[key]) or policy[key] <= 0:
            raise ValueError('positive finite time limits required')
    if not math.isfinite(policy['retry_after_seconds']) or policy['retry_after_seconds'] < 0:
        raise ValueError('retry hint must be finite and non-negative')
    if not math.isfinite(policy['jitter']) or not 0 <= policy['jitter'] <= 1:
        raise ValueError('jitter must be between zero and one')
    if not isinstance(policy['max_attempts'], int) or policy['max_attempts'] < 1:
        raise ValueError('positive integer attempt limit required')
    return SimpleNamespace(thread_id=thread_id, socket=Path(endpoint), **policy)


def emit(event, **fields):
    print(json.dumps({'event': event, **fields}, sort_keys=True), flush=True)

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()

def snapshot(rpc, thread):
    goal = rpc.call('thread/goal/get', {'threadId': thread})['goal']
    state = rpc.call('thread/read', {'threadId': thread, 'includeTurns': False})['thread']
    turns = rpc.call('thread/turns/list', {'threadId': thread, 'limit': 1,
                     'sortDirection': 'desc', 'itemsView': 'summary'})['data']
    queued = rpc.call('thread/queue/list', {'threadId': thread, 'limit': 1})['data']
    return {'goal': goal, 'runtime': state['status']['type'], 'queued': bool(queued),
            'configuration': {k: state.get(k) for k in ('model', 'modelProvider', 'reasoningEffort')},
            'turn': turns[0] if turns else None}

def binding(snap):
    goal = snap['goal']
    if not goal or not all(k in goal for k in ('threadId', 'objective', 'createdAt', 'tokenBudget')):
        raise RuntimeError('no identifiable goal')
    return digest({'goal': {k: goal[k] for k in ('threadId', 'objective', 'createdAt', 'tokenBudget')},
                   'configuration': snap['configuration']})

def failure(snap):
    turn = snap['turn']
    return bool(snap['goal'] and snap['goal']['status'] == 'blocked'
                and snap['runtime'] in ('idle', 'systemError') and not snap['queued'] and turn
                and turn['status'] == 'failed' and turn.get('error')
                and turn['error'].get('codexErrorInfo') == 'serverOverloaded'
                and isinstance(turn.get('completedAt'), (int, float))
                and snap['goal']['updatedAt'] <= turn['completedAt'])

def unchanged(original, current):
    return (current['goal'] == original['goal'] and current['turn'] == original['turn']
            and current['runtime'] == original['runtime'] and current['queued'] == original['queued']
            and current['configuration'] == original['configuration'])

def save(path, record):
    temp = path.with_name(path.name + '.' + str(os.getpid()) + '.tmp')
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(record, stream, sort_keys=True)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if temp.exists():
            temp.unlink()

def run(args, rpc, ledger):
    started = time.monotonic()
    deadline = started + args.max_elapsed_seconds
    initial = snapshot(rpc, args.thread_id)
    identity = binding(initial)
    if initial['goal']['status'] not in ('active', 'blocked'):
        emit('stopped', status=initial['goal']['status'])
        return 0
    if args.execute and initial['goal']['status'] != 'active':
        emit('not_armed', reason='start while goal is active; existing blocked cause is ambiguous')
        return 2
    if args.execute and any(value is None for value in initial['configuration'].values()):
        emit('not_armed', reason='runtime configuration is not observable')
        return 2
    seen_active_turns = set()
    if initial['goal']['status'] == 'active' and initial['turn'] and initial['turn']['status'] == 'inProgress':
        seen_active_turns.add(initial['turn']['id'])
    prior = json.loads(ledger.read_text()) if ledger.exists() else None
    owner = {'schema': 1, 'thread': args.thread_id, 'socket_hash': digest(str(args.socket)),
             'goal_binding': identity}
    if prior:
        if any(prior.get(k) != v for k, v in owner.items()):
            raise RuntimeError('ledger belongs to another goal or socket')
        if prior.get('status') in ('dispatched', 'uncertain'):
            emit('uncertain_prior_action', action='inspect host before rearming')
            return 4
    record = prior or {**owner, 'status': 'watching', 'attempts': []}
    save(ledger, record)
    while time.monotonic() < deadline:
        current = snapshot(rpc, args.thread_id)
        if not current['goal'] or binding(current) != identity:
            emit('cancelled', reason='goal changed or cleared')
            return 2
        if current['goal']['status'] not in ('active', 'blocked'):
            emit('stopped', status=current['goal']['status'])
            return 0
        if current['goal']['status'] == 'active' and current['turn'] and current['turn']['status'] == 'inProgress':
            seen_active_turns.add(current['turn']['id'])
        if not failure(current):
            if current['goal']['status'] == 'blocked':
                emit('stopped', reason='blocked without verified terminal capacity failure')
                return 2
            time.sleep(min(args.poll_seconds, max(0, deadline - time.monotonic())))
            continue
        failed_turn = current['turn']['id']
        if args.execute and failed_turn not in seen_active_turns:
            emit('stopped', reason='failure was not observed on an armed active turn')
            return 2
        if any(a['failed_turn'] == failed_turn for a in record['attempts']):
            emit('stopped', reason='already dispatched for this failure')
            return 4
        count = len(record['attempts'])
        if count >= args.max_attempts:
            emit('exhausted', attempts=count)
            return 3
        delay = max(args.retry_after_seconds,
                    min(args.max_delay_seconds, args.delay_seconds * (3 ** count)))
        delay += random.uniform(0, delay * args.jitter)
        emit('planned', failed_turn=failed_turn, delay_seconds=delay,
             mode='best_effort' if args.execute else 'observe')
        if not args.execute:
            return 0
        due = time.monotonic() + delay
        if due >= deadline:
            emit('exhausted', reason='backoff exceeds total deadline')
            return 3
        while time.monotonic() < due:
            time.sleep(min(args.poll_seconds, max(0, due - time.monotonic())))
            if not unchanged(current, snapshot(rpc, args.thread_id)):
                emit('cancelled', reason='host state changed during backoff')
                return 2
        # This deliberately does not claim atomicity: the host API lacks CAS.
        if time.monotonic() >= deadline or not unchanged(current, snapshot(rpc, args.thread_id)):
            emit('cancelled', reason='final precondition changed')
            return 2
        record['attempts'].append({'failed_turn': failed_turn, 'at': time.time()})
        record['status'] = 'dispatched'
        save(ledger, record)
        try:
            rpc.call('thread/goal/set', {'threadId': args.thread_id, 'status': 'active',
                                        'origin': 'user'})
            verify_deadline = min(deadline, time.monotonic() + 10)
            while time.monotonic() < verify_deadline:
                updated = snapshot(rpc, args.thread_id)
                if not updated['goal'] or binding(updated) != identity:
                    raise RuntimeError('goal identity changed after dispatch')
                turn = updated['turn']
                if turn and turn['id'] != failed_turn:
                    seen_active_turns.add(turn['id'])
                    record['status'] = 'observed_new_turn'
                    record['attempts'][-1]['new_turn'] = turn['id']
                    save(ledger, record)
                    emit('recovery_observed', failed_turn=failed_turn, new_turn=turn['id'],
                         goal_status=updated['goal']['status'])
                    if args.one_recovery:
                        return 0
                    break
                time.sleep(args.poll_seconds)
            else:
                raise TimeoutError('activation acknowledged but no new turn observed')
        except Exception:
            record['status'] = 'uncertain'
            save(ledger, record)
            emit('uncertain_action', action='query host; do not blindly resend')
            return 4
    emit('exhausted', reason='total deadline')
    return 3

if __name__ == '__main__':
    raise SystemExit('Test fixture only: use test-native-host.py; no Desktop connection is available.')
