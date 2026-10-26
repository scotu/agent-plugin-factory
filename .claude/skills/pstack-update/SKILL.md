---
name: pstack-update
description: Pull the latest upstream pstack into its build repos (hermes, claude-code), audit every upstream change against our principles, and push. Optional argument - the target.
disable-model-invocation: true
---

# pstack update

Bring upstream pstack into a build repo, check every file it changed against the **Principles** and the active entries in the ledger, fix what breaks them, and publish. Run commands from the factory root unless a step says the build clone.

There are two targets, each with its own build repo, ledger and port:

| Target | Build clone | Port hook and overlay | Upstream folder |
|---|---|---|---|
| `hermes` | `builds/hermes/pstack` (`scotu/pstack-hermes`) | `plugins/pstack/hermes/` | `pstack` |
| `claude-code` | `builds/claude-code/pstack` (`scotu/pstack-claude-code`) | `plugins/pstack/claude-code/` | `harness/pstack/claude-code` |

An argument of `hermes` or `claude-code` runs one target. With no argument, run every step for `hermes`, then for `claude-code`. Add `--target <target>` to every `factory` command below. "The build clone", "the ledger" and "the port" mean that target's. A clean merge proves only that nothing collided. The audit is what proves the build is ours. This skill does not install. Installing is `/pstack-install`.

## Steps

1. **Start clean.** Run `git pull --ff-only` in the factory, then `python3 -m unittest discover -s tests`. Done when the factory is current and the tests are green.
2. **Check for work.** Run `python3 -m factory status pstack` and `python3 -m factory audit pstack`.
   - `0 new upstream commits` and `nothing to audit`: report the current version and stop.
   - An unfinished audit from an earlier run: skip to step 5.
3. **Sync.** Run `python3 -m factory sync pstack`. It merges locally and never pushes.
   - If it ends with `MERGE CONFLICT`, go to step 4.
   - Otherwise go to step 5.
4. **Resolve each conflict by intent.** Work in the build clone. For each conflicted file:
   - Find the active entries whose `Touches:` lists the file.
   - Start from upstream's text with `git show refs/heads/upstream:<file> > <file>`.
   - Re-apply each entry's **Intent** to that text, in upstream's new style. Upstream may have moved the passage, for example into a playbook that another playbook now inherits. Put the intent where the behavior now lives.

   Commit the merge with a message that names each re-applied entry.
5. **Audit every changed path.** Run `python3 -m factory audit pstack`. It writes `audits/<sha12>.md` in the build clone with one `pending` row per path changed since the last published build. Before reading, load the ledger's Principles and every active Intent. Then, for each row:
   - Read the change with `git diff <From> <To> -- <path>` (`From:` and `To:` are in the file header). Read an added file in full.
   - Judge it against every principle and intent, not only the entries whose `Touches:` names it. Look for text that:
     - prescribes duplicated work or a recurring tick;
     - adds a panel or model role;
     - names a Cursor tool, skill, plugin or path;
     - links to a dropped file;
     - undoes a customization in other words.
   - Fix each violation where the fix will last:
     - **P-2 mappings and dropped-file links:** fix in the factory, in the target's `port.py` or its `overlay/`. Commit the factory change, then run step 3 again. The new audit carries over verdicts for paths that did not change.
     - **Everything else:** a `C-NNN: …` commit on `main`. Add the file to that entry's `Touches:`, or add a new entry.
   - Write the verdict and a one-line note: `complies`, `n/a`, `port` or `C-NNN`.

   For a large audit, split the rows by skill folder across subagents. Give each one the Principles, the Intents and its rows, and have it return a verdict and note per row. You own the fixes and the final verdicts.

   Done when all of these hold:
   - `python3 -m unittest discover -s tests` passes in the build clone; `tests/test_principles.py` scans the whole tree;
   - every ledger `Check:` that is a command other than a test passes;
   - the audit file is committed on `main`;
   - `factory audit pstack` reports it complete.
6. **Retire what upstream now covers.** For each `review C-NNN` that sync printed, and any entry whose intent upstream now states itself, propose retiring the entry. Ask before retiring, and keep the entry as history per the ledger rules.
7. **Publish.** Run `python3 -m factory push pstack`. It refuses an incomplete audit.
8. **Report.**
   - old and new version (`version` in `plugin.json`) and the number of upstream commits
   - conflicts and how each intent was re-applied
   - audit counts by verdict, and each `port` or `C-NNN` fix with what it changed
   - new or removed upstream skills
   - a pointer to `/pstack-install`

## Rules

- `main` is append-only. Never rebase, reset or force-push it, because `hermes plugins update` pulls with `--ff-only`. Never edit `upstream` by hand.
- Write the upstream branch as `refs/heads/upstream`. On macOS, the bare name `upstream` collides with the `UPSTREAM` file.
- When an intent cannot be re-applied cleanly, for example because upstream removed the passage or the intent now contradicts upstream, stop and ask before committing.
