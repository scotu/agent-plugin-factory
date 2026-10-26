---
name: pstack-install
description: Install the current pstack-hermes main into every Hermes profile that already has pstack.
disable-model-invocation: true
---

# pstack install

Move every Hermes profile that installed pstack from the local build clone to the clone's current `main`. Run everything from the factory root. The clone is `builds/hermes/pstack`. To pull a new upstream version first, run `/pstack-update`.

## Steps

1. **Refresh the clone and install only what is published.** Run `git -C builds/hermes/pstack pull --ff-only`. If the clone is missing, stop and point to `/pstack-update`. Hermes installs the clone's local `main`, so `main` must equal `origin/main`. `git -C builds/hermes/pstack rev-list --count origin/main..main` must print `0`. A higher count means an unpublished, possibly unaudited update is in progress. Stop and point to `/pstack-update`.
2. **Find the targets.** Run `python3 -m factory status pstack`. Its `installed:` list gives each `<profile>@<rev>`. Every profile whose rev is behind `main` is a target. If none are behind, report that all profiles are current and stop.
3. **Update each target.** Run `hermes -p <profile> plugins update pstack`. A target that exits 0 is done.
4. **Handle a scan block.** Hermes' install scanner may refuse the update with `Decision: BLOCKED … Use --force to override`. `plugins update` has no `--force` flag. The override is a forced reinstall from the same source.
   - Collect the findings: severity, file and line.
   - Sort them by whether the file changed since the installed rev: `git -C builds/hermes/pstack diff --quiet <rev> main -- <file>` exits 0 when it is unchanged. Read each new or changed flagged line.
   - Show the user every finding, with the changed or new ones first, and ask whether to force. Approval covers only this run.
   - On yes, for each blocked profile, check whether pstack is enabled in `hermes -p <profile> plugins list`. Then run `hermes -p <profile> plugins install "file://$PWD/builds/hermes/pstack" --force --ref $(git -C builds/hermes/pstack rev-parse main)`, adding `--enable` if it was enabled and `--no-enable` if it was not. Use the same `file://` source so that `factory status` still tracks the profile.
5. **Verify.** Done when `python3 -m factory status pstack` shows every installed profile at `main`'s short SHA, and `hermes -p <profile> plugins list` shows the new version with its enabled state unchanged. Report:
   - each profile with its old and new rev and version
   - whether a scan block was overridden, and which findings were new
