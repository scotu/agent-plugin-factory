# pstack for Claude Code Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `claude-code` target to the factory that builds `scotu/pstack-claude-code` from upstream's Claude Code tree, carries the economy customizations and a Codex executor, and ships through the same audit gate.

**Architecture:**
- **Factory.** Targets get their own upstream `path` and `ref`. A new port hook copies `harness/pstack/claude-code/`, adds a marketplace manifest and the `pstack-codex` overlay, and relinks dropped files.
- **Build repo `main`.** It carries C-001 to C-005, rewritten for Claude Code: economy, the adapter hook, the setup inventory, lean lanes, and the background watcher tick. Its tests check the Principles across the whole tree.
- **Process.** `/pstack-update` and `/pstack-install` become target-aware.

**Tech Stack:** Python 3 stdlib (factory, watcher, tests), Markdown skills, Node (`check-plan.mjs`), git, `gh`, `claude plugin` CLI, Codex CLI / `openai/codex-plugin-cc`.

**Spec:** `docs/specs/2026-10-26-pstack-claude-code-design.md`

## Global Constraints

- Upstream source: `https://github.com/cursor/plugins`, path `harness/pstack/claude-code`, ref `main`.
- Build repo: `git@github.com:scotu/pstack-claude-code.git`, public, default branch `main`. The clone lives at `builds/claude-code/pstack`.
- **Plugin name stays `pstack`.** Commands are `/pstack:<name>` and agents are `pstack:<agent>`.
- **No `version`** in `.claude-plugin/plugin.json` or in the marketplace entry. Claude Code then versions each install by the commit SHA (code.claude.com/docs/en/plugins/loading.md "How Claude Code computes the version"). The upstream version goes into `description` as `(pstack <version>, upstream <sha7>)`.
- Marketplace name `scotu-pstack`. The single entry is `{"name": "pstack", "source": "./"}`.
- Install at user scope from GitHub (`claude plugin marketplace add scotu/pstack-claude-code`), never from the local clone. A local-path marketplace loads source files live, which would bypass the audit gate.
- Model rule file: `~/.claude/rules/pstack-models.md`. Program dirs: `~/.claude/pstack-programs/<program>/`.
- Executors: `parent`, `agent:<opus|sonnet|haiku|fable> <effort>`, `codex:<model> <effort>`. Cost class `subscription` for both families.
- Codex code-writing runs under `workspace-write` with no network. A light-tier Claude wrapper commits, pushes and opens the PR. The pair is the branch's one writer.
- Two families are required for duplicated-work seats at lean width and for the author/verifier split, never for divided work.
- The watcher runs as Bash `run_in_background` (no Monitor) and exits only on a change. Its output carries no timestamps.
- `main` is append-only. Publish only through `python3 -m factory push pstack --target claude-code`.
- Commit trailer on every commit: `Claude-Session: https://claude.ai/code/session_013sRd4dYuAg3Bysp8fiAMwT`.

## Review Focus

1. **Upstream rewords the adapter.** The Codex section and the C-002 hook have to survive an upstream rewrite of `docs/harness/claude-code.md`. Task 3 tests that the port appends the Codex section to whatever adapter text arrives. Task 6 tests the hook line by intent, using a phrase, not a line position.
2. **Codex missing or logged out.** Every Codex path must fall back to Claude and say so in one line. Task 4 asserts the fallback sentence exists, and Task 8 asserts setup-pstack writes Claude-only defaults with the note.
3. **A Codex job that finishes but never gets committed.** The watcher must surface it. Task 7 has `test_codex_job_done_without_commit_escalates`.
4. **The watcher must stay silent while nothing changes.** It must not exit or print on an unchanged snapshot. Task 7 has `test_loop_silent_until_change`.
5. **Hermes regressions from the per-target config.** Existing `hermes` behavior must be identical when a target sets no `path` or `ref`. Task 1 runs the full suite and adds `test_target_without_override_uses_upstream_path`.

---

### Task 1: Per-target upstream path and ref

