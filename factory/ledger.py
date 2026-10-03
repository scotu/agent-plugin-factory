"""CUSTOMIZATIONS.md: one `## C-NNN — title  [status]` section per customization, with a `Touches:` line."""
import re
from dataclasses import dataclass

HEADING = re.compile(r"## (C-\d+)\b.*\[(\w+)\]\s*$")


@dataclass(frozen=True)
class Entry:
    id: str
    title: str
    status: str
    touches: tuple[str, ...]


def parse(text: str) -> list[Entry]:
    entries = []
    for block in re.split(r"^(?=## C-)", text, flags=re.M)[1:]:
        first = block.splitlines()[0]
        head = HEADING.match(first)
        if not head:  # e.g. the `## C-NNN` example inside the template's code fence
            continue
        line = re.search(r"^Touches:(.*)$", block, re.M)
        touches = tuple(p.strip() for p in line.group(1).split(",") if p.strip()) if line else ()
        entries.append(Entry(head.group(1), first[3:].strip(), head.group(2), touches))
    return entries


def _hit(path: str, changed: str) -> bool:
    return changed == path or changed.startswith(path.rstrip("/") + "/")


def touched(entries: list[Entry], changed: list[str]) -> list[Entry]:
    """Active entries with a Touches path that one of the changed files matches or lies under."""
    return [e for e in entries
            if e.status == "active" and any(_hit(p, c) for p in e.touches for c in changed)]
