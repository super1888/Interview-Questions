import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1] / "scripts" / "sync_skill.py"
spec = importlib.util.spec_from_file_location("sync_skill", MODULE)
sync_skill = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync_skill)


class SyncSkillTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "source"
        self.source.mkdir()
        (self.source / "SKILL.md").write_text("first version", encoding="utf-8")
        self.destination_root = self.root / "skills"
        self.destination = self.destination_root / sync_skill.SKILL_NAME

    def install(self):
        return sync_skill.sync(self.source, self.destination_root)

    def test_install_and_read_only_check(self):
        self.assertEqual(self.install()["status"], "installed")
        before = {p: p.stat().st_mtime_ns for p in self.destination_root.rglob("*")}
        self.assertEqual(sync_skill.sync(self.source, self.destination_root, check=True)["status"], "verified")
        self.assertEqual(before, {p: p.stat().st_mtime_ns for p in self.destination_root.rglob("*")})

    def test_update_replaces_changed_files_and_removes_retired_files(self):
        (self.source / "old.md").write_text("retired")
        self.install()
        (self.source / "old.md").unlink()
        (self.source / "SKILL.md").write_text("second version")
        (self.source / "new.md").write_text("new")
        self.assertEqual(self.install()["status"], "updated")
        self.assertFalse((self.destination / "old.md").exists())
        self.assertEqual(sync_skill.inventory(self.source), sync_skill.inventory(self.destination))

    def test_local_edits_are_preserved_and_update_is_rejected(self):
        self.install()
        (self.destination / "SKILL.md").write_text("local customization")
        (self.source / "SKILL.md").write_text("upstream change")
        with self.assertRaises(sync_skill.SyncError):
            self.install()
        self.assertEqual((self.destination / "SKILL.md").read_text(), "local customization")

    def test_unknown_installation_is_not_overwritten(self):
        self.destination.mkdir(parents=True)
        (self.destination / "SKILL.md").write_text("someone else's skill")
        with self.assertRaises(sync_skill.SyncError):
            self.install()
        self.assertEqual((self.destination / "SKILL.md").read_text(), "someone else's skill")

    def test_identical_official_installation_can_be_adopted(self):
        self.destination.mkdir(parents=True)
        (self.destination / "SKILL.md").write_text("first version")
        self.assertEqual(self.install()["status"], "adopted")
        sync_skill.sync(self.source, self.destination_root, check=True)

    def test_missing_installation_check_has_no_side_effects(self):
        with self.assertRaises(sync_skill.SyncError):
            sync_skill.sync(self.source, self.destination_root, check=True)
        self.assertFalse(self.destination_root.exists())

    def test_check_detects_drift(self):
        self.install()
        (self.source / "SKILL.md").write_text("changed")
        with self.assertRaises(sync_skill.SyncError):
            sync_skill.sync(self.source, self.destination_root, check=True)

    def test_symlink_installation_is_preserved(self):
        self.destination_root.mkdir()
        self.destination.symlink_to(self.source, target_is_directory=True)
        with self.assertRaises(sync_skill.SyncError):
            self.install()
        self.assertTrue(self.destination.is_symlink())

    def test_failed_replacement_restores_previous_installation(self):
        self.install()
        old_state = (self.destination_root / f".{sync_skill.SKILL_NAME}.installation.json").read_bytes()
        (self.source / "SKILL.md").write_text("second version")
        real_replace = sync_skill.os.replace

        def fail_candidate(source, destination):
            if Path(source).name == "candidate":
                raise OSError("simulated replacement failure")
            return real_replace(source, destination)

        with patch.object(sync_skill.os, "replace", side_effect=fail_candidate):
            with self.assertRaises(sync_skill.SyncError):
                self.install()
        self.assertEqual((self.destination / "SKILL.md").read_text(), "first version")
        self.assertEqual((self.destination_root / f".{sync_skill.SKILL_NAME}.installation.json").read_bytes(), old_state)

    def test_other_skills_remain_untouched(self):
        other = self.destination_root / "unrelated"
        other.mkdir(parents=True)
        (other / "SKILL.md").write_text("keep")
        self.install()
        (self.source / "SKILL.md").write_text("second version")
        self.install()
        self.assertEqual((other / "SKILL.md").read_text(), "keep")


if __name__ == "__main__":
    unittest.main()
