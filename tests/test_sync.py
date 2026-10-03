import tempfile
import unittest
from pathlib import Path

from factory import build, config
from factory.gitutil import git, is_dirty
from tests.helpers import Sandbox


def customize(clone: Path, rel: str, text: str, msg: str, ledger_entry: str = "") -> None:
    (clone / rel).write_text(text)
    if ledger_entry:
        with (clone / "CUSTOMIZATIONS.md").open("a") as f:
            f.write("\n" + ledger_entry)
    git(clone, "add", "-A")
    git(clone, "commit", "-q", "-m", msg)


class SyncTest(unittest.TestCase):
    def setUp(self):
        self.sb = Sandbox()
        self.first = build.sync(self.sb.root, "demo", "hermes")

    def tearDown(self):
        self.sb.cleanup()

    def test_first_sync_builds_merges_and_pushes(self):
        r = self.first
        self.assertEqual((r.conflicts, r.pushed), ([], True))
        self.assertEqual(r.upstream_sha, git(self.sb.upstream, "rev-parse", "HEAD"))
        self.assertEqual(self.sb.remote_rev("upstream"), r.built)
        self.assertEqual(self.sb.remote_rev("main"), r.main)
        self.assertEqual(git(self.sb.remote, "show", "refs/heads/main:a.txt"), "one\ntwo\nthree")
        stamp = git(self.sb.remote, "show", "refs/heads/upstream:UPSTREAM")
        self.assertEqual(stamp, f"repo: {self.sb.upstream.as_uri()}\npath: plug\nref: main\ncommit: {r.upstream_sha}")
        self.assertEqual(git(self.sb.remote, "show", "refs/heads/upstream:FACTORY"), "commit: unknown")
        self.assertEqual(git(self.sb.remote, "log", "-1", "--format=%s", "refs/heads/upstream"),
                         f"demo 1.0 @ {r.upstream_sha[:12]}")
        self.assertIn("C-000", git(self.sb.clone, "log", "--format=%s", "main"))
        self.assertEqual(git(self.sb.clone, "branch", "--show-current"), "main")

    def test_rerun_without_changes_is_noop(self):
        again = build.sync(self.sb.root, "demo", "hermes")
        self.assertEqual((again.built, again.main, again.conflicts, again.pushed),
                         (self.first.built, self.first.main, [], True))

    def test_customization_survives_upstream_change(self):
        customize(self.sb.clone, "a.txt", "ONE\ntwo\nthree\n", "C-001: shout")
        self.sb.write_upstream("b.txt", "bee\n")
        r = build.sync(self.sb.root, "demo", "hermes")
        self.assertEqual((r.conflicts, r.pushed), ([], True))
        self.assertEqual((self.sb.clone / "a.txt").read_text(), "ONE\ntwo\nthree\n")
        self.assertEqual((self.sb.clone / "b.txt").read_text(), "bee\n")
        self.assertEqual(self.sb.remote_rev("main"), r.main)

    def test_review_notice_for_touched_entries(self):
        entry = "## C-001 — a: shout  [active]\nIntent: x\nTouches: a.txt\n"
        customize(self.sb.clone, "a.txt", "ONE\ntwo\nthree\n", "C-001: shout", entry)
        self.sb.write_upstream("a.txt", "one\ntwo\nTHREE\n")
        r = build.sync(self.sb.root, "demo", "hermes")
        self.assertEqual([e.id for e in r.reviews], ["C-001"])
        self.assertEqual((self.sb.clone / "a.txt").read_text(), "ONE\ntwo\nTHREE\n")

    def test_conflict_then_resolution_pushes(self):
        customize(self.sb.clone, "a.txt", "one\nmine\nthree\n", "C-001: mine")
        self.sb.write_upstream("a.txt", "one\ntheirs\nthree\n")
        remote_main = self.sb.remote_rev("main")
        r = build.sync(self.sb.root, "demo", "hermes")
        self.assertEqual((r.conflicts, r.pushed), (["a.txt"], False))
        self.assertEqual(self.sb.remote_rev("main"), remote_main)
        self.assertEqual(self.sb.remote_rev("upstream"), self.first.built)

        (self.sb.clone / "a.txt").write_text("one\nmine and theirs\nthree\n")
        git(self.sb.clone, "add", "a.txt")
        git(self.sb.clone, "commit", "-q", "--no-edit")
        again = build.sync(self.sb.root, "demo", "hermes")
        self.assertEqual((again.conflicts, again.pushed), ([], True))
        self.assertEqual(git(self.sb.remote, "show", "refs/heads/main:a.txt"), "one\nmine and theirs\nthree")
        self.assertEqual(self.sb.remote_rev("upstream"), again.built)

    def test_unfinished_merge_refused(self):
        customize(self.sb.clone, "a.txt", "one\nmine\nthree\n", "C-001: mine")
        self.sb.write_upstream("a.txt", "one\ntheirs\nthree\n")
        build.sync(self.sb.root, "demo", "hermes")
        git(self.sb.clone, "checkout", "--ours", "--", "a.txt")
        git(self.sb.clone, "add", "a.txt")
        with self.assertRaisesRegex(build.SyncError, "unfinished merge"):
            build.sync(self.sb.root, "demo", "hermes")

    def test_failing_hook_leaves_state_clean(self):
        self.sb.write_upstream("FAIL", "x\n")
        with self.assertRaisesRegex(build.HookError, "boom"):
            build.sync(self.sb.root, "demo", "hermes")
        self.assertEqual(git(self.sb.clone, "rev-parse", "refs/heads/upstream"), self.first.built)
        self.assertEqual(git(self.sb.clone, "branch", "--show-current"), "main")
        self.assertFalse(is_dirty(self.sb.clone))

    def test_missing_manifest_fails(self):
        self.sb.write_upstream("plugin.json", "", delete=True)
        with self.assertRaisesRegex(build.HookError, "no plugin.json"):
            build.sync(self.sb.root, "demo", "hermes")
        self.assertEqual(git(self.sb.clone, "rev-parse", "refs/heads/upstream"), self.first.built)

    def test_dirty_clone_refused(self):
        (self.sb.clone / "scratch.txt").write_text("x\n")
        self.sb.write_upstream("b.txt", "bee\n")
        with self.assertRaisesRegex(build.SyncError, "uncommitted changes"):
            build.sync(self.sb.root, "demo", "hermes")
        self.assertEqual(git(self.sb.clone, "rev-parse", "refs/heads/upstream"), self.first.built)

    def test_missing_clone_is_cloned(self):
        import shutil
        shutil.rmtree(self.sb.clone)
        self.sb.write_upstream("b.txt", "bee\n")
        r = build.sync(self.sb.root, "demo", "hermes")
        self.assertTrue(r.pushed)
        self.assertEqual(git(self.sb.clone, "config", "rerere.enabled"), "true")

    def test_shallow_install_fast_forwards(self):
        with tempfile.TemporaryDirectory() as tmp:
            inst = Path(tmp) / "inst"
            git(Path(tmp), "clone", "-q", "--depth", "1", self.sb.remote.as_uri(), str(inst))
            customize(self.sb.clone, "a.txt", "ONE\ntwo\nthree\n", "C-001: shout")
            self.sb.write_upstream("b.txt", "bee\n")
            build.sync(self.sb.root, "demo", "hermes")
            git(inst, "pull", "-q", "--ff-only")
            self.assertEqual((inst / "a.txt").read_text(), "ONE\ntwo\nthree\n")
            self.assertTrue((inst / "b.txt").exists())

    def test_unknown_target(self):
        with self.assertRaisesRegex(config.ConfigError, "no target 'codex'"):
            build.sync(self.sb.root, "demo", "codex")


if __name__ == "__main__":
    unittest.main()
