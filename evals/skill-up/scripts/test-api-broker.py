"""Exercise real loopback HTTP error responses with synthetic auth and no upstream."""
import contextlib
import http.client
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch, Mock
import urllib.error

spec = importlib.util.spec_from_file_location('broker', Path(__file__).parent / 'baseline-container/api-broker.py')
broker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(broker)


class BrokerFailures(unittest.TestCase):
    def request(self, error, version, close=False, after_headers=False):
        with tempfile.TemporaryDirectory() as directory:
            auth = Path(directory) / 'synthetic-auth.json'
            auth.write_text(json.dumps({'tokens': {'access_token': 'dummy-test-token', 'account_id': 'dummy-test-account'}}))
            opener = Mock()
            if after_headers:
                response = Mock(status=200)
                response.__enter__ = Mock(return_value=response)
                response.__exit__ = Mock(return_value=False)
                response.read1.side_effect = error
                opener.open.return_value = response
            else:
                opener.open.side_effect = error
            logs = io.StringIO()
            server = broker.Server(('127.0.0.1', 0), broker.Handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            with patch.object(broker, 'AUTH_PATH', auth), patch.object(broker.urllib.request, 'build_opener', return_value=opener), patch.dict(broker.os.environ, {'UPSTREAM_CONNECT_PROXY': 'http://127.0.0.1:1'}), contextlib.redirect_stdout(logs):
                thread.start()
                try:
                    client = http.client.HTTPConnection(*server.server_address, timeout=3)
                    client._http_vsn = version
                    client._http_vsn_str = 'HTTP/1.0' if version == 10 else 'HTTP/1.1'
                    headers = {'Content-Type': 'application/json',
                               'session-id': '00000000-0000-4000-8000-000000000001',
                               'thread-id': '00000000-0000-4000-8000-000000000002'}
                    if close:
                        headers['Connection'] = 'close'
                    payload = {'model': broker.MODEL, 'reasoning': {'effort': broker.EFFORT}, 'stream': True}
                    client.request('POST', '/v1/responses', json.dumps(payload), headers)
                    response = client.getresponse()
                    status, body = response.status, response.read()
                    client.close()
                finally:
                    server.shutdown()
                    thread.join()
                    server.server_close()
            records = [json.loads(line) for line in logs.getvalue().splitlines()]
            self.assertEqual(opener.open.call_count, 1)
            self.assertNotIn('dummy-test-token', logs.getvalue())
            self.assertNotIn('dummy-test-account', logs.getvalue())
            return status, body, records

    def test_pre_response_failure_has_502_and_terminal_record(self):
        for version, close in ((10, False), (11, True), (11, False)):
            for error in (TimeoutError('synthetic timeout'), urllib.error.URLError('synthetic failure')):
                with self.subTest(version=version, close=close, error=type(error).__name__):
                    status, body, records = self.request(error, version, close)
                    self.assertEqual(status, 502)
                    self.assertEqual(json.loads(body), {'error': 'broker_request_failed'})
                    self.assertEqual([row['event'] for row in records], ['accepted', 'broker_error', 'denied'])
                    self.assertEqual(records[-1]['status'], 502)

    def test_stream_failure_does_not_send_second_status(self):
        for error, terminal in (
            (TimeoutError('synthetic stream failure'), 'broker_error'),
            (urllib.error.HTTPError('http://synthetic.invalid', 503, 'synthetic failure', {}, None), 'upstream_error'),
        ):
            with self.subTest(terminal=terminal):
                status, body, records = self.request(error, 11, True, True)
                self.assertEqual((status, body), (200, b''))
                self.assertEqual([row['event'] for row in records], ['accepted', terminal])

    def test_pre_response_http_error_is_sanitized(self):
        error = urllib.error.HTTPError('http://synthetic.invalid', 503, 'synthetic failure', {}, None)
        status, body, records = self.request(error, 11, True)
        self.assertEqual((status, json.loads(body)), (502, {'error': 'upstream_request_failed'}))
        self.assertEqual([row['event'] for row in records], ['accepted', 'upstream_error', 'denied'])


if __name__ == '__main__':
    unittest.main()
