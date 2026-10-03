import json
import unittest

from factory import build, install, status
from tests.helpers import Sandbox


def fake_install(sb, profile, key, source, revision="abc1234def"):
    meta = sb.profiles / profile / "plugins" / ".install-metadata.json"
    meta.parent.mkdir(parents=True)
    meta.write_text(json.dumps({key: {"pinned": False, "revision": revision, "source": source}}))


class InstallStatusTest(unittest.TestCase):
    def setUp(self):
        self.sb = Sandbox()
        build.sync(self.sb.root, "demo", "hermes")

    def tearDown(self):
        self.sb.cleanup()

    def test_installed_matches_only_this_clone(self):
        fake_install(self.sb, "alpha", "demo", self.sb.clone.as_uri())
        fake_install(self.sb, "beta", "demo", "file:///elsewhere/demo")
        fake_install(self.sb, "gamma", "other", self.sb.clone.as_uri())
        self.assertEqual(install.installed(self.sb.profiles, "demo", self.sb.clone), [("alpha", "abc1234def")])

    def test_status_line(self):
        fake_install(self.sb, "alpha", "demo", self.sb.clone.as_uri())
        (line,) = status.lines(self.sb.root, ["demo"], self.sb.profiles)
        self.assertTrue(line.startswith("demo/hermes: "))
        self.assertIn("0 new upstream commits on main", line)
        self.assertIn("0 active customizations", line)
        self.assertIn("installed: alpha@abc1234", line)
        self.sb.write_upstream("b.txt", "bee\n")
        (line,) = status.lines(self.sb.root, ["demo"], self.sb.profiles)
        self.assertIn("1 new upstream commits on main", line)

    def test_status_not_cloned(self):
        import shutil
        shutil.rmtree(self.sb.clone)
        self.assertEqual(status.lines(self.sb.root, ["demo"], self.sb.profiles), ["demo/hermes: not cloned (run sync)"])


if __name__ == "__main__":
    unittest.main()
