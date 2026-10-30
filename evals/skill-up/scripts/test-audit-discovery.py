"""Metadata exemption must never hide content reads or executable sed scripts."""
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('audit',Path(__file__).with_name('run-baseline.py'))
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)

class DiscoveryTest(unittest.TestCase):
    def test_metadata_pipeline(self):
        for command in (
            "/bin/bash -lc \"pwd && rg --files -g 'SKILL.md' | sed -n '1,100p'\"",
            "/bin/bash -lc \"rg --files | sort | head -n 10\"",
        ):
            with self.subTest(command=command):self.assertTrue(audit.filename_discovery(command))

    def test_content_and_commands_are_not_exempt(self):
        for body in (
            "sed -n '1,100p' SKILL.md", "rg --files | sed -n '1,100p' SKILL.md",
            "rg --files | sed -n '1p; r SKILL.md'", "rg --files | sed -n '1e cat SKILL.md'",
            "rg --files | sed -n '1w /tmp/out'", "rg --files && sed -n '1,100p'",
            "cat SKILL.md | sed -n '1,100p'", "rg secret SKILL.md", "find / -exec cat SKILL.md +",
            "ls & cat SKILL.md", "ls |& cat SKILL.md", "ls &&& cat SKILL.md",
            "ls &", "ls |& sort",
            "rg --files | sed -n \"$(cat SKILL.md)\"", "rg --files | sed -n '1p' > /tmp/out",
        ):
            import shlex
            with self.subTest(body=body):self.assertFalse(audit.filename_discovery('/bin/bash -lc '+shlex.quote(body)))

if __name__=='__main__':unittest.main()
