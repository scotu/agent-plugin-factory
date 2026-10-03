import unittest

from factory.ledger import Entry, parse, touched

LEDGER = """# x customizations

Entry format:

```
## C-NNN — <skill>: <short title>  [active]
Touches: skills/<name>/SKILL.md
```

## C-001 — bro: shorter  [active]
Intent: shorter
Touches: skills/bro/SKILL.md

## C-002 — poteto-mode: no PRs  [active]
Touches: skills/poteto-mode/, README.md

## C-003 — old thing  [retired]
Touches: skills/bro/SKILL.md
"""


class LedgerTest(unittest.TestCase):
    def test_parse(self):
        entries = parse(LEDGER)
        self.assertEqual([e.id for e in entries], ["C-001", "C-002", "C-003"])
        self.assertEqual(entries[0], Entry("C-001", "C-001 — bro: shorter  [active]", "active",
                                           ("skills/bro/SKILL.md",)))
        self.assertEqual(entries[1].touches, ("skills/poteto-mode/", "README.md"))
        self.assertEqual(entries[2].status, "retired")

    def test_touched_matches_files_and_folders(self):
        hits = touched(parse(LEDGER), ["skills/poteto-mode/playbooks/x.md", "UPSTREAM"])
        self.assertEqual([e.id for e in hits], ["C-002"])
        hits = touched(parse(LEDGER), ["skills/bro/SKILL.md"])
        self.assertEqual([e.id for e in hits], ["C-001"])

    def test_template_example_and_retired_entries_ignored(self):
        hits = touched(parse(LEDGER), ["skills/<name>/SKILL.md", "skills/bro/SKILL.md"])
        self.assertEqual([e.id for e in hits], ["C-001"])

    def test_prefix_is_not_a_folder_match(self):
        self.assertEqual(touched(parse(LEDGER), ["skills/poteto-mode-extra/a.md"]), [])

    def test_empty(self):
        self.assertEqual(parse(""), [])


if __name__ == "__main__":
    unittest.main()
