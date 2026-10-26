# pstack for Claude Code: design

## Intent

pstack already runs on Hermes through this factory (`scotu/pstack-hermes`). Every upstream update is audited against the fork's Principles before it ships, and the fork runs economically. This design adds a second target, **Claude Code**, on the same terms:

- **It follows the same Principles.** Lean by default, going wide only on approval, and every upstream change audited before it is pushed.
- **It uses Codex as a first-class second family of agents** when Codex is installed and logged in. Codex agents can run any role and can write code in their own worktree. A thin Claude wrapper commits and publishes their work. pstack's multi-model workflows (two-family panels, a reviewer from the family that didn't write the code) keep their diversity in Claude Code. Upstream's Claude Code build loses it: every non-Claude slug falls back to "run on the session model".

The user pays for Claude Code and Codex through **subscriptions** (two separate quotas). No model is paid per token. The economy therefore comes from smaller widths: fewer duplicate runners, fewer same-prompt reviewers, one lane per check, and no hourly loop. Model choice follows **heterogeneity** and **tier**, not price.

## Goals

1. **Build.** A build repo `scotu/pstack-claude-code` is built by the factory and published only through the audit gate. It works as a Claude Code marketplace that the user installs once at user scope.
2. **Lean widths.** With no "go wide", no pstack skill runs duplicated work beyond the lean widths. The table is the same as Hermes' `pstack-economy`.
3. **Two families where it matters.** When Codex is available:
   - every duplicated-work step that runs two or more seats at lean width draws them from both families (arena candidates, a reviewer panel, architect runners when going wide);
   - every single reviewer, judge or verifier comes from the family that did not write the work.

   Divided work may use Codex, picked by tier and quota headroom, but it is not required to mix. When Codex is unavailable, everything runs on Claude, and the report says in one line that diversity was lost.
4. **Codex agents.** A Codex agent can own a unit of work, including writing the code for a PR, in its own git worktree. It is paired with a thin Claude wrapper:
   - **Codex** edits files in the worktree under its default `workspace-write` sandbox. Network stays off, and git metadata stays untouched.
   - **The wrapper** is a light-tier Claude subagent. It commits what Codex wrote, pushes, opens the PR, and runs the babysit loop, sending fix rounds back to Codex.

   The pair counts as the branch's one writer. The wrapper never writes code of its own. The pair keeps a decision trail, has a record in the program dir, and gets verification from the other family before merge.
5. **Self-contained audit tick.** A program's audit tick is a background watcher script that does the mechanical liveness checks with no model involved. It wakes the root session only when something changes. The hourly `/loop 1h` tick is the going-wide form only.
6. **Same update process.** Upstream updates follow the same process as Hermes: sync, audit every changed path against the Principles, fix, push, install. `/pstack-update` and `/pstack-install` cover both targets.

## Non-goals

- Surviving a closed session. The watcher, the owners and the root all live in one Claude Code session and stop together. There is no launchd or cron, and no `claude -p --resume` wake-ups.
- Per-token cost routing. The per-token rule stays in `pstack-economy` as a dormant guard in case an API-key executor is ever added. Nothing is designed around it.
- Codex Cloud (`codex cloud`). Codex agents run locally.
- Replacing upstream's Claude Code adapter (`docs/harness/claude-code.md`). It is reused as is, and the fork only adds to it.
- Sharing one copy of the economy text across targets. Each build repo has its own ledger. Duplicating the policy text is accepted.

## Anti-goals (failure even if it "works")

- Codex used as an extra width rather than as a family. If adding Codex makes panels wider than the lean width, the economy has been undone.
- A Codex agent and a Claude agent writing the same branch.
- Silent fallback: diversity lost, or Codex unavailable, with no line in the report.
- A watcher that costs a model turn while nothing is happening, for example a Monitor that must be re-armed every 30 minutes.
- An update published without its audit, or a Claude Code-specific gap that the Hermes guards would have caught.

## Decided

