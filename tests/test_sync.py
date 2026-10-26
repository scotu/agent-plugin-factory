import tempfile
import unittest
from pathlib import Path

from factory import audit, build, config
from factory.gitutil import git, is_dirty
from tests.helpers import Sandbox, publish


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
        publish(self.sb)

    def tearDown(self):
        self.sb.cleanup()

    def test_first_sync_builds_merges_and_pushes(self):
        r = self.first
        self.assertEqual((r.conflicts, r.audit_needed), ([], True))
        self.assertEqual(r.upstream_sha, git(self.sb.upstream, "rev-parse", "HEAD"))
        self.assertEqual(self.sb.remote_rev("upstream"), r.built)
        self.assertTrue(git(self.sb.clone, "merge-base", "--is-ancestor", r.main, self.sb.remote_rev("main")) == "")
        self.assertEqual(git(self.sb.remote, "show", "refs/heads/main:a.txt"), "one\ntwo\nthree")
        self.assertIn(f"| `a.txt` | A | complies |",
                      git(self.sb.remote, "show", f"refs/heads/main:audits/{r.built[:12]}.md"))
        stamp = git(self.sb.remote, "show", "refs/heads/upstream:UPSTREAM")
        self.assertEqual(stamp, f"repo: {self.sb.upstream.as_uri()}\npath: plug\nref: main\ncommit: {r.upstream_sha}")
        self.assertEqual(git(self.sb.remote, "show", "refs/heads/upstream:FACTORY"), "commit: unknown")
        self.assertEqual(git(self.sb.remote, "log", "-1", "--format=%s", "refs/heads/upstream"),
                         f"demo 1.0 @ {r.upstream_sha[:12]}")
        self.assertIn("C-000", git(self.sb.clone, "log", "--format=%s", "main"))
        self.assertEqual(git(self.sb.clone, "branch", "--show-current"), "main")

    def test_rerun_without_changes_is_noop(self):
        published_main = git(self.sb.clone, "rev-parse", "main")
        again = build.sync(self.sb.root, "demo", "hermes")
        self.assertEqual((again.built, again.main, again.conflicts, again.audit_needed),
                         (self.first.built, published_main, [], False))

    def test_customization_survives_upstream_change(self):
        customize(self.sb.clone, "a.txt", "ONE\ntwo\nthree\n", "C-001: shout")
        self.sb.write_upstream("b.txt", "bee\n")
        r = build.sync(self.sb.root, "demo", "hermes")
        self.assertEqual((r.conflicts, r.audit_needed), ([], True))
        self.assertEqual((self.sb.clone / "a.txt").read_text(), "ONE\ntwo\nthree\n")
        self.assertEqual((self.sb.clone / "b.txt").read_text(), "bee\n")
        self.assertNotEqual(self.sb.remote_rev("main"), r.main)
        publish(self.sb)
        self.assertEqual(self.sb.remote_rev("main"), git(self.sb.clone, "rev-parse", "main"))

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
        self.assertEqual(r.conflicts, ["a.txt"])
        self.assertEqual(self.sb.remote_rev("main"), remote_main)
        self.assertEqual(self.sb.remote_rev("upstream"), self.first.built)

        (self.sb.clone / "a.txt").write_text("one\nmine and theirs\nthree\n")
        git(self.sb.clone, "add", "a.txt")
        git(self.sb.clone, "commit", "-q", "--no-edit")
        again = build.sync(self.sb.root, "demo", "hermes")
        self.assertEqual(again.conflicts, [])
        publish(self.sb)
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

    def test_system_exit_in_hook_is_rolled_back(self):
        self.sb.write_upstream("EXIT", "x\n")
        with self.assertRaisesRegex(build.HookError, "bye"):
            build.sync(self.sb.root, "demo", "hermes")
        self.assertEqual(git(self.sb.clone, "rev-parse", "refs/heads/upstream"), self.first.built)
        self.assertEqual(git(self.sb.clone, "branch", "--show-current"), "main")
        self.assertFalse(is_dirty(self.sb.clone))

    def test_dirty_upstream_branch_gives_recovery_command(self):
        git(self.sb.clone, "switch", "-q", "upstream")
        (self.sb.clone / "a.txt").unlink()
        with self.assertRaisesRegex(build.SyncError, "reset --hard"):
            build.sync(self.sb.root, "demo", "hermes")

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
        self.assertTrue(r.audit_needed)
        self.assertEqual(git(self.sb.clone, "config", "rerere.enabled"), "true")

    def test_shallow_install_fast_forwards(self):
        with tempfile.TemporaryDirectory() as tmp:
            inst = Path(tmp) / "inst"
            git(Path(tmp), "clone", "-q", "--depth", "1", self.sb.remote.as_uri(), str(inst))
            customize(self.sb.clone, "a.txt", "ONE\ntwo\nthree\n", "C-001: shout")
            self.sb.write_upstream("b.txt", "bee\n")
            build.sync(self.sb.root, "demo", "hermes")
            publish(self.sb)
            git(inst, "pull", "-q", "--ff-only")
            self.assertEqual((inst / "a.txt").read_text(), "ONE\ntwo\nthree\n")
            self.assertTrue((inst / "b.txt").exists())

    def test_push_refuses_unaudited_upstream_build(self):
        self.sb.write_upstream("b.txt", "bee\n")
        build.sync(self.sb.root, "demo", "hermes")
        remote_main = self.sb.remote_rev("main")
        with self.assertRaisesRegex(build.AuditError, "no committed audit"):
            build.push(self.sb.root, "demo", "hermes")
        audit.skeleton(self.sb.clone)
        git(self.sb.clone, "add", "-A")
        git(self.sb.clone, "commit", "-q", "-m", "audit skeleton")
        with self.assertRaisesRegex(build.AuditError, r"no verdict: b\.txt, FACTORY|no verdict: .*b\.txt"):
            build.push(self.sb.root, "demo", "hermes")
        self.assertEqual(self.sb.remote_rev("main"), remote_main)

    def test_audit_rows_match_the_unpublished_range(self):
        self.sb.write_upstream("b.txt", "bee\n")
        self.sb.write_upstream("a.txt", "", delete=True)
        build.sync(self.sb.root, "demo", "hermes")
        rows = dict((p, s) for p, s in audit.changes(self.sb.clone, audit.published(self.sb.clone),
                                                      git(self.sb.clone, "rev-parse", "upstream")))
        self.assertEqual((rows["b.txt"], rows["a.txt"]), ("A", "D"))
        self.assertNotIn("CUSTOMIZATIONS.md", rows)
        publish(self.sb, verdict="C-001")
        self.assertEqual(self.sb.remote_rev("upstream"), git(self.sb.clone, "rev-parse", "upstream"))

    def test_rebuild_carries_verdicts_for_unchanged_paths(self):
        self.sb.write_upstream("b.txt", "bee\n")
        self.sb.write_upstream("c.txt", "sea\n")
        build.sync(self.sb.root, "demo", "hermes")
        first = audit.skeleton(self.sb.clone)
        first.write_text(first.read_text().replace("| pending |", "| complies |"))
        git(self.sb.clone, "add", "-A")
        git(self.sb.clone, "commit", "-q", "-m", "audit")
        self.sb.write_upstream("c.txt", "see\n")
        build.sync(self.sb.root, "demo", "hermes")
        text = audit.skeleton(self.sb.clone).read_text()
        self.assertIn("| `b.txt` | A | complies |", text)
        self.assertIn("| `c.txt` | A | pending |", text)

    def test_customization_pushes_without_audit(self):
        customize(self.sb.clone, "a.txt", "ONE\ntwo\nthree\n", "C-001: shout")
        self.assertIsNone(build.push(self.sb.root, "demo", "hermes"))
        self.assertEqual(git(self.sb.remote, "show", "refs/heads/main:a.txt"), "ONE\ntwo\nthree")

    def test_target_path_builds_from_its_subdir(self):
        (self.sb.upstream / "plug2").mkdir()
        (self.sb.upstream / "plug2" / "plugin.json").write_text('{"name": "demo"}\n')
        (self.sb.upstream / "plug2" / "a.txt").write_text("from plug2\n")
        git(self.sb.upstream, "add", "-A")
        git(self.sb.upstream, "commit", "-q", "-m", "plug2")
        remote = self.sb.root.parent / "cc.git"
        remote.mkdir()
        git(remote, "init", "-q", "--bare", "-b", "main")
        seed = self.sb.root.parent / "cc-seed"
        seed.mkdir()
        git(seed, "init", "-q", "-b", "upstream")
        git(seed, "commit", "-q", "--allow-empty", "-m", "init")
        git(seed, "switch", "-q", "-c", "main")
        (seed / "CUSTOMIZATIONS.md").write_text("# ledger\n")
        git(seed, "add", "-A")
        git(seed, "commit", "-q", "-m", "C-000: ledger")
        git(seed, "push", "-q", remote.as_uri(), "main", "upstream")
        toml = self.sb.root / "plugins" / "demo" / "plugin.toml"
        toml.write_text(toml.read_text() + f'\n[targets.cc]\nbuild_repo = "{remote.as_uri()}"\npath = "plug2"\n')
        (self.sb.root / "plugins" / "demo" / "cc").mkdir()
        (self.sb.root / "plugins" / "demo" / "cc" / "port.py").write_text(
            (self.sb.root / "plugins" / "demo" / "hermes" / "port.py").read_text())
        build.sync(self.sb.root, "demo", "cc")
        clone = self.sb.root / "builds" / "cc" / "demo"
        self.assertEqual((clone / "a.txt").read_text(), "from plug2\n")
        self.assertIn("path: plug2", (clone / "UPSTREAM").read_text())

    def test_claude_code_target_checks_its_own_manifest(self):
        self.assertEqual(build.MANIFESTS["claude-code"], ".claude-plugin/plugin.json")

    def test_unknown_target(self):
        with self.assertRaisesRegex(config.ConfigError, "no target 'codex'"):
            build.sync(self.sb.root, "demo", "codex")


if __name__ == "__main__":
    unittest.main()
