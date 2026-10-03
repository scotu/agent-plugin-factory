# pstack for Hermes

This builds upstream [pstack](https://github.com/cursor/plugins/tree/main/pstack) into a Hermes portable plugin (Agent Plugins v1). It replaces the cut-down catalog port: that port has 6 skills and about 34 KB of text, while this build has all 47 skills and about 400 KB.

```
git clone git@github.com:scotu/pstack-hermes.git && cd pstack-hermes
python3 sync.py [git-ref] [--install]   # default: main → build/pstack (its own git repo)
hermes -p <profile> plugins install file://$PWD/build/pstack --enable   # first time
hermes -p <profile> plugins update pstack     # after a re-sync (or pass --install above)
```

## Personal fork

`build/pstack` is not part of this repo. It is a clone of [scotu/pstack-hermes-build](https://github.com/scotu/pstack-hermes-build), and `sync.py` clones it on first run, fast-forwards it from GitHub before each build, and pushes both branches after each successful merge. Hermes installs from the local clone (`file://…/build/pstack`).

It has two branches:

- **`upstream`** is the exact output of `sync.py`. Never edit it by hand.
- **`main`** is `upstream` plus personal changes. Hermes installs this branch.

Each personal change is a commit on `main` named `C-NNN: …`. It has a matching entry in `build/pstack/CUSTOMIZATIONS.md` that records the intent, the reason, the files it touches, and a check that it still holds. `git -C build/pstack diff upstream main --` shows the whole fork.

`sync.py` commits the new build to `upstream` and then merges it into `main`, with git rerere enabled. Then:

- **Conflict:** the script stops and lists the conflicted files. Re-apply each affected entry's intent, commit, and re-run with `--install`.
- **Merge succeeded:** the script lists the active entries whose files upstream changed. Review each one. If upstream now covers it, mark it `retired`.

Never rebase or reset `main`. `hermes plugins update` pulls with `--ff-only`, so a rewritten `main` breaks every installed profile.

## What the build changes

Upstream text is copied verbatim, except for these changes:

1. **Manifest.** A root `plugin.json` (Agent Plugins v1) replaces `.cursor-plugin/plugin.json`. Its version is `<upstream>+hermes.<sha>`, and `UPSTREAM` records the exact commit.
2. **Names.** Each `SKILL.md` `name:` is set to its directory name, which Hermes requires. This fixes `poteto-mode`.
3. **Pointer.** A one-line pointer to the `pstack-on-hermes` skill is added after every skill's frontmatter.
4. **Overlay** (`overlay/skills/`):
   - `pstack-on-hermes` maps Cursor to Hermes: `Task`/`subagent_type` become `delegate_task`, model roles become `pstack-models.md`, `AskQuestion` becomes `clarify`, `/loop` stays `/loop`, cloud agents become worktrees, `cursor-team-kit` gets substitutes, and transcripts become sessions. Upstream `agents/*.md` ship as its `references/`.
   - `setup-pstack` is replaced by a Hermes version that sets `delegation.model` and writes `pstack-models.md` (roles map to `parent` | `delegate` | `profile:<name>`).
5. **Dropped:** `make-bot-ui`, which is platform-specific; dr-eggbot ships its own Hermes version. Also dropped: `automations/benny` (a Cursor Slack automation kit), the docs, and the assets.

Skills resolve only under their namespaced name, `agent-plugin-pstack-7171b73f:<name>`. The prefix is `sha256("pstack")[:8]`, so it is the same on every install. `sync.py` writes it into the pointer and the overlay.

## Known limits on Hermes

- **Models.** There is no per-subagent model. Every `delegate_task` child uses the profile's `delegation.model`. The only way to get a different model family in a panel is a `profile:<name>` entry (via `message_agent`, which is async).
- **Named agents.** Named Cursor agents (`poteto-agent`, `comment-sicko`) become delegated tasks with their text as context.
- **Missing Cursor pieces.** Cursor cloud agents and `cursor-team-kit` (`deslop`, `control-ui`, `control-cli`) have no Hermes equivalent. The shim names the substitutes: worktrees, `unslop`, browser tools, and the terminal.
- **Invocation flags.** `disable-model-invocation` is ignored by Hermes, so the model can load every skill.
- **Scripts.** `poteto-mode/scripts` need `bun`, `node`, and `gh`. Run `bun install` in the installed copy before first use.

## License

MIT. Upstream pstack is MIT, Copyright (c) 2026 Lauren Tan. See `LICENSE`.