- **Source tree.** The factory builds the Claude Code target from upstream's generated Claude Code tree, `cursor/plugins` at `harness/pstack/claude-code/`, not from the Cursor tree. That tree already ships `.claude-plugin/plugin.json`, `agents/`, `skills/`, `docs/guide/`, and the adapter `docs/harness/claude-code.md`. That adapter maps `Task` to `Agent`, `environment: "cloud"` to `isolation: "worktree"`, and the model rule to `~/.claude/rules/pstack-models.md`. It also says Claude Code installs it as plugin `pstack`, with commands such as `/pstack:poteto-mode` and agents such as `pstack:poteto-agent`.
- **Plugin name.** It stays `pstack`, so upstream's adapter mappings (`pstack:poteto-agent`, `/pstack:<name>`) hold unchanged.
- **Codex writes code** in its own worktree, under its default sandbox, with no sandbox loosening. **A Claude wrapper commits and publishes it,** and the pair owns the PR.
- **Required mixing covers duplicated work and the author/verifier split only.** Divided work may use Codex but isn't required to mix.
- **Liveness is self-contained** in the Claude Code session (see Audit tick).
- **Both subscriptions.** Routing prefers heterogeneity at equal tier, not price.

## Architecture

### 1. Factory: per-target upstream

`plugins/pstack/plugin.toml` keeps `[upstream] repo/path/ref` as the default. A target may override `path` and `ref`:

```toml
[targets.claude-code]
build_repo = "git@github.com:scotu/pstack-claude-code.git"
plugin_key = "pstack"
path = "harness/pstack/claude-code"
```

- `config.Target` gains optional `path` and `ref`.
- `sync`, `status` (the upstream-ahead count) and the `UPSTREAM` stamp use the target's values.
- The port hook lives at `plugins/pstack/claude-code/port.py`.
- `factory new` / `factory sync` / `audit` / `push` already take `--target`, and they keep working per target.
- Create the build repo with `factory new`'s machinery. Its first sync's audit covers the whole tree, which is expected for a new build.

**Installs.** `factory status` reports Hermes installs from profile metadata. For Claude Code it reports the installed version and commit of `pstack@<marketplace>` from Claude Code's plugin records (`~/.claude/plugins/installed_plugins.json` or `claude plugin list`; the builder checks which is stable).

### 2. Port hook: `claude-code/port.py`

It is mechanical and faithful, like the Hermes port. It copies the upstream Claude Code tree, then:

1. **Manifest and marketplace.**
   - `.claude-plugin/plugin.json` gets version `<upstream version>+cc.<upstream sha7>` plus a part that changes on every publish of `main` *(my call)*. Claude Code may only deliver an update when the version string changes, so a customization-only push must still change it. The builder checks Claude Code's actual update rule. If updates track the git commit when `version` is absent, dropping the field is acceptable, and the upstream version moves into the description. Otherwise `factory push` stamps a publish counter in a commit before pushing. `/pstack-install` and `factory status` compare whatever this produces.
   - The hook adds `.claude-plugin/marketplace.json`, listing the one plugin `pstack` with source `./`, so the build repo is itself a marketplace. The marketplace name is the builder's call, for example `scotu-pstack`.
2. **Codex executor (overlay).** It adds an overlay skill `pstack-codex`, described below. It also adds one row to the adapter's Models table and a pointer from the adapter, so that whatever reads the adapter learns about Codex. The row says that a role value `codex <model> <effort>` runs as a Codex agent per `pstack-codex` when Codex is available. **Any non-Claude slug** (`grok-*`, `composer-*`, `cursor-grok-*`, `gpt-*`) also runs on Codex then, with Codex's own configured default model (no `-m`). That is how upstream's built-in two-family defaults keep their diversity before setup-pstack has run *(my call)*. Without Codex, these are omitted and reported, as upstream does today. This replaces upstream's "omit `model`" behavior for non-Claude slugs only when Codex is available. The builder inserts it in a way that survives upstream rewording, the way the Hermes port uses a pointer and overlay rather than in-place edits.
3. **Relinking.** The same relink pass as Hermes (`relink()` in the Hermes port): a relative link to a file the tree leaves out points at upstream on GitHub, pinned to the built commit. Upstream's tree already does this against `main`, so the hook pins it.
4. **Nothing is dropped** unless the audit finds a Claude Code-incompatible skill. Upstream's tree already left out automations and assets.

### 3. Overlay skill `pstack-codex`

This is a platform mapping, part of the port in the way `pstack-on-hermes` is. It defines **the Codex executor**:

- **Available** when all of these hold:
  - `codex --version` succeeds;
  - `codex login status` reports logged in;
  - the repo is a git repo.

  The OpenAI `codex` Claude Code plugin (`openai/codex-plugin-cc`) is preferred when installed. Its `codex-companion.mjs` provides `task [--background] [--write] [--model] [--effort]`, `status [--json]`, `result [--json]` and `cancel`. `codex exec -C <dir> -s workspace-write -m <model> --json` is the fallback.
