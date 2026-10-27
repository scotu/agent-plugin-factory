---
name: pstack-install
description: Install the current published pstack build into every place that already has it - Hermes profiles (hermes) and Claude Code (claude-code). Optional argument - the target.
disable-model-invocation: true
---

# pstack install

Bring every install of pstack up to its build repo's published `main`. Run everything from the factory root. An argument of `hermes` or `claude-code` limits the run to that target. With no argument, run both. To pull a new upstream version first, run `/pstack-update`.

## Hermes

Move every Hermes profile that installed pstack from the local build clone to the clone's current `main`. The clone is `builds/hermes/pstack`.

1. **Refresh the clone and install only what is published.** Run `git -C builds/hermes/pstack pull --ff-only`. If the clone is missing, stop and point to `/pstack-update`. Hermes installs the clone's local `main`, so `main` must equal `origin/main`. `git -C builds/hermes/pstack rev-list --count origin/main..main` must print `0`. A higher count means an unpublished, possibly unaudited update is in progress. Stop and point to `/pstack-update`.
2. **Find the targets.** Run `python3 -m factory status pstack`. Its `installed:` list gives each `<profile>@<rev>`. Every profile whose rev is behind `main` is a target. If none are behind, report that all profiles are current and stop.
3. **Update each target.** Run `hermes -p <profile> plugins update pstack`. A target that exits 0 is done.
4. **Handle a scan block.** Hermes' install scanner may refuse the update with `Decision: BLOCKED … Use --force to override`. `plugins update` has no `--force` flag. The override is a forced reinstall from the same source.
   - Collect the findings: severity, file and line.
   - Sort them by whether the file changed since the installed rev: `git -C builds/hermes/pstack diff --quiet <rev> main -- <file>` exits 0 when it is unchanged. Read each new or changed flagged line.
   - Show the user every finding, with the changed or new ones first, and ask whether to force. Approval covers only this run.
   - On yes, for each blocked profile, check whether pstack is enabled in `hermes -p <profile> plugins list`. Then run `hermes -p <profile> plugins install "file://$PWD/builds/hermes/pstack" --force`, adding `--enable` if it was enabled and `--no-enable` if it was not. Use the same `file://` source so that `factory status` still tracks the profile. Leave out `--ref`, because it pins the profile and `update` refuses a pinned plugin from then on.
   - **A pinned profile** (`update` says `is pinned to <sha>`) keeps its pin through a reinstall. To unpin it: back up `config.yaml`, run `plugins remove pstack`, then install as above. Confirm afterwards that `config.yaml` is unchanged and that `.install-metadata.json` shows `"pinned": false`.
5. **Verify.** Done when `python3 -m factory status pstack` shows every installed profile at `main`'s short SHA, and `hermes -p <profile> plugins list` shows the new version with its enabled state unchanged. Report:
   - each profile with its old and new rev and version
   - whether a scan block was overridden, and which findings were new

## Claude Code

Claude Code installs pstack from the GitHub marketplace `scotu/pstack-claude-code` (marketplace name `scotu-pstack`), never from the local clone. A local-path marketplace loads its files live, which would skip the audit gate. The build has no `version`, so Claude Code versions each install by commit, and every push is an update.

1. **Install only what is published.** Run `git -C builds/claude-code/pstack fetch -q`. `git -C builds/claude-code/pstack rev-list --count origin/main..main` must print `0`. Otherwise, stop and point to `/pstack-update`.
2. **First install.** If `python3 -m factory status pstack` shows `installed: none` for `claude-code`, ask the user before installing. `~/.claude/settings.json` is managed by chezmoi (`dot_claude/private_settings.json.tmpl`), so the first install is a settings change the user makes there: `extraKnownMarketplaces.scotu-pstack` with source `{"source": "github", "repo": "scotu/pstack-claude-code"}`, plus `enabledPlugins["pstack@scotu-pstack"] = true`. Give them those entries rather than running `claude plugin marketplace add` or `claude plugin install`, which would write the unmanaged file.
3. **Update.** Run `claude plugin marketplace update scotu-pstack`, then `claude plugin update pstack@scotu-pstack`.
4. **Verify.** Done when `python3 -m factory status pstack` shows `installed: <scope>@<origin/main sha7>` for `claude-code`. A settings-enabled install has no record in `~/.claude/plugins/installed_plugins.json`, so status reads the live cache folder and shows `cache@<sha7>`. The marketplace has `autoUpdate` on, so a new session also picks up a push by itself. Tell the user that open sessions keep the old copy until `/reload-plugins` or a restart.
