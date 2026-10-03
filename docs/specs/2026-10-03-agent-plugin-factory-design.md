# Agent plugin factory: design

## Goal

Turn `pstack-hermes` into a factory for agent plugins that we customize but keep in sync with their upstreams. pstack is the first plugin. For every plugin the factory does the same things: pull upstream, apply a mechanical port to the target agent, keep personal customizations, merge future upstream changes, and install.

Constraints and decisions:
- **Hermes is the only target for now.** Names and layout carry the target, so another agent can be added later without restructuring.
- **One tooling repo plus one build repo per plugin and target** (option C). Each build repo is a plugin that installs on its own.
- **Customizations stay as `C-NNN` git commits** on the build repo's `main`, with a `CUSTOMIZATIONS.md` ledger. Upstream comes in by merge, with rerere enabled. This is the workflow already built and tested for pstack.

Success means:
- Adding a plugin takes `./factory new` plus a port hook, with no change to `factory/`.
- pstack is rebuilt from the factory with the same tree as today's build.
- The installed profiles keep working.

## Repositories

| Repo | Role |
|---|---|
| `scotu/agent-plugin-factory` | The tooling. It is the current `scotu/pstack-hermes`, renamed. |
| `scotu/<plugin>-<target>` | One build repo per plugin and target. pstack's is `scotu/pstack-hermes`, renamed from `scotu/pstack-hermes-build`. |

The renames happen in this order: first factory, then build. GitHub keeps a redirect after a rename only until another repo takes the old name, so the `pstack-hermes` → factory redirect is lost when the build repo takes that name. That's acceptable: the only references to it are the local clone and our READMEs, and both get updated. The redirect `pstack-hermes-build` → `pstack-hermes` keeps working.

## Factory layout

```
factory/                      shared tool, Python standard library only
  cli.py                      ./factory sync <plugin> [--ref X] [--install] | new | status
  ...                         modules for git, ledger, and install
factory (executable)          thin wrapper: python3 -m factory.cli "$@"
plugins/<plugin>/
  plugin.toml                 upstream source and the targets to build
  <target>/port.py            port hook
  <target>/overlay/...        files owned by the hook (for pstack: pstack-on-hermes, setup-pstack)
builds/<target>/<plugin>/     gitignored clone of the build repo; Hermes installs it via file://
tests/                        unittest suite
docs/specs/                   design docs
```

`plugins/pstack/plugin.toml`:
```toml
[upstream]
repo = "https://github.com/cursor/plugins"
path = "pstack"
ref = "main"

[targets.hermes]
build_repo = "git@github.com:scotu/pstack-hermes.git"
plugin_key = "pstack"          # the name Hermes installs it under, used by --install
```

## Build repo model (unchanged)

- `upstream` is the exact output of a factory build and is never edited by hand.
- `main` is `upstream` plus `C-NNN` commits and `CUSTOMIZATIONS.md`. Hermes installs this branch.
- Never rewrite `main`, because `hermes plugins update` runs `git pull --ff-only`.
- Each `upstream` build commit includes `UPSTREAM` (repo, path, ref, commit) and `FACTORY` (the factory commit, plus `dirty` if the factory tree had uncommitted changes). Every build can then be traced to its tool and overlay version.

## Shared tool vs. port hook

The shared tool, in `factory/`, does the steps that are the same for every plugin:
1. Read `plugin.toml`. Fetch the upstream repo with a sparse checkout of `path` at the ref.
2. Set up the build repo:
   - Clone it into `builds/<target>/<plugin>` if it's missing, and enable rerere.
   - Refuse to run if the tree has uncommitted changes.
   - Fetch, check out `upstream`, and fast-forward it from `origin`.
3. Empty the tree, keeping `.git`. Call the hook. Write `UPSTREAM` and `FACTORY`.
4. Commit to `upstream`, if anything changed.
5. Check out `main`, fast-forward it from `origin`, and print review notices: the active ledger entries whose `Touches` paths upstream changed.
6. Merge `upstream` with `--no-ff`. Push both branches.
7. With `--install`, run `hermes -p <profile> plugins update <plugin_key>` for every profile whose `.install-metadata.json` records this build clone as the source.

