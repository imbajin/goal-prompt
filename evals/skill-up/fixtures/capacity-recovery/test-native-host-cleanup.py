#!/usr/bin/env python3
"""Fault-inject cleanup failures without launching Docker or a model."""
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('native_host_fixture', Path(__file__).with_name('test-native-host.py'))
FIXTURE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FIXTURE)


class CleanupFailures(unittest.TestCase):
    def exercise(self, fault):
        calls = []
        def check_output(command, **kwargs):
            if command[1] == 'create':
                return 'fixture-owned-container\n'
            self.assertEqual(command, ['docker', 'inspect', 'fixture-owned-container'])
            return json.dumps([{'Image': 'fixture-image', 'HostConfig': {
                'NetworkMode': 'none', 'ReadonlyRootfs': True, 'Binds': None,
                'CapDrop': ['ALL'], 'SecurityOpt': ['no-new-privileges']}, 'Mounts': []}]).encode()
        def run(command, **kwargs):
            calls.append(command)
            if fault == 'start' and command[1] == 'start':
                raise subprocess.CalledProcessError(1, command)
            if fault == 'archive' and command[1] == 'exec' and command[3] == 'tar':
                raise OSError('injected evidence failure')
            # During a start failure the container has no evidence to collect.
            return subprocess.CompletedProcess(command, 1 if command[1] == 'exec' and 'cat' in command else 0, stdout=b'')
        with tempfile.TemporaryDirectory() as tmp:
            args = argparse.Namespace(output=Path(tmp)/'run', image='fixture-image', codex='codex', scenario='recovery', recovery_script=None)
            expected = subprocess.CalledProcessError if fault == 'start' else OSError
            with patch.object(FIXTURE.subprocess, 'check_output', side_effect=check_output), patch.object(FIXTURE.subprocess, 'run', side_effect=run):
                with self.assertRaises(expected):
                    FIXTURE.docker(args)
            self.assertEqual((args.output/'container-id.txt').read_text(), 'fixture-owned-container\n')
        self.assertEqual(calls[-1], ['docker', 'rm', '-f', 'fixture-owned-container'])
        self.assertEqual(sum(command[1] == 'rm' for command in calls), 1)

    def test_start_failure_still_removes_owned_container(self):
        self.exercise('start')

    def test_archive_exception_still_removes_owned_container(self):
        self.exercise('archive')


if __name__ == '__main__':
    unittest.main()