**Files:**
- Modify: `factory/config.py` (Target, load)
- Modify: `factory/build.py` (`sync`: use target values)
- Modify: `factory/status.py` (ahead count and stamp per target)
- Modify: `factory/__main__.py` (cmd_status unchanged; check `--target` plumbing)
- Test: `tests/test_config.py`, `tests/test_sync.py`

**Interfaces:**
- Produces: `config.Target(name, build_repo, plugin_key, path: str | None = None, ref: str | None = None)`, plus `config.Plugin.source(target: str) -> tuple[str, str]`, which returns `(path, ref)` with the target's override or the plugin default.

- [ ] **Step 1: Write failing tests**

`tests/test_config.py`:
- `test_target_overrides_path_and_ref`: a plugin.toml with `[targets.cc] build_repo="x", path="harness/p/cc", ref="dev"`. Assert `plugin.source("cc") == ("harness/p/cc", "dev")`.
- `test_target_without_override_uses_upstream_path`: assert `plugin.source("hermes") == (plugin.path, plugin.ref)`.

`tests/test_sync.py`:
- `test_target_path_builds_from_its_subdir`. In the Sandbox, write `plug2/plugin.json` and `plug2/a.txt` upstream. Add `[targets.cc]` with `path="plug2"` and its own bare remote (create it with `git init --bare -b main`, then push an `upstream` branch with an empty commit and a `main` branch with the ledger, mirroring `new._init_build_repo`). Run `build.sync(root, "demo", "cc")`. Assert the clone at `builds/cc/demo` has `a.txt` from `plug2`, and that `UPSTREAM` contains `path: plug2`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest tests.test_config tests.test_sync -v`
Expected: FAIL. `Target` has no `path`, and `Plugin` has no `source`.

- [ ] **Step 3: Implement**
- `config.load` reads optional `path`/`ref` per target.
- `sync()` uses `plugin.source(target)` for `upstream.fetch` and for the `UPSTREAM` stamp.
- `status.lines` uses it for `count_ahead`.

- [ ] **Step 4: Run the full suite**

Run: `python3 -m unittest discover -s tests`
Expected: OK, with all prior tests passing.

- [ ] **Step 5: Commit** (`factory: per-target upstream path and ref`)

### Task 2: Add a target to an existing plugin; Claude Code install state

**Files:**
- Modify: `factory/new.py` (add `add_target`)
- Modify: `factory/__main__.py` (`new` accepts an existing plugin when `--target` is new)
- Modify: `factory/install.py` (add `claude_code_installed`)
- Modify: `factory/status.py` (installed list per target)
- Test: `tests/test_new.py`, `tests/test_install_status.py`

**Interfaces:**
- Produces:
  - `new.add_target(root, name, target, remote, *, github_repo=None, public=True, path=None, ref=None) -> Path`. It creates the build repo (the same `_init_build_repo` flow), appends `[targets.<target>]` to `plugin.toml`, and writes the stub `plugins/<name>/<target>/port.py` only if missing.
  - `install.claude_code_installed(plugins_json: Path, plugin_id: str) -> list[tuple[str, str]]`. It returns `[(scope, gitCommitSha)]` from `installed_plugins.json` `plugins[plugin_id]`.
  - `install.DEFAULT_CC_PLUGINS = Path.home() / ".claude/plugins/installed_plugins.json"`.
- `config.Target` gains `marketplace: str | None = None`, read from the target key `marketplace`.
- Status prints `installed: user@<sha7>` for a target whose `marketplace` is set, with plugin id `<plugin_key>@<marketplace>`. Targets without it keep the Hermes profile lookup.

- [ ] **Step 1: Write failing tests**
- `test_add_target_to_existing_plugin`: after `new(...)` for `demo`, call `add_target(root, "demo", "cc", remote2_uri, path="plug2")`. Assert `config.load(root, "demo").targets["cc"].path == "plug2"`. Assert the remote has `main` and `upstream` branches, and that the existing `hermes/port.py` is untouched.
- `test_add_target_refuses_existing_target`: raises `ConfigError` "already has target".
- `test_claude_code_installed_reads_commit`: write a fake `installed_plugins.json` with `{"version": 2, "plugins": {"pstack@scotu-pstack": [{"scope": "user", "gitCommitSha": "abc1234def"}]}}`. Assert the result is `[("user", "abc1234def")]`. A missing file gives `[]`.
- `test_status_line_claude_code`: a `cc` target with `marketplace` set. The status line contains `installed: user@abc1234`.

- [ ] **Step 2: Run them to see them fail.** Run: `python3 -m unittest tests.test_new tests.test_install_status -v`
- [ ] **Step 3: Implement** the signatures above. `--cc-plugins` is a hidden CLI option next to `--profiles`, for tests.
- [ ] **Step 4: Full suite.** Run: `python3 -m unittest discover -s tests`. Expected: OK.
- [ ] **Step 5: Commit** (`factory: add a target to an existing plugin; Claude Code install state`)

### Task 3: Claude Code port hook

**Files:**
- Create: `plugins/pstack/claude-code/port.py`
- Create: `plugins/pstack/claude-code/overlay/skills/pstack-codex/SKILL.md` (stub here; content in Task 4)
- Create: `plugins/pstack/claude-code/overlay/adapter-codex.md`
- Test: `tests/test_port_pstack_claude_code.py`

**Interfaces:**
- Produces: `port(src, out, ctx)`. Behavior:
  1. Copy `src` (the upstream Claude Code tree) to `out`, ignoring `node_modules` and `.DS_Store`.
  2. Rewrite `.claude-plugin/plugin.json` and the root `plugin.json` (if present). Remove `version`, and set `description` to `<upstream description> (pstack <version>, upstream <sha7>)`.
  3. Write `.claude-plugin/marketplace.json`: `{"name": "scotu-pstack", "owner": {"name": "scotu"}, "plugins": [{"name": "pstack", "source": "./", "description": <same>}]}`.
  4. Copy `overlay/skills/*` into `out/skills/`.
  5. Append `overlay/adapter-codex.md` to `out/docs/harness/claude-code.md`, after a blank line.
  6. Run `relink(out, src, sha)`. It is the Hermes `relink` logic with `UPSTREAM_BLOB = "https://github.com/cursor/plugins/blob/{sha}/harness/pstack/claude-code/{path}"`. Additionally, any existing `https://github.com/cursor/plugins/blob/main/pstack/...` link becomes pinned to `{sha}`.
  7. Set `ctx.version` to the upstream version.
- Factory config: add `[targets.claude-code]` to `plugins/pstack/plugin.toml` with `build_repo`, `plugin_key = "pstack"`, `path = "harness/pstack/claude-code"`, and `marketplace = "scotu-pstack"`. This happens in Task 5 through `add_target`, so don't hand-edit it here.

- [ ] **Step 1: Write failing tests.** Use a fixture tree built in `tmp` with `.claude-plugin/plugin.json` (version `9.9.9`), `skills/a/SKILL.md` linking `[g](../../docs/guide/missing.md)`, and `docs/harness/claude-code.md` holding "# pstack in Claude Code\n". Load the hook with `factory.build.load_hook`, and call it with `ctx = Context("pstack", "claude-code", here, "a"*40, "main")`.
  - `test_manifest_has_no_version_and_names_upstream`: `"version" not in manifest`, and `"(pstack 9.9.9, upstream aaaaaaa)" in manifest["description"]`.
  - `test_marketplace_lists_pstack_at_root`: `json.load(...)["plugins"] == [{"name": "pstack", "source": "./", "description": ...}]`, and the name is `scotu-pstack`.
  - `test_adapter_gets_codex_section`: the adapter text starts with the upstream text and contains `## Codex`.
  - `test_overlay_skill_present`: `out/skills/pstack-codex/SKILL.md` exists with `name: pstack-codex`.
  - `test_dropped_link_pinned`: the link becomes `https://github.com/cursor/plugins/blob/aaaa…/harness/pstack/claude-code/docs/guide/missing.md` when that file exists in `src`. It is left as is (dangling) when it exists nowhere.
- [ ] **Step 2: Run them to see them fail.** Run: `python3 -m unittest tests.test_port_pstack_claude_code -v`
- [ ] **Step 3: Implement `port.py`.** `adapter-codex.md` content (exact, the decided policy):

```markdown
## Codex

When Codex is available, it is pstack's second model family in Claude Code. Load the `pstack-codex` skill (`/pstack:pstack-codex`) for how to run a Codex agent.

| Cursor | Claude Code |
| --- | --- |
| A role value `codex <model> <effort>` | A Codex agent per `pstack-codex`, with that model and effort. |
| A `grok-*`, `cursor-grok-*`, `composer-*`, or `gpt-*` slug | When Codex is available: a Codex agent on Codex's configured default model (no `-m`). When it is not: omit `model` as in the Models table, and say in one line that the panel lost its second family. |
```

- [ ] **Step 4: Run the tests to see them pass**, then run the full suite. Expected: OK.
- [ ] **Step 5: Commit** (`pstack claude-code port: copy upstream tree, marketplace, Codex adapter section, relink`)

### Task 4: `pstack-codex` overlay skill

**Files:**
- Modify: `plugins/pstack/claude-code/overlay/skills/pstack-codex/SKILL.md`
- Test: `tests/test_port_pstack_claude_code.py` (content assertions)

**Interfaces:**
- Consumes: the Task 3 port, which copies the overlay.
- Produces:
  - the skill name `pstack-codex`;
  - section headings `## Available`, `## Advisory seat`, `## Code-writing owner`, `## Wrapper loop`, `## Standing down`, `## Limits`, which Tasks 6 to 9 cite by name;
  - the program-record columns `executor` and `job` (Task 7).

- [ ] **Step 1: Write failing tests** (text checks on the overlay file):
  - `test_codex_available_checks`: contains `codex --version`, `codex login status`, `codex-companion.mjs`, and `codex exec`.
  - `test_codex_fallback_sentence`: contains "say in one line that" and "Claude".
  - `test_wrapper_owns_git`: the `## Code-writing owner` section contains `workspace-write`, `git worktree add`, "commits", "push", and "gh pr create". The `## Limits` section contains "does not commit, push, or reach the network".
  - `test_advisory_is_read_only`: the `## Advisory seat` section says to run without `--write`.
- [ ] **Step 2: Run them to see them fail.**
- [ ] **Step 3: Write the skill.** Follow spec §3 exactly. Name the companion path as `~/.claude/plugins/cache/openai-codex/codex/*/scripts/codex-companion.mjs`, resolved with a glob to the newest version, and fall back to `codex exec -C <worktree> -s workspace-write [-m <model>] --json "<brief>"`. Advisory seats use `codex exec -s read-only`. Effort goes in `-c model_reasoning_effort=<effort>` for `exec`, or `--effort` for the companion. Before writing, check the companion `task` command with a worktree as cwd: run `node <companion> task --help` and read `task-worker --cwd` in its source. If it can't target a worktree, make `codex exec -C` the default for code-writing owners and say so.
- [ ] **Step 4: Run the tests to see them pass.**
- [ ] **Step 5: Commit** (`pstack claude-code overlay: pstack-codex executor`)

### Task 5: Create the build repo, first sync, and first full audit

**Files:**
- Modify: `plugins/pstack/plugin.toml` (via `add_target`)
- Create in the build clone `builds/claude-code/pstack/`:
  - `CUSTOMIZATIONS.md`: the template from `add_target`, then replace its Principles with P-1 and P-3, copied verbatim from the Hermes ledger, and P-2 "Runs on Claude Code" per spec §6;
  - `audits/<sha12>.md`;
  - `tests/__init__.py`;
  - `tests/test_principles.py`.

**Interfaces:**
- Consumes: Tasks 1 to 4.
- Produces:
  - the build clone at `builds/claude-code/pstack`;
  - `tests/test_principles.py`, with `ADAPTER = ROOT/"docs/harness/claude-code.md"`, `CODEX = ROOT/"skills/pstack-codex/SKILL.md"`, `POLICY = {pstack-economy, pstack-codex, setup-pstack}`, and the guard classes `EconomyPrincipleTest` and `ClaudeCodePrincipleTest`.

- [ ] **Step 1: Create the repo.** Run `python3 -m factory new pstack --target claude-code --upstream https://github.com/cursor/plugins#harness/pstack/claude-code` (the Task 2 path for an existing plugin). Then add `marketplace = "scotu-pstack"` to the target and commit the factory change.
- [ ] **Step 2: Sync.** Run `python3 -m factory sync pstack --target claude-code`. Expected: `merged locally, not pushed`.
- [ ] **Step 3: Write `tests/test_principles.py`.** Adapt the Hermes file:
  - Keep the economy guards and the link guard verbatim.
  - The named-skill guard accepts a name that is a skill dir, appears in `ADAPTER` as `` `/?name` ``, or appears in `CODEX`.
  - The companion-plugin guard checks `ADAPTER`.
  - The subagent-type guard accepts the types the adapter's "Subagent fields" table names (`general-purpose`, `Explore`, `pstack:poteto-agent`, `pstack:comment-sicko`) and the Cursor types it maps (`generalPurpose`, `poteto-agent`, `comment-sicko`).
  - Add `test_non_claude_slugs_mapped`: if any doc names `grok-`, `composer-` or `gpt-`, `ADAPTER` contains `## Codex`.

  Run it. Expected: failures list real gaps, which are input to Step 4.