- **Two shapes.**
  - **Code-writing owner** (feature, fix, a candidate in a race): a Codex job plus a Claude wrapper. The wrapper is an `Agent` subagent on a light model.
  - **Advisory seat** (reviewer, judge, verifier, explorer): a Codex job run read-only, with no `--write` and no wrapper. The caller reads its result directly.
- **Starting a code-writing owner:**
  1. The wrapper creates the worktree and branch (`git worktree add`), or takes the one the playbook names.
  2. It runs the Codex task from that worktree as cwd, background and write-capable (`workspace-write`), with the role's model and effort and the full brief. Codex sees only the brief, so the brief has to carry everything.
  3. It records the pair in the program dir (Audit tick): executor `codex`, worktree, branch, Codex job id, wrapper agent id, and expected minutes.
- **The wrapper's loop:**
  1. When the Codex job ends, review the worktree's diff for scope only. The wrapper doesn't rewrite code.
  2. Commit it with a message that names the Codex job, push, and open or update the PR.
  3. Babysit per the playbook. Send each fix round back to Codex as a resumed task on the same worktree, then commit and push again.

  The wrapper runs the repo's checks before a push, as any owner does.
- **Collecting.** Use the companion's `result` (or `exec`'s JSON output). Judge progress by side effects (Codex's file changes, then the wrapper's commits and pushes), never by summaries.
- **Standing down.** `cancel` the Codex job and stop the wrapper. The worktree stays for inspection.
- **Limits:**
  - Codex is a leaf. It does not spawn pstack subagents, and it does not commit, push, or reach the network.
  - The pair never writes another agent's branch.
  - Merge authority follows the playbook as for any owner.
- **Model names** are whatever the user's Codex accepts. setup-pstack records them (below), and pstack-codex never hardcodes a catalog.

### 4. Customizations on `main` (the ledger of `scotu/pstack-claude-code`)

These mirror Hermes' C-001 to C-005, rewritten for Claude Code. They are new entries in this repo's own ledger, and the IDs can restart at C-001.

- **C-001 `pstack-economy` (Claude Code).** It carries over from Hermes:
  - the lean-widths table, unchanged;
  - divided versus duplicated work;
  - the going-wide approval and cost statement;
  - the free-executor exemption, which has no free executor today and so stays dormant.

  The executors are:
  - `parent` (this session);
  - `agent:<opus|sonnet|haiku|fable> <effort>`, an `Agent` subagent with `model` and `effort`;
  - `codex:<model> <effort>`.

  Cost class is `subscription` for both families, with the quota tracked per family. **The routing rule replaces Hermes' "cheapest at tier":**
  1. Meet the role's tier: `light`, `strong` or `frontier`.
  2. When a duplicated-work step has two or more seats at lean width, draw them from both families. For example, arena's 2 candidates are one Claude and one Codex. Divided work picks per seat by tier and headroom, and isn't required to mix.
  3. A single reviewer, judge or verifier comes from the family that did not write the work.
  4. Otherwise, at equal tier, prefer the family with more quota headroom when known, else the session's family.

  It also defines the audit tick (below).
- **C-002 hook.** Whatever upstream uses to make agents read the adapter tells them to load `pstack-economy` before any fan-out, loop or role-model choice. When they explain cost or widths, they give the lean widths. This is the Claude Code twin of Hermes' C-002. The builder finds the hook point in upstream's tree, for example the adapter itself, the per-skill pointer, or poteto-mode's Subagents section.
- **C-003 setup-pstack.** It builds the inventory: Claude models from the `Agent` tool schema with their efforts, plus Codex availability and the Codex models the user confirms. Each model gets a family, a tier, `tools` and an executor. It recommends role defaults that alternate families: author and verifier from different families, panel entries interleaved, with lean panel lengths like Hermes'. It writes `~/.claude/rules/pstack-models.md` in upstream's format, with the inventory as comment lines. When Codex is unavailable, the defaults are Claude-only with a note.
- **C-004.** One live lane per distinct check, with ten only when going wide. This is the same intent as Hermes, applied to the Claude Code tree's `multi-phase-plan.md` and `check-plan.mjs`.
- **C-005 audit tick.** Programs arm the self-contained watcher tick (below) instead of the hourly root loop, which is reserved for going wide. `check-plan.mjs` accepts the watcher's marker.

### 5. Audit tick (self-contained watcher)

- **Program dir:** `~/.claude/pstack-programs/<program>/`. It holds:
  - `plan.txt`: the plan path, the playbook, and the session to report to;
  - `owners.tsv`: Hermes' columns plus `executor` (`claude` or `codex`) and `job` (the Claude agent id, or for a Codex pair the Codex job id and the wrapper's agent id);
  - the watcher's last snapshot.
