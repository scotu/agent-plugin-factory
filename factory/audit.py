"""The upstream audit: every file a new upstream build changes gets a verdict before that build is published.

`audits/<to sha12>.md` on `main` covers `From..To`, where From is the upstream build last pushed and To the one
about to be. Each changed path is one table row whose verdict is `complies`, `n/a`, `port` (fixed in the factory's
port hook or overlay), or the `C-NNN` entry under which it was changed. `push` refuses a new upstream build
without a complete audit."""
import re
from dataclasses import dataclass, field
from pathlib import Path

from .gitutil import git, ok

AUDITS = "audits"
ROW = re.compile(r"^\|\s*`?([^|`]+?)`?\s*\|\s*([AMD])\s*\|\s*([^|]*?)\s*\|(.*)$")
VERDICT = re.compile(r"^(complies|n/a|port|C-\d+)$")
PENDING = "pending"


@dataclass
class Check:
    path: Path
    found: bool = False
    missing: list = field(default_factory=list)   # changed paths with no row
    pending: list = field(default_factory=list)   # rows without a valid verdict
    extra: list = field(default_factory=list)     # rows for paths the range did not change

    @property
    def complete(self) -> bool:
        return self.found and not (self.missing or self.pending or self.extra)


def published(clone: Path) -> str:
    """The upstream build last pushed: the base every audit starts from."""
    return git(clone, "rev-parse", "refs/remotes/origin/upstream")


def needed(clone: Path) -> bool:
    return git(clone, "rev-parse", "refs/heads/upstream") != published(clone)


def changes(clone: Path, base: str, head: str) -> list[tuple[str, str]]:
    out = git(clone, "diff", "--no-renames", "--name-status", base, head)
    return [(line[2:].strip(), line[0]) for line in out.splitlines() if line]


def path_for(clone: Path, head: str) -> Path:
    return clone / AUDITS / f"{head[:12]}.md"


def _blob(clone: Path, rev: str, rel: str) -> str:
    spec = f"{rev}:{rel}"
    return git(clone, "rev-parse", spec) if ok(clone, "cat-file", "-e", spec) else ""


def _carried(clone: Path, base: str, head: str) -> dict[str, tuple[str, str]]:
    """Verdicts from an earlier audit of the same base (a rebuild after a port fix), for paths whose
    content is the same in both builds."""
    out = {}
    for old in sorted((clone / AUDITS).glob("*.md")) if (clone / AUDITS).is_dir() else []:
        text = old.read_text()
        to = re.search(r"^To: (\w+)$", text, re.M)
        if f"\nFrom: {base}\n" not in text or not to or to.group(1) == head:
            continue
        for line in text.splitlines():
            m = ROW.match(line)
            if m and VERDICT.match(m.group(3)) and _blob(clone, to.group(1), m.group(1)) == _blob(clone, head, m.group(1)):
                out[m.group(1)] = (m.group(3), m.group(4).rstrip("|").strip())
    return out


def skeleton(clone: Path) -> Path:
    """Write the audit for published..upstream with every verdict pending, except verdicts carried from an
    earlier audit of the same base for unchanged paths. An existing file is kept."""
    base, head = published(clone), git(clone, "rev-parse", "refs/heads/upstream")
    path = path_for(clone, head)
    if path.exists():
        return path
    carried = _carried(clone, base, head)
    rows = ""
    for p, s in changes(clone, base, head):
        verdict, note = carried.get(p, (PENDING, ""))
        rows += f"| `{p}` | {s} | {verdict} | {note + ' ' if note else ''}|\n"
    path.parent.mkdir(exist_ok=True)
    path.write_text(f"# Upstream audit {base[:7]}..{head[:7]}\n\nFrom: {base}\nTo: {head}\n\n"
                    "Verdicts: `complies`, `n/a` (metadata, no behavior), `port` (fixed in the factory's port hook or overlay), "
                    "or the `C-NNN` entry it was changed under.\n\n"
                    "| Path | Change | Verdict | Note |\n|---|---|---|---|\n" + rows)
    return path


def check(clone: Path) -> Check:
    base, head = published(clone), git(clone, "rev-parse", "refs/heads/upstream")
    path = path_for(clone, head)
    result = Check(path)
    rel = f"{AUDITS}/{path.name}"
    if not ok(clone, "cat-file", "-e", f"refs/heads/main:{rel}"):
        result.missing = [p for p, _ in changes(clone, base, head)]
        return result
    result.found = True
    rows = {}
    for line in git(clone, "show", f"refs/heads/main:{rel}").splitlines():
        m = ROW.match(line)
        if m:
            rows[m.group(1)] = m.group(3)
    wanted = [p for p, _ in changes(clone, base, head)]
    result.missing = [p for p in wanted if p not in rows]
    result.pending = [p for p in wanted if p in rows and not VERDICT.match(rows[p])]
    result.extra = [p for p in rows if p not in wanted]
    return result