Each plugin and target provides the hook:
```python
def port(src: Path, out: Path, ctx: Context) -> None
```
- `src` is the upstream subtree, read-only. `out` is empty.
- `ctx` carries the upstream commit, the ref, and `here`, the hook's own folder, for its overlay.

pstack's hook takes over everything in today's `sync.py` that is specific to pstack:
- the `NS` prefix, `POINTER` and `patch_skill`, and `EXCLUDE`
- copying the overlay, with `{{NS}}` substituted
- turning `agents/*.md` into the `pstack-on-hermes` references
- the `LICENSE` copy and the `UPSTREAM-README.md` copy
- `plugin.json` with version `<upstream>+hermes.<sha7>`

A helper moves into `factory/` only once a second plugin needs it.

The other commands:
- `./factory new <plugin> --target hermes --upstream <git-url#subdir>` creates `plugins/<plugin>/` with `plugin.toml` and a stub hook that copies everything. It also creates `scotu/<plugin>-<target>` (public) with `gh repo create`, initialized with a `main` that holds the ledger and a README.
- `./factory status` lists, for each build: the `upstream` and `main` commits, how many commits upstream is ahead at the configured ref, the active ledger entries, and the installed profiles with their revision.

## Error handling

| Failure | Behavior |
|---|---|
| The build repo has uncommitted changes or an unfinished merge | Refuse to run. Nothing changes. |
| The hook raises an exception, or the output has no manifest (`plugin.json` for hermes) | Reset `upstream` to its previous commit, check out `main`, exit non-zero. Nothing is committed or pushed. |
| Conflict when merging into `main` | Stop mid-merge. List the conflicted files and the ledger path. Nothing is pushed. After resolving and committing, run `sync` again: the merge does nothing, then it pushes and installs. |
| Fast-forward from `origin` fails (the histories diverged) | Stop with a message. Never force anything. |
| A push fails | Report it. The local state is correct, and the next run pushes again. |

## Testing

Use `unittest` with temporary git repos and no network.
- **Unit tests:** ledger parsing and touched-entry matching, and loading `plugin.toml`.
- **End-to-end tests**, with a fake upstream repo, a bare repo standing in for GitHub, and a test plugin whose hook copies files:
  1. The first sync clones the build repo, commits to `upstream`, merges into `main`, and pushes.
  2. A `C-001` commit on `main` survives an upstream change to a different file.
  3. An upstream change to the same line stops with the conflict listed, and nothing is pushed.
  4. A failing hook leaves `upstream` unchanged, the repo on `main`, and the tree clean.
  5. A shallow clone of the bare remote fast-forwards with `git pull --ff-only` after a sync.
- **pstack check:** `./factory sync pstack --ref ecc249f1e306fc64ddf83c7bed16cacf7c2239db`, run on a scratch copy, rebuilds the same tree as today's `upstream` (0a84f1d), apart from the new `FACTORY` file.

## Migration

1. Restructure the local repo:
   - `factory/`, `plugins/pstack/` (hook, overlay, and `plugin.toml`), `tests/`, and the READMEs.
   - Remove `sync.py` and the root `overlay/`.
2. Run the tests and the pstack check.
3. Rename the GitHub repos as described above, then update the `origin` URLs and `plugin.toml`.
4. Move the build clone from `build/pstack` to `builds/hermes/pstack`. Reinstall pstack in `dr-eggbot` and `homelab-ops` with `file://…/builds/hermes/pstack`. Both must end at revision `b322423` with pstack enabled.
5. Commit and push the factory.
6. Pulling upstream 0.15.6 into pstack is a separate step, and only with explicit approval.

## Out of scope

- Targets other than Hermes, until one is needed.
- Sharing customizations between targets.
- Running syncs automatically on a schedule.