- **Watcher:** a script shipped in `pstack-economy`, adapted from Hermes' `pstack-audit-watch.py`. The root starts it with **Bash `run_in_background`**, not Monitor. A Monitor watch expires after at most 30 minutes, and re-arming it costs a turn. A background Bash task has no such cap and notifies once, when it exits. The loop:
  1. Sleep about 15 minutes.
  2. Check each owner:
     - branch head (`git ls-remote`);
     - PR and CI state (`gh`);
     - Codex job state (`codex-companion status --json`) for Codex pairs. A Codex job that ended without a later wrapper commit is a change worth judgment;
     - elapsed time against `expected_minutes`.
  3. Compare with the snapshot.
  4. When nothing changed, print nothing and loop.
  5. On a change worth judgment, print one line per owner concerned and **exit**. A change worth judgment is: past stuck-after with no new side effect, a failed check, a new PR comment from a bot or reviewer, a Codex job that ended, or all work done.

  Output contains no timestamps, so identical states compare equal.
- **On wake,** the root runs the judgment half of the playbook's tick for the owners named, then re-arms the watcher. When no delegated work is left, it doesn't re-arm. It then deletes the program dir.
- **Lifetime:** tied to the session, by design.

### 6. Principles and guards

- The Principles section of the Claude Code ledger reuses P-1 and P-3 verbatim. **P-2 becomes "Runs on Claude Code":** every tool, feature, skill, plugin, subagent type, model slug and path that a skill names exists in Claude Code or has a mapping in upstream's adapter or in `pstack-codex`, and nothing points at a dropped file.
- `tests/test_principles.py` is adapted for this tree:
  - the economy guards are unchanged;
  - the relative-link guard is unchanged;
  - the named-skill, plugin and subagent-type guards check against the adapter plus `pstack-codex`;
  - the known-Cursorisms table keys on the adapter's mappings.
- **One factory process for both targets.** `/pstack-update` takes a target, defaults to both, and runs sync, audit and push per target. `/pstack-install` handles Hermes profiles as today. For Claude Code it runs `claude plugin marketplace update <marketplace>` and `claude plugin update pstack@<marketplace>`, only when `main` equals `origin/main`. The first install is `claude plugin marketplace add scotu/pstack-claude-code` plus `claude plugin install pstack@<marketplace>` at user scope.

## Success checks

- `python3 -m factory sync pstack --target claude-code` builds from `harness/pstack/claude-code`, and `push` refuses it until its audit is complete.
- After install, `/pstack:poteto-mode` loads in a fresh Claude Code session, and `pstack-economy` is reachable from it.
- **With Codex logged in:**
  - `/pstack:setup-pstack` lists Claude and Codex models and writes alternating-family defaults;
  - an arena run at lean width spawns one Claude candidate and one Codex candidate, the Codex one in its own worktree, committed by its wrapper;
  - with no `~/.claude/rules/pstack-models.md`, the same arena run still uses Codex for the non-Claude default seat;
  - a Codex-written feature lands as a PR the wrapper opened, with Codex's sandbox unchanged;
  - an interrogate pass on Claude-written code uses a Codex reviewer.
- **With Codex logged out,** the same runs are Claude-only, with one line saying diversity was lost.
- An autopilot program arms the watcher. The session sees no notification while owners progress normally, and gets one when an owner passes stuck-after.
- `tests/test_principles.py` passes on the Claude Code build.

## Left to the builder

- Where exactly the Codex row and pointer enter the upstream adapter, and where the C-002 hook point is, so that both survive upstream rewording.
- The marketplace name.
- How `factory status` reads Claude Code install state.
- Whether `pstack-codex` drives the companion script or `codex exec` by default, beyond "prefer the companion when installed". Verify the companion runs correctly with a worktree as cwd.
- Watcher implementation details: the language, and how to read Codex job state robustly. Keep Hermes' tested parts.
- Test coverage for the factory changes (per-target path and ref) in the factory's own suite.

## Calls made in writing this up

- The version changes on every publish, and the builder checks Claude Code's update rule (see Port hook 1).
- Non-Claude default slugs run on Codex's default model when Codex is available (see Port hook 2).
- The watcher is a background Bash task, not Monitor (see Audit tick).
- Program dirs live in `~/.claude/pstack-programs/<program>/`.
- The wrapper is a light-tier Claude subagent that reviews Codex's diff for scope only.
