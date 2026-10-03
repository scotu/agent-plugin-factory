import tempfile
import unittest
from pathlib import Path

from factory.gitutil import GitError, git, has_branch, is_dirty, ok


class GitUtilTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        git(self.repo, "init", "-q", "-b", "main")
        (self.repo / "f.txt").write_text("x\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "first")

    def tearDown(self):
        self.tmp.cleanup()

    def test_commits_with_factory_identity(self):
        self.assertEqual(git(self.repo, "log", "-1", "--format=%an <%ae>"),
                         "agent-plugin-factory <agent-plugin-factory@localhost>")

    def test_git_raises_with_detail(self):
        with self.assertRaises(GitError) as cm:
            git(self.repo, "rev-parse", "no-such-ref")
        self.assertIn("rev-parse", str(cm.exception))

    def test_ok_and_has_branch(self):
        self.assertTrue(has_branch(self.repo, "main"))
        self.assertFalse(has_branch(self.repo, "upstream"))
        self.assertFalse(ok(self.repo, "rev-parse", "--verify", "--quiet", "nope"))

    def test_is_dirty(self):
        self.assertFalse(is_dirty(self.repo))
        (self.repo / "new.txt").write_text("y\n")
        self.assertTrue(is_dirty(self.repo))

    def test_unfinished_merge_is_dirty_even_when_tree_matches_head(self):
        git(self.repo, "switch", "-q", "-c", "side")
        (self.repo / "f.txt").write_text("side\n")
        git(self.repo, "commit", "-qam", "side")
        git(self.repo, "switch", "-q", "main")
        (self.repo / "f.txt").write_text("main\n")
        git(self.repo, "commit", "-qam", "main")
        self.assertFalse(ok(self.repo, "merge", "side"))
        git(self.repo, "checkout", "--ours", "--", "f.txt")
        git(self.repo, "add", "f.txt")
        self.assertTrue(is_dirty(self.repo))


if __name__ == "__main__":
    unittest.main()
