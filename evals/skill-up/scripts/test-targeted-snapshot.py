#!/usr/bin/env python3
"""Verify Skill snapshot copying without credentials, models or PyYAML."""
import importlib.util
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("targeted_runner", Path(__file__).with_name("run-targeted.py"))
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)

SUMMARY_SPEC = importlib.util.spec_from_file_location("targeted_summary", Path(__file__).with_name("summarize-targeted.py"))
SUMMARY = importlib.util.module_from_spec(SUMMARY_SPEC)
SUMMARY_SPEC.loader.exec_module(SUMMARY)


class SkillCopyPolicy(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.skill = self.root / "skill"
        self.skill.mkdir()
        (self.skill / "SKILL.md").write_bytes(b"---\nname: fixture\n---\nUnchanged bytes.  \n")
        self.outside = self.root / "outside-marker.txt"
        self.outside.write_text("harmless outside fixture marker")
        self.destination = self.root / "snapshot" / "skill"

    def tearDown(self):
        self.temp.cleanup()

    def rejected(self):
        with self.assertRaisesRegex(ValueError, "符号链接"):
            RUNNER.copy_skill_tree(self.skill, self.destination)
        self.assertFalse(self.destination.exists())

    def test_regular_tree_keeps_bytes_and_executable_mode(self):
        nested = self.skill / "scripts"
        nested.mkdir()
        script = nested / "helper.sh"
        script.write_text("#!/bin/sh\nexit 0\n")
        script.chmod(0o755)
        RUNNER.copy_skill_tree(self.skill, self.destination)
        for relative in ("SKILL.md", "scripts/helper.sh"):
            self.assertEqual((self.destination / relative).read_bytes(), (self.skill / relative).read_bytes())
        self.assertEqual((self.destination / "scripts/helper.sh").stat().st_mode & 0o777, 0o755)

    def test_external_file_link_is_rejected(self):
        (self.skill / "linked.txt").symlink_to(self.outside)
        self.rejected()

    def test_external_directory_link_is_rejected(self):
        outside = self.root / "outside-directory"
        outside.mkdir()
        (outside / "marker.txt").write_text("directory marker")
        (self.skill / "linked-directory").symlink_to(outside, target_is_directory=True)
        self.rejected()

    def test_internal_link_is_also_rejected(self):
        (self.skill / "linked.md").symlink_to("SKILL.md")
        self.rejected()

    def test_broken_link_is_rejected(self):
        (self.skill / "broken.txt").symlink_to("missing.txt")
        self.rejected()

    def test_symlink_source_root_is_rejected(self):
        alias = self.root / "alias"
        alias.symlink_to(self.skill, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "符号链接"):
            RUNNER.copy_skill_tree(alias, self.destination)
        self.assertFalse(self.destination.exists())

    def assert_main_rejects_before_copy_or_tool_launch(self, skill):
        stderr = io.StringIO()
        arguments = ["run-targeted.py", "--skill", str(skill), "--output", str(self.destination),
                     "--cases", "unused-fixture"]
        with patch.object(sys, "argv", arguments), contextlib.redirect_stderr(stderr), \
                patch.object(RUNNER, "copy_skill_tree") as copy, \
                patch.object(RUNNER, "captured") as capture, \
                patch.object(RUNNER.shutil, "which") as which:
            with self.assertRaises(SystemExit) as stopped:
                RUNNER.main()
            self.assertEqual(stopped.exception.code, 2)
            copy.assert_not_called()
            capture.assert_not_called()
            which.assert_not_called()
        self.assertIn("符号链接", stderr.getvalue())
        self.assertFalse(self.destination.exists())

    def test_main_rejects_supplied_root_symlink_before_resolve(self):
        alias = self.root / "alias"
        alias.symlink_to(self.skill, target_is_directory=True)
        self.assert_main_rejects_before_copy_or_tool_launch(alias)

    def test_main_rejects_tree_symlink_before_copy(self):
        (self.skill / "linked.txt").symlink_to(self.outside)
        self.assert_main_rejects_before_copy_or_tool_launch(self.skill)

    def test_cli_rejects_root_symlink_without_optional_dependencies(self):
        alias = self.root / "alias"
        alias.symlink_to(self.skill, target_is_directory=True)
        result = subprocess.run([sys.executable, "-S", str(Path(RUNNER.__file__)), "--skill", str(alias),
                                 "--output", str(self.destination), "--cases", "unused-fixture"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("符号链接", result.stderr)
        self.assertFalse(self.destination.exists())
        self.assertEqual(self.outside.read_text(), "harmless outside fixture marker")

    def test_catalog_probe_rejects_before_launching_codex(self):
        (self.skill / "linked.txt").symlink_to(self.outside)
        with patch.object(RUNNER.subprocess, "run") as execute:
            with self.assertRaisesRegex(ValueError, "符号链接"):
                RUNNER.catalog_preflight(self.root / "probe", "unused-codex", [], self.skill)
            execute.assert_not_called()
        self.assertFalse((self.root / "probe/catalog-probe/.codex/skills/goal-prompt").exists())

    def test_link_inserted_during_copy_is_not_followed_and_copy_is_removed(self):
        copytree = RUNNER.shutil.copytree
        copied_as_link = []
        def changed_source(source, target, **kwargs):
            (self.skill / "late.txt").symlink_to(self.outside)
            result = copytree(source, target, **kwargs)
            copied_as_link.append((target / "late.txt").is_symlink())
            return result
        with patch.object(RUNNER.shutil, "copytree", side_effect=changed_source):
            self.rejected()
        self.assertEqual(copied_as_link, [True])
        self.assertEqual(self.outside.read_text(), "harmless outside fixture marker")

    def test_destination_link_is_rejected_after_copy(self):
        copytree = RUNNER.shutil.copytree
        def changed_destination(source, target, **kwargs):
            result = copytree(source, target, **kwargs)
            (target / "late.txt").symlink_to(self.outside)
            return result
        with patch.object(RUNNER.shutil, "copytree", side_effect=changed_destination):
            self.rejected()

    def test_copy_failure_removes_only_owned_partial_tree(self):
        def failed_copy(source, target, **kwargs):
            (target / "partial.txt").write_text("partial fixture")
            raise OSError("injected copy failure")
        with patch.object(RUNNER.shutil, "copytree", side_effect=failed_copy):
            with self.assertRaisesRegex(OSError, "injected"):
                RUNNER.copy_skill_tree(self.skill, self.destination)
        self.assertFalse(self.destination.exists())
        self.assertTrue((self.skill / "SKILL.md").is_file())

    def test_existing_destination_is_never_removed(self):
        self.destination.mkdir(parents=True)
        marker = self.destination / "existing.txt"
        marker.write_text("existing output")
        with self.assertRaises(FileExistsError):
            RUNNER.copy_skill_tree(self.skill, self.destination)
        self.assertEqual(marker.read_text(), "existing output")


class PreparedSnapshotPolicy(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.run = self.root / "frozen-run"
        self.snapshot = self.run / "snapshot"
        self.snapshot.mkdir(parents=True)
        self.skill_file = self.snapshot / "SKILL.md"
        self.skill_file.write_bytes(b"harmless fixed snapshot bytes\n")
        self.outside = self.root / "outside-marker.txt"
        self.outside.write_bytes(self.skill_file.read_bytes())
        (self.run / "bin").mkdir()
        (self.run / "bin/codex").write_text("wrapper fixture")
        self.binary = self.root / "binary"
        self.binary.write_text("binary fixture")
        self.manifest = {
            "cases": [], "snapshot_sha256": {"SKILL.md": RUNNER.digest(self.skill_file)},
            "wrapper": {"sha256": RUNNER.digest(self.run / "bin/codex")},
            "skill_up_sha256": RUNNER.digest(self.binary),
            "codex_binary": str(self.binary), "codex": "fixture-version",
        }
        RUNNER.write_json(self.run / "manifest.json", self.manifest)

    def tearDown(self):
        self.temp.cleanup()

    def tamper(self, variant):
        if variant == "same-bytes":
            self.skill_file.unlink()
            self.skill_file.symlink_to(self.outside)
        else:
            (self.snapshot / "dangling.txt").symlink_to(self.root / "missing.txt")
        # This is the old bypass: both mutations preserve the previous hash map.
        actual = {str(path.relative_to(self.snapshot)): RUNNER.digest(path)
                  for path in self.snapshot.rglob("*") if path.is_file()}
        self.assertEqual(actual, self.manifest["snapshot_sha256"])

    def test_run_frozen_rejects_links_before_checks_or_dispatch(self):
        for variant in ("same-bytes", "dangling"):
            with self.subTest(variant=variant):
                self.tamper(variant)
                with patch.object(RUNNER, "verify_catalog_evidence") as catalog, \
                        patch.object(RUNNER.subprocess, "run") as launch:
                    with self.assertRaisesRegex(ValueError, "符号链接"):
                        RUNNER.run_frozen(self.run, self.binary, self.manifest)
                    catalog.assert_not_called()
                    launch.assert_not_called()
                self.assertNotIn("execution_started_utc", self.manifest)
                self.assertFalse((self.run / "run.log").exists())
                if variant == "same-bytes":
                    self.skill_file.unlink()
                    self.skill_file.write_bytes(self.outside.read_bytes())

    def test_prepared_main_rejects_before_delegating_old_runner(self):
        self.tamper("same-bytes")
        archived = self.run / "run-targeted.py"
        archived.write_text("old archived runner fixture")
        self.manifest["runner_sha256"] = RUNNER.digest(archived)
        RUNNER.write_json(self.run / "manifest.json", self.manifest)
        stderr = io.StringIO()
        arguments = ["run-targeted.py", "--run-prepared", "--output", str(self.run)]
        with patch.object(sys, "argv", arguments), contextlib.redirect_stderr(stderr), \
                patch.object(RUNNER, "verify_catalog_evidence") as catalog, \
                patch.object(RUNNER.os, "execv") as delegate, \
                patch.object(RUNNER, "run_frozen") as execute:
            with self.assertRaises(SystemExit) as stopped:
                RUNNER.main()
            self.assertEqual(stopped.exception.code, 2)
            catalog.assert_not_called()
            delegate.assert_not_called()
            execute.assert_not_called()
        self.assertIn("符号链接", stderr.getvalue())
        self.assertEqual(archived.read_text(), "old archived runner fixture")

    def test_cli_prepared_rejects_dangling_without_dependencies(self):
        self.tamper("dangling")
        before = (self.run / "manifest.json").read_bytes()
        result = subprocess.run([sys.executable, "-S", RUNNER.__file__, "--run-prepared",
                                 "--output", str(self.run)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("符号链接", result.stderr)
        self.assertEqual((self.run / "manifest.json").read_bytes(), before)
        self.assertFalse((self.run / "run.log").exists())

    def test_regular_prepared_snapshot_still_dispatches_stub_once(self):
        with patch.object(RUNNER, "verify_catalog_evidence"), \
                patch.object(RUNNER, "captured", return_value="fixture-version"), \
                patch.object(RUNNER.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as launch, \
                patch.object(RUNNER, "audit_outputs"):
            self.assertEqual(RUNNER.run_frozen(self.run, self.binary, self.manifest), 0)
            self.assertEqual(launch.call_count, 1)
        self.assertIn("completed_utc", self.manifest)

    def test_summary_rejects_same_bytes_and_dangling_links_before_archiving(self):
        for variant in ("same-bytes", "dangling"):
            with self.subTest(variant=variant):
                self.tamper(variant)
                output = self.root / ("summary-" + variant)
                output.mkdir()
                with self.assertRaisesRegex(ValueError, "符号链接"):
                    SUMMARY.summarize_run(self.run, output, {})
                self.assertFalse((output / self.run.name).exists())
                if variant == "same-bytes":
                    self.skill_file.unlink()
                    self.skill_file.write_bytes(self.outside.read_bytes())

    def test_regular_summary_keeps_verified_status(self):
        output = self.root / "summary"
        output.mkdir()
        info = SUMMARY.summarize_run(self.run, output, {})
        self.assertTrue(info["snapshot_verified"])
        self.assertEqual(info["state"], "pending")
        self.assertEqual(info["cases"], [])


if __name__ == "__main__":
    unittest.main()
