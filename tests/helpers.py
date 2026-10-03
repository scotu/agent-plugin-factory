"""A throwaway world for end-to-end tests: a fake upstream repo, a bare repo standing in for GitHub,
a factory root with plugin `demo` (target `hermes`) created through `new`, and an empty profiles dir."""
import tempfile
from pathlib import Path

from factory.gitutil import git
from factory.new import clone_path, new

COPY_HOOK = '''import shutil


def port(src, out, ctx):
    if (src / "FAIL").exists():
        raise RuntimeError("boom")
    shutil.copytree(src, out, dirs_exist_ok=True)
    ctx.version = "1.0"
'''


class Sandbox:
    def __init__(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name).resolve()
        self.upstream = base / "upstream"
        self.remote = base / "remote.git"
        self.root = base / "factory"
        self.profiles = base / "profiles"
        self.profiles.mkdir()
        (self.upstream / "plug").mkdir(parents=True)
        git(self.upstream, "init", "-q", "-b", "main")
        (self.upstream / "other").mkdir()
        (self.upstream / "other" / "x.txt").write_text("not part of the plugin\n")
        self.write_upstream("plugin.json", '{"name": "demo"}\n')
        self.write_upstream("a.txt", "one\ntwo\nthree\n")
        self.remote.mkdir()
        git(self.remote, "init", "-q", "--bare", "-b", "main")
        self.root.mkdir()
        new(self.root, "demo", "hermes", f"{self.upstream.as_uri()}#plug", self.remote.as_uri())
        (self.root / "plugins" / "demo" / "hermes" / "port.py").write_text(COPY_HOOK)
        self.clone = clone_path(self.root, "demo", "hermes")

    def write_upstream(self, rel: str, text: str, delete: bool = False) -> str:
        path = self.upstream / "plug" / rel
        if delete:
            path.unlink()
        else:
            path.write_text(text)
        git(self.upstream, "add", "-A")
        git(self.upstream, "commit", "-q", "-m", f"change {rel}")
        return git(self.upstream, "rev-parse", "HEAD")

    def remote_rev(self, branch: str) -> str:
        return git(self.remote, "rev-parse", f"refs/heads/{branch}")

    def cleanup(self):
        self._tmp.cleanup()
