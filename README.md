# agent-plugin-factory

Builds upstream agent plugins for the agents we use, with personal customizations that survive upstream updates. For now the only target is [Hermes](https://hermes-agent.nousresearch.com/).

| Plugin | Upstream | Build repo |
|---|---|---|
| pstack | [cursor/plugins/pstack](https://github.com/cursor/plugins/tree/main/pstack) | [scotu/pstack-hermes](https://github.com/scotu/pstack-hermes) |

## How it works

Each plugin and target has its own **build repo**, `scotu/<plugin>-<target>`. It is a standalone plugin that you can install directly. It has two branches:

- **`upstream`** is the exact build output: the upstream tree run through the plugin's port hook. `UPSTREAM` records the upstream commit, and `FACTORY` records the factory commit that built it. Never edit it by hand.
- **`main`** is `upstream` plus personal changes. Hermes installs this branch.

Each personal change is a `C-NNN: …` commit on `main`, with an entry in that repo's `CUSTOMIZATIONS.md`: the intent, the reason, the files it touches, and how to check it. `git diff refs/heads/upstream main --` shows the whole fork.

`python3 -m factory sync <plugin>` does the following:
1. Fetches upstream and clones or fast-forwards the build repo into `builds/<target>/<plugin>/` (gitignored).
2. Runs the port hook into `upstream` and commits.
3. Lists the ledger entries whose files upstream changed, so you can check whether upstream now covers them.
4. Merges into `main`, with git rerere on, and pushes both branches.

On a conflict it stops without pushing. Re-apply each affected entry's intent, commit in the build clone, and run `sync` again.

Never rebase or reset `main` in a build repo. `hermes plugins update` pulls with `--ff-only`.

## Commands

```
python3 -m factory sync <plugin> [--ref <git-ref>] [--install]   # --install: update Hermes profiles using the build clone
python3 -m factory status [<plugin>]
python3 -m factory new <plugin> --upstream <git-url>[#subdir]     # creates plugins/<plugin>/ and scotu/<plugin>-hermes
python3 -m unittest discover -s tests -v
```

First install into a Hermes profile:
```
hermes -p <profile> plugins install file://$PWD/builds/hermes/<plugin> --enable
```

## Adding a plugin

1. Run `python3 -m factory new <name> --upstream <git-url>#<subdir>`. It writes `plugins/<name>/plugin.toml` and a stub `plugins/<name>/hermes/port.py`, which copies the tree as is. It also creates the public build repo.
2. Write the port hook, `port(src, out, ctx)`:
   - `src` is the upstream subtree and `out` is the empty build folder.
   - `ctx.here` is the hook's own folder, so overlay files can live next to it.
   - `ctx.upstream_sha` is the upstream commit. You can set `ctx.version`, which appears in commit messages.
   - The output must contain `plugin.json`.
3. Run `python3 -m factory sync <name>`, then install it.

## pstack on Hermes

`plugins/pstack/hermes/port.py` makes these changes to the upstream text:

1. **Manifest.** A root `plugin.json` (Agent Plugins v1) replaces `.cursor-plugin/plugin.json`. Its version is `<upstream>+hermes.<sha>`.
2. **Names.** Each `SKILL.md` `name:` is set to its directory name, which Hermes requires. This fixes `poteto-mode`.
3. **Pointer.** A one-line pointer to the `pstack-on-hermes` skill is added after every skill's frontmatter.
4. **Overlay** (`plugins/pstack/hermes/overlay/skills/`):
   - `pstack-on-hermes` maps Cursor to Hermes: `Task`/`subagent_type` become `delegate_task`, model roles become `pstack-models.md`, `AskQuestion` becomes `clarify`, cloud agents become worktrees, and transcripts become sessions. Upstream `agents/*.md` ship as its `references/`.
   - `setup-pstack` is replaced by a Hermes version that sets `delegation.model` and writes `pstack-models.md`.
5. **Dropped:** `make-bot-ui` (dr-eggbot ships its own), `automations/`, the docs, and the assets.

Skills resolve only under their namespaced name, `agent-plugin-pstack-7171b73f:<name>`.

Known limits:
- There is no per-subagent model on Hermes.
- Named Cursor agents become delegated tasks.
- Cursor cloud agents and `cursor-team-kit` have no Hermes equivalent.
- `disable-model-invocation` is ignored.
- `poteto-mode/scripts` need `bun`, `node` and `gh`.

## License

MIT. pstack is MIT, Copyright (c) 2026 Lauren Tan. See `LICENSE`.