- [ ] **Step 4: Audit the whole tree.** Run `python3 -m factory audit pstack --target claude-code`. Every path is `A`. Review each row against P-1 to P-3 as `/pstack-update` step 5 describes, splitting rows by skill folder across at most 3 read-only reviewers, per the stay-within-limits skill. Fixes:
  - P-2 gaps go to the Task 3 port or Task 4 overlay; rebuild, and verdicts carry over.
  - P-1 gaps are noted for Tasks 6 to 9 as `C-00N` verdicts.

  Done when every row has a verdict and the test file's guards are either green or failing only on items assigned to Tasks 6 to 9.
- [ ] **Step 5: Commit** in the build clone (`principles and guards for the Claude Code tree`; audit committed with Task 10's final state)

### Task 6: C-001 economy skill and C-002 hook

**Files (build clone):**
- Create: `skills/pstack-economy/SKILL.md`
- Modify: `docs/harness/claude-code.md` (C-002: one line under its first paragraph)
- Modify: `CUSTOMIZATIONS.md` (entries C-001, C-002)
- Test: `tests/test_skills.py`

**Interfaces:**
- Consumes: `pstack-codex` section names (Task 4).
- Produces: economy headings `## Duplicated and divided work`, `## Lean widths`, `## Going wide`, `## Routing`, and `## Audit tick` (Task 7 fills the last).

- [ ] **Step 1: Write failing tests** (`tests/test_skills.py`):
  - `EconomySkillTest.test_sections`: the five headings above.
  - `test_lean_table_matches_hermes`: the Lean widths table rows have the same Pattern column as Hermes'. Copy the expected list into the test: swarm coverage slices; swarm races and best-of; architect; arena; interrogate; reflect, why, how, poteto-mode subagents; live verification; autopilot audit tick; second-opinion profiles is replaced by `second-opinion Codex runs (/codex:review, /codex:rescue)`.
  - `test_routing_rule`: contains "both families", "family that did not write", and "Divided work" with "not required to mix". Does not contain "cheapest executor".
  - `test_executors`: contains `agent:<opus|sonnet|haiku|fable> <effort>` and `codex:<model> <effort>`.
  - `OnAdapterHookTest`: the adapter contains `pstack-economy` and "lean widths" within its first 15 lines.
- [ ] **Step 2: Run them to see them fail.** Run: `python3 -m unittest tests.test_skills -v`
- [ ] **Step 3: Write the skill.** Port the Hermes `pstack-economy` text, keeping divided versus duplicated work, going wide, and the free-executor exemption marked dormant. Replace Routing with spec §4 C-001's four-step rule, and Hermes executors with the Claude Code executors. Replace "Split audit tick" with a `## Audit tick` heading that Task 7 fills. Add the C-002 line to the adapter: "Before any fan-out, loop, or role-model choice, read the `pstack-economy` skill (`/pstack:pstack-economy`) and apply it; its lean widths override the widths skills state, and when you explain cost or widths, give its lean widths." Write ledger entries C-001 and C-002 in the Hermes format, with Touches and Checks naming these tests.
- [ ] **Step 4: Run the tests to see them pass**, then run the full build-repo suite.
- [ ] **Step 5: Commit** two commits, `C-001: …` and `C-002: …`.

### Task 7: C-005 background watcher

**Files (build clone):**
- Create: `skills/pstack-economy/audit-watch/pstack-audit-watch.py`
- Modify: `skills/pstack-economy/SKILL.md` (`## Audit tick`)
- Test: `tests/test_audit_watch.py`

**Interfaces:**
- Consumes: the `owners.tsv` columns `owner remote repo branch pr expected_minutes started_at executor job`.
- Produces:
  - `snapshot(dir: Path) -> list[str]`: one stable line per owner, as Hermes' format, plus `codex=<running|done|failed|cancelled|unknown|->` for `executor=codex`;
  - `watch(dir: Path, interval: int, max_cycles: int | None = None) -> list[str]`: loops sleep→snapshot. It returns and prints the changed lines when the snapshot differs from the saved one, or when any line has `STUCK`/`ERROR`. It never prints while the snapshot is unchanged;
  - CLI: `pstack-audit-watch.py [--once | --watch] [--interval 900]`. `--once` keeps Hermes behavior: print the snapshot and exit 0.

- [ ] **Step 1: Write failing tests.** Copy the Hermes `tests/test_audit_watch.py` cases for `--once`, then add:
  - `test_loop_silent_until_change`: with stubbed `git` and `gh` on PATH, as in the Hermes tests, run `watch(dir, interval=0, max_cycles=3)` with no change. Assert it returns `[]`, prints nothing, and exits after the cycles.
  - `test_loop_exits_on_new_head`: change the stub's head between cycles. Assert the returned lines name that owner.
  - `test_codex_job_done_without_commit_escalates`: `executor=codex`, with the companion stub reporting `completed` and the head unchanged since start. Assert the line contains `codex=done` and is returned.
  - `test_no_timestamps`: the snapshot lines match no `\d{4}-\d{2}-\d{2}` and no epoch-like value.
- [ ] **Step 2: Run them to see them fail.**
- [ ] **Step 3: Implement.** Start from the Hermes script. Read Codex state with `node <companion> status <job> --json`, using the companion path glob from Task 4. Any failure gives `unknown`. Write `## Audit tick` in the economy skill:
  1. The root creates the program dir with `plan.txt` and `owners.tsv`.
  2. It copies the script there and starts it with Bash `run_in_background`: `python3 pstack-audit-watch.py --watch --interval 900`.
  3. On the exit notification, it runs the judgment half for the named owners and re-arms the watcher.
  4. When no delegated work is left, it doesn't re-arm and it deletes the program dir.

  It never uses Monitor, and the hourly `/loop 1h` tick is only for going wide. Add ledger entry C-005.
- [ ] **Step 4: Run the tests to see them pass**, then the suite.
- [ ] **Step 5: Commit** (`C-005: background watcher audit tick`)

### Task 8: C-003 setup-pstack inventory

**Files (build clone):**
- Modify: `skills/setup-pstack/SKILL.md`
- Modify: `CUSTOMIZATIONS.md` (C-003)
- Test: `tests/test_skills.py` (`SetupInventoryTest`)

- [ ] **Step 1: Write failing tests:**
  - `test_inventory_fields`: the skill contains "family", "tier", "tools", "executor", `codex login status`, and `~/.claude/rules/pstack-models.md`.
  - `test_alternating_defaults`: the skill's default role block puts a `codex` entry second in `arena runners`, `interrogate reviewers`, and `architect runners`, and names the Claude-only fallback note.
  - `test_lean_panel_lengths`: the defaults list one entry for `interrogate reviewers` and `architect runners`, and two for `arena runners`.
- [ ] **Step 2: Run them to see them fail.**
- [ ] **Step 3: Edit setup-pstack.** Keep upstream's steps and add:
  - an inventory step: Claude models from the `Agent` schema, plus Codex detection and user-confirmed Codex models;
  - family-alternating defaults per spec §4 C-003;
  - the inventory written as comment lines at the top of the rule file.

  Add ledger entry C-003.
- [ ] **Step 4: Run the tests to see them pass.**
- [ ] **Step 5: Commit** (`C-003: …`)

### Task 9: C-004 lanes and C-005 playbook text

**Files (build clone):**
- Modify: `skills/poteto-mode/playbooks/multi-phase-plan.md`, `autopilot-full.md`, `autopilot-stack.md`
- Modify: `skills/poteto-mode/scripts/check-plan.mjs`
- Modify: `CUSTOMIZATIONS.md` (C-004, and C-005's Touches)
- Test: `tests/test_check_plan.py` (copy from Hermes and adapt the marker), `tests/test_principles.py`

- [ ] **Step 1: Write failing tests.** Copy the Hermes `tests/test_check_plan.py`. Change the program-marker expectation from `pstack-audit-` to `pstack-audit-watch`. `EconomyPrincipleTest` must also pass.
- [ ] **Step 2: Run them to see them fail.** Run: `python3 -m unittest tests.test_check_plan tests.test_principles -v`
- [ ] **Step 3: Apply the intents.**
  - C-004 is Hermes' intent: one lane per distinct check, `(N lanes)`, and ten only when going wide.
  - In the playbooks, the tick is armed per `pstack-economy` `## Audit tick`, and `/loop 1h` is reserved for going wide. Re-apply the intent in this tree's wording, not Hermes' sentences.
  - `check-plan.mjs` accepts `/loop 1h` or `pstack-audit-watch` as the marker.
- [ ] **Step 4: Run the tests to see them pass.** Run the full suite and `cd skills/poteto-mode/scripts && bun test check-plan.test.ts` if `bun` is present.
- [ ] **Step 5: Commit** (`C-004: …`, `C-005: playbooks arm the background watcher`)

### Task 10: Target-aware process skills, publish, install, live checks

**Files:**
- Modify: `.claude/skills/pstack-update/SKILL.md`, `.claude/skills/pstack-install/SKILL.md`, `README.md` (factory)
- Commit in the build clone: `audits/<sha12>.md` (complete)

- [ ] **Step 1: Make the skills target-aware.**
  - `/pstack-update [hermes|claude-code]`: with no argument it runs both, one after the other. Commands get `--target <t>`, and the clone path is `builds/<t>/pstack`.
  - `/pstack-install` gains a Claude Code branch:
    1. `main == origin/main`.
    2. `claude plugin marketplace update scotu-pstack`.
    3. `claude plugin update pstack@scotu-pstack`.
    4. Verify `installed_plugins.json` `gitCommitSha` equals `main`.
    5. A first install is `claude plugin marketplace add scotu/pstack-claude-code` then `claude plugin install pstack@scotu-pstack --scope user`. Ask before a first install.
  - README: a "pstack on Claude Code" section mirroring "pstack on Hermes", listing the port's edits.
- [ ] **Step 2: Check the audit is complete.** Run `python3 -m factory audit pstack --target claude-code`. Expected: `complete`. Run the build-repo suite. Expected: OK.
- [ ] **Step 3: Publish** (ask the user first; outward-facing). Run `python3 -m factory push pstack --target claude-code`, then push the factory repo.
- [ ] **Step 4: Install** (ask the user first). Then in a fresh `claude -p` session, check each item:
  - `/pstack:poteto-mode` loads;
  - `pstack-economy` is reachable;
  - the manifest shows no `version`;
  - `factory status pstack` shows `installed: user@<main sha7>`.
- [ ] **Step 5: Live success checks** from the spec, run with the user present: setup-pstack with Codex logged in; one lean arena run (one Claude and one Codex candidate, the Codex one committed by its wrapper); interrogate with a Codex reviewer; the same with Codex logged out; the watcher silent, then escalating on a stuck owner. Record the results in the final report. Fix gaps as `C-NNN` or `port` and go round again.
- [ ] **Step 6: Commit** (`process: /pstack-update and /pstack-install handle the claude-code target`)
