# pstack Economy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make pstack economical by default, as customizations C-001 to C-005 on `main` of the build repo `scotu/pstack-hermes`.
- Lean widths for duplicated work.
- Go wide only with approval for that task.
- Routing by tier from a per-profile model inventory.
- A split audit tick: a free cron watcher plus a paid root that acts on its escalations.

**Architecture:**
- A new `pstack-economy` skill holds the policy, and `pstack-on-hermes` points every skill at it.
- `setup-pstack` builds the inventory.
- Targeted edits to the poteto-mode playbooks and `check-plan.mjs` cover the places where upstream enforces width.
- A new monitor script and watcher prompt implement the split tick.
- Every change is a `C-NNN` commit plus a `CUSTOMIZATIONS.md` entry in the build clone.

**Tech Stack:** Markdown skills, Node (`check-plan.mjs`, existing), Python 3 standard library (watcher script and tests, `unittest`), git, `gh`, and the Hermes CLI (`cron`, `plugins`).

**Spec:** `docs/specs/2026-10-04-pstack-economy-design.md` (factory repo)

## Global Constraints

- Every edit goes in the build clone `/Users/matteo/Development/agents/agent-plugin-factory/builds/hermes/pstack` on branch `main`. Never edit branch `upstream`, and never edit the factory overlay `plugins/pstack/hermes/overlay/`.
- Each commit message starts with its ledger ID, `C-00N: …`. Each ID gets one entry appended to `CUSTOMIZATIONS.md` in the format that file defines, with `Spec: https://github.com/scotu/agent-plugin-factory/blob/main/docs/specs/2026-10-04-pstack-economy-design.md`.
- Commit with your normal git identity. Push only in Task 7. Never rebase or force-push `main`.
- Skill names: the frontmatter `name:` must equal the folder name. The namespace for skill references is `agent-plugin-pstack-7171b73f:<name>`.
- Cost classes are exactly `self-hosted`, `subscription`, `per-token`. Tiers are exactly `frontier`, `strong`, `light`. Executors are `parent`, `delegate`, `profile:<name>`, `cron`.
- Lean role defaults: `architect runners: parent`, `arena runners: parent, delegate`, `arena cross-judge pool: parent`, `interrogate reviewers: delegate`.
- Cron job name: `pstack-audit-<program>`. Monitor script: `pstack-audit-watch.py`, installed into `~/.hermes/scripts/`. A watcher that finds nothing to escalate replies `[SILENT]`.
- Tests live in `tests/` at the build-repo root (a new folder, only on `main`). Run them with `python3 -m unittest discover -s tests -v` from the clone root.
- Text added to playbooks must not change the prose that `check-plan.mjs` enforces on plans. Plan templates must still pass the script's prose checks: no long dashes, no curly quotes, no mid-sentence colons outside backticks.

## Review Focus

1. **Duplicated-work panels whose `pstack-models.md` already lists several entries.** Profiles that ran the old `setup-pstack` have 3-entry panels. Lean must still use one entry. Test: `test_economy_states_first_entry_rule` (Task 1).
2. **A plan that states a lean lane count but numbers its lanes wrongly** (gaps, or more lanes than stated) must still fail. Test: `test_lean_count_mismatch_fails` (Task 4).
3. **`gh pr checks` exits non-zero while checks are pending or failing** and still prints JSON. The watcher must read that JSON, not report `unknown`. Test: `test_checks_summary_reads_json_on_nonzero_exit` (Task 5).
4. **Watcher state across a new push.** `STUCK` must clear when the owner pushes, and must not reappear until the new head has been idle past the expected runtime. Test: `test_stuck_clears_on_push` (Task 5).
5. **A malformed `owners.tsv` row** must print one stable error line and not crash, so the watcher escalates instead of failing silently. Test: `test_malformed_row` (Task 5).

---

## File Structure (build clone)

```
skills/pstack-economy/SKILL.md                      C-001 policy skill (new)
skills/pstack-economy/audit-watch/pstack-audit-watch.py   C-005 monitor script (new)
skills/pstack-economy/audit-watch/watcher-prompt.md       C-005 watcher agent prompt (new)
skills/pstack-on-hermes/SKILL.md                    C-002 one bullet
skills/setup-pstack/SKILL.md                        C-003 inventory + lean defaults (full rewrite)
skills/poteto-mode/scripts/check-plan.mjs           C-004 lane count, C-005 program marker
skills/poteto-mode/playbooks/multi-phase-plan.md    C-004 lane text, C-005 tick text
skills/poteto-mode/playbooks/autopilot-full.md      C-005 tick text
skills/poteto-mode/playbooks/autopilot-stack.md     C-005 tick text
tests/test_skills.py                                text checks for C-001..C-003, C-005 (new)
tests/test_check_plan.py                            check-plan.mjs behavior (new)
tests/test_audit_watch.py                           watcher script behavior (new)
CUSTOMIZATIONS.md                                   one entry per C-ID
```

All commands below run from `/Users/matteo/Development/agents/agent-plugin-factory/builds/hermes/pstack` unless stated otherwise.

---

### Task 1: C-001 `pstack-economy` skill

**Files:**
- Create: `skills/pstack-economy/SKILL.md`, `tests/__init__.py` (empty), `tests/test_skills.py`
- Modify: `CUSTOMIZATIONS.md` (append the C-001 entry)

**Interfaces:**
- Produces:
  - Skill `agent-plugin-pstack-7171b73f:pstack-economy`, with sections `## Duplicated and divided work`, `## Lean widths`, `## Going wide`, `## Routing`, and `## Split audit tick`.
  - It refers to `audit-watch/pstack-audit-watch.py` and `audit-watch/watcher-prompt.md` (created in Task 5).
  - `tests/test_skills.py` with helper `skill(name) -> str` and `frontmatter_name(text) -> str`.

- [ ] **Step 1: Write the failing test** `tests/test_skills.py`:

```python
"""Text checks for the economy customizations (C-001, C-002, C-003, C-005)."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"


def skill(name: str) -> str:
    return (SKILLS / name / "SKILL.md").read_text()


def frontmatter_name(text: str) -> str:
    m = re.match(r"\A---\n(.*?)\n---\n", text, re.S)
    return re.search(r"^name:\s*(\S+)", m.group(1), re.M).group(1) if m else ""


class SkillNamesTest(unittest.TestCase):
    def test_every_skill_name_matches_its_folder(self):
        for md in sorted(SKILLS.glob("*/SKILL.md")):
            self.assertEqual(frontmatter_name(md.read_text()), md.parent.name, md)


class EconomySkillTest(unittest.TestCase):
    def test_sections(self):
        text = skill("pstack-economy")
        for heading in ("## Duplicated and divided work", "## Lean widths", "## Going wide",
                        "## Routing", "## Split audit tick"):
            self.assertIn(heading, text)

    def test_economy_states_first_entry_rule(self):
        self.assertIn("use only the first entry", skill("pstack-economy"))

    def test_economy_states_per_token_rule(self):
        text = skill("pstack-economy")
        self.assertIn("per-token", text)
        self.assertIn("only executor at the tier", text)

    def test_economy_points_at_watcher_files(self):
        text = skill("pstack-economy")
        self.assertIn("audit-watch/pstack-audit-watch.py", text)
        self.assertIn("audit-watch/watcher-prompt.md", text)
        self.assertIn("pstack-audit-<program>", text)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests and confirm they fail.** Run `python3 -m unittest tests.test_skills -v`. Expected: `test_every_skill_name_matches_its_folder` passes. The four `EconomySkillTest` tests fail with `FileNotFoundError` for `skills/pstack-economy/SKILL.md`.

- [ ] **Step 3: Write** `skills/pstack-economy/SKILL.md`:

````markdown
---
name: pstack-economy
description: >-
  Spending rules for pstack on this profile. Lean by default: cut duplicated
  agent work (races, same-prompt panels, repeated lanes, polling loops), keep
  divided work, ask before going wide, and route each role to the cheapest
  executor that meets its tier. Apply before any pstack fan-out, loop, or
  role-model choice.
---

# pstack economy

Upstream pstack assumes model calls are cheap. On this profile they are not. Apply these rules whenever a pstack skill would spawn more than one agent, arm a loop, or pick a model for a role. They override the widths that pstack's skills state. They never weaken a check. They only limit how many copies of the same check run.

## Duplicated and divided work

- **Divided work:** several agents each do a different piece. Examples are swarm coverage slices, `how` explorers on distinct angles, `why` investigators per evidence category, `reflect`'s three lenses, and poteto-mode delegates. Run it as the skill says, with subagents as needed.
- **Duplicated work:** several agents do the same piece. Examples are races, best-of, several candidates for one artifact, several reviewers with one prompt, repeated verification lanes, and periodic re-checks. Run the lean width below.
- **Free-executor exemption.** Duplicated work may run on a `self-hosted` executor (see Routing) when its output stays advisory and you read only a short report. Advisory means it never merges, dispatches, stands down, or decides.

For a duplicated-work panel role in `pstack-models.md` (architect runners, arena runners, arena cross-judge pool, interrogate reviewers), use only the first entry, or the first two for arena runners, unless the user approved going wide. Profiles set up before this skill may list three entries; that is the go-wide width, not the default.

## Lean widths

| Pattern | Lean default | Go wide (upstream) |
|---|---|---|
| swarm, coverage slices | one worker per slice, no cap | — |
| swarm, races and best-of | no race, one worker per arm | upstream races |
| architect | one design by the parent that names the alternatives it rejected and why, with no runners | 2 to 3 runners |
| arena | 2 candidates on different executors or model families, judged by the parent against the rubric, with no separate cross-judge | 3 candidates plus a cross-judge |
| interrogate | 1 reviewer on an executor whose model differs from the author's, plus optionally one free advisory reviewer on a `self-hosted` executor | one reviewer per configured model |
| reflect, why, how, poteto-mode subagents | as upstream (divided work) | — |
| live verification | one lane per distinct check, with no repeats | ten lanes |
| autopilot audit tick | the split audit tick when `pstack-models.md` has a `cron` model, otherwise none (audit when owners report back or when asked) | full hourly `/loop 1h` tick on the root |
| second-opinion profiles (`message_agent`) | only when the user asks | as configured |

Event-driven waits (a `/loop` that watches CI or a merge) stay as upstream. They wait for something to happen; they don't repeat work.

## Going wide

Before any step wider than lean, post one message that names:
- the pattern;
- the width you want and the lean width it replaces;
- the executors involved, with their models and cost classes from `pstack-models.md`;
- a rough relative cost, for example "about 3x one pass; 2 runs are subscription, 1 is per-token".

Then wait for an explicit yes. "Go wide", "spare no expense", or a named width for the current task ("arena with 3") approves that task only. Approval never carries over to later tasks or sessions. When nobody is watching (autopilot, figure-it-out, the user stepped away), stay lean, and list in your report the steps you would have widened.

## Routing

`pstack-models.md` starts with an inventory: model, provider, cost class (`self-hosted`, `subscription`, `per-token`), tier (`frontier`, `strong`, `light`), `tools` (yes or no), and executor (`parent`, `delegate`, `profile:<name>`, `cron`). If the inventory is missing, treat `parent` and `delegate` as unknown cost, say so once, and suggest running `agent-plugin-pstack-7171b73f:setup-pstack`.

- **Which work needs which tier:**
  - `light`: exploration and grep sweeps, running tests and reporting results, reading transcripts or logs.
  - `strong`: code-writing delegates, reviewers, investigators.
  - `frontier`: judgment, synthesis, the hardest tasks, final picks and verdicts.
- Route each role to the cheapest executor whose model meets its tier. At equal tier, prefer `self-hosted`, then `subscription`, then `per-token`.
- **Per-token rule:** never pick a `per-token` executor unless it is the only executor at the tier the role needs. When a role would land on one, say so before spending.
- A `profile:<name>` executor is used only where the role table names it, never implicitly. It is asynchronous and costs that bot a turn.
- `self-hosted` executors, including the `cron` model, may take duplicated or scheduled work under the free-executor exemption.

## Split audit tick

Use this in place of the hourly `/loop 1h` tick when a program arms its audit tick and `pstack-models.md` has a `cron` model with `tools: yes`. The watcher does the mechanical checks for free. You do the judgment.

1. **Program dir.** Create one outside any repo checkout: `~/.hermes/profiles/<profile>/pstack-programs/<program>/`, or `~/.hermes/pstack-programs/<program>/` for the default profile.
2. **`owners.tsv`.** Write it in the program dir, tab-separated, with this header: `owner remote repo branch pr expected_minutes started_at`.
   - `remote` is the git URL, and `repo` is `owner/name` for `gh`.
   - `pr` is the PR number, or `-` before the PR exists.
   - `started_at` is in epoch seconds.
   - Update it whenever an owner spawns, opens its PR, or finishes.
3. **Install the script.** Copy `audit-watch/pstack-audit-watch.py` from this skill's folder (`plugins/pstack/skills/pstack-economy/` under the profile's Hermes home) into `~/.hermes/scripts/`.
4. **Arm the watcher.** The cron job is named `pstack-audit-<program>`:
   ```
   hermes -p <profile> cron create 15m "$(cat <skill dir>/audit-watch/watcher-prompt.md)" \
     --name pstack-audit-<program> --monitor-script pstack-audit-watch.py \
     --workdir <program dir> --model <cron model> --provider <its provider> --pin \
     --deliver bot-chat:<profile> --failure-deliver local
   ```
   The script runs every 15 minutes. The watcher model runs only when the script's output changes, and replies `[SILENT]` unless something needs you.
5. **On an escalation** (a message from the watcher naming owners), run the judgment half of the playbook's audit tick for those owners only:
   - re-read the playbook from trunk;
   - fix drift;
   - stand down and replace stuck owners;
   - handle failed checks and bot comments.
6. **Teardown.** When no delegated work is left, run `hermes -p <profile> cron remove pstack-audit-<program>`, then delete the program dir.

Without a `cron` model, arm no tick. Audit when an owner reports back and when the user asks. Arm the hourly `/loop 1h` tick only when the user approves going wide.
````

- [ ] **Step 4: Run the tests and confirm they pass.** Run `python3 -m unittest tests.test_skills -v`. Expected: 5 tests OK.

- [ ] **Step 5: Append the ledger entry** to `CUSTOMIZATIONS.md`:

```markdown

## C-001 — pstack-economy: lean-by-default spending policy  [active]
Intent: a pstack-economy skill defines lean widths for duplicated agent work (divided work untouched), per-task go-wide approval with a cost statement, tier routing over the setup-pstack inventory with the per-token rule, and the split audit tick procedure.
Why: upstream assumes cheap LLM calls; this profile pays through subscription quotas, self-hosted and per-token models.
Spec: https://github.com/scotu/agent-plugin-factory/blob/main/docs/specs/2026-10-04-pstack-economy-design.md
Touches: skills/pstack-economy/SKILL.md, tests/test_skills.py
Check: python3 -m unittest tests.test_skills passes
```

- [ ] **Step 6: Commit**

```bash
git add skills/pstack-economy/SKILL.md tests/__init__.py tests/test_skills.py CUSTOMIZATIONS.md
git commit -m "C-001: pstack-economy skill (lean widths, go-wide approval, tier routing, split tick)"
```

---

### Task 2: C-002 hook in `pstack-on-hermes`

**Files:**
- Modify: `skills/pstack-on-hermes/SKILL.md` (insert one bullet at the top of `## Subagents`), `tests/test_skills.py`, `CUSTOMIZATIONS.md`

**Interfaces:**
- Consumes: the skill name `pstack-economy` from Task 1, and the `skill()` helper in `tests/test_skills.py`.

- [ ] **Step 1: Write the failing test.** Add this to `tests/test_skills.py`, before `if __name__`:

```python
class OnHermesHookTest(unittest.TestCase):
    def test_on_hermes_points_at_economy(self):
        text = skill("pstack-on-hermes")
        self.assertIn("agent-plugin-pstack-7171b73f:pstack-economy", text)
        subagents = text.split("## Subagents", 1)[1]
        self.assertIn("pstack-economy", subagents.split("\n- ", 2)[1])
```

- [ ] **Step 2: Run the test and confirm it fails.** Run `python3 -m unittest tests.test_skills.OnHermesHookTest -v`. Expected: FAIL, with `'agent-plugin-pstack-7171b73f:pstack-economy' not found`.

- [ ] **Step 3: Insert the bullet.** In `skills/pstack-on-hermes/SKILL.md`, replace the exact text `## Subagents\n\n` with:

```markdown
## Subagents

- Before any fan-out, loop, or choice of model for a role, load `agent-plugin-pstack-7171b73f:pstack-economy` with `skill_view` and apply it. Its widths and routing override the ones pstack's skills state.
```

followed by a blank line, so the existing first bullet (`` `Task` with any `subagent_type` becomes ... ``) follows unchanged. Apply it with:

```bash
python3 - <<'EOF'
from pathlib import Path
p = Path("skills/pstack-on-hermes/SKILL.md"); s = p.read_text()
old = "## Subagents\n\n"
assert s.count(old) == 1
s = s.replace(old, old + "- Before any fan-out, loop, or choice of model for a role, load `agent-plugin-pstack-7171b73f:pstack-economy` with `skill_view` and apply it. Its widths and routing override the ones pstack's skills state.\n", 1)
p.write_text(s)
EOF
```

- [ ] **Step 4: Run the tests and confirm they pass.** Run `python3 -m unittest tests.test_skills -v`. Expected: 6 tests OK.

- [ ] **Step 5: Append the ledger entry:**

```markdown

## C-002 — pstack-on-hermes: route every fan-out through pstack-economy  [active]
Intent: pstack-on-hermes, which every pstack skill loads first, tells the agent to load and apply pstack-economy before any fan-out, loop, or role-model choice.
Why: one hook makes the economy policy reach all 47 skills without editing each.
Spec: https://github.com/scotu/agent-plugin-factory/blob/main/docs/specs/2026-10-04-pstack-economy-design.md
Touches: skills/pstack-on-hermes/SKILL.md
Check: python3 -m unittest tests.test_skills.OnHermesHookTest passes
```

- [ ] **Step 6: Commit**

```bash
git add skills/pstack-on-hermes/SKILL.md tests/test_skills.py CUSTOMIZATIONS.md
git commit -m "C-002: pstack-on-hermes loads pstack-economy before any fan-out"
```

---

### Task 3: C-003 `setup-pstack` inventory and lean defaults

**Files:**
- Modify: `skills/setup-pstack/SKILL.md` (full rewrite), `tests/test_skills.py`, `CUSTOMIZATIONS.md`

**Interfaces:**
- Produces: the `pstack-models.md` format that Task 1's Routing section reads. The inventory comes first, with columns `model | provider | cost class | tier | tools | executor`, followed by the role table with the lean defaults from Global Constraints.

- [ ] **Step 1: Write the failing test.** Add this to `tests/test_skills.py`:

```python
class SetupInventoryTest(unittest.TestCase):
    def test_inventory_and_lean_defaults(self):
        text = skill("setup-pstack")
        for needle in ("cost class", "self-hosted", "subscription", "per-token", "frontier", "strong", "light",
                       "tools", "cron", "# Models this profile can reach"):
            self.assertIn(needle, text)
        for line in ("architect runners: parent\n", "arena runners: parent, delegate\n",
                     "arena cross-judge pool: parent\n", "interrogate reviewers: delegate\n"):
            self.assertIn(line, text)
        self.assertNotIn("interrogate reviewers: delegate, delegate, delegate", text)
```

- [ ] **Step 2: Run the test and confirm it fails.** Run `python3 -m unittest tests.test_skills.SetupInventoryTest -v`. Expected: FAIL, with `'cost class' not found`.

- [ ] **Step 3: Rewrite** `skills/setup-pstack/SKILL.md`:

````markdown
---
name: setup-pstack
description: >-
  Configure how pstack's roles map onto this Hermes profile's models: an
  inventory of every reachable model with its cost class and capability tier,
  the delegation model for subagents, the cron model for scheduled watchers,
  and which roles run in-session, as subagents, or on another profile. Writes
  pstack-models.md in the profile home. Use for /setup-pstack, "configure
  pstack models", "pstack budget", or changing pstack's model choices.
---

# Setup pstack (Hermes)

Write `pstack-models.md` in this profile's home directory: `~/.hermes/profiles/<profile>/`, or `~/.hermes/` for the default profile. The `pstack-on-hermes` and `pstack-economy` skills read it whenever a pstack skill needs a role's model or a model's cost. Load `agent-plugin-pstack-7171b73f:pstack-on-hermes` and `agent-plugin-pstack-7171b73f:pstack-economy` with `skill_view` first if you have not.

## 1. Load the current state

- The profile's chat model: `hermes -p <profile> config get model`.
- Its subagent model: `hermes -p <profile> config get delegation.model` and `delegation.provider`. Empty means children use the chat model.
- The teammates and their models: `hermes profile list`. These are candidates for `profile:<name>` entries.
- If `pstack-models.md` exists, read it, and treat its inventory and role values as the current choices. Drop any role line whose role is not in the table in step 5, and tell the user which lines you dropped.

## 2. Detect the models

A model is available only if the provider's model list shows it, and the providers' lists are cached in `provider_models_cache.json` in the profile home. Never write a model you have not confirmed. If the cache is empty or stale, ask the user to run `hermes model --refresh`, or to paste the model names they have. Include the teammates' models from step 1.

## 3. Propose the inventory

For each detected model, propose these values and mark them as proposals:

- **Cost class**, from the provider type:
  - a local or self-hosted base URL (Ollama, LM Studio, vLLM, llama.cpp) is `self-hosted`;
  - a plan login through OAuth (for example the Codex or ChatGPT plan, or a Claude subscription) is `subscription`;
  - an API key is `per-token`.

  When unsure, ask.
- **Tier**, from what you know of the model:
  - `frontier`: best reasoning and judgment;
  - `strong`: solid coding and review;
  - `light`: mechanical reading, searching and summarizing.
- **tools:** `yes` if the model handles tool calls reliably. For each `self-hosted` model, ask whether the user has found its tool calling reliable.

## 4. Choose, then confirm

Recommend the slots, then use `clarify` once to confirm the inventory and the slots together:

- **parent** (the chat model): the best `subscription` model.
- **delegate** (`delegation.model`): the cheapest model rated `strong` or better, preferring `self-hosted`, then `subscription`. Every subagent runs here, so this slot decides most of the spend. Also offer `unset` (children use the chat model).
- **cron**: the best `self-hosted` model with `tools: yes`, if any. It runs the split audit tick's watcher. Say plainly that self-hosted `light` models help only as the `cron` model or through a teammate profile, never as an inline subagent.
- **Second-opinion profiles:** offer each teammate on a different model as a `profile:<name>` panel entry. Warn that these replies arrive asynchronously and cost that bot a turn.

Then show the full role table with its values, and ask whether to accept it or change specific roles. Each role takes `parent`, `delegate`, or `profile:<name>`. A panel role takes a list. `pstack-economy` uses only the first entry of a duplicated-work panel (the first two for arena runners) unless the user approves going wide, so extra entries are the go-wide width.

## 5. Write

Apply the subagent model first. Changing it is a config write, so say that before doing it:

```
hermes -p <profile> config set delegation.model <model>
hermes -p <profile> config set delegation.provider <provider>
```

Then overwrite `pstack-models.md` completely, so re-runs stay idempotent:

```
# Models this profile can reach (re-run setup-pstack when they change)
# model | provider | cost class | tier | tools | executor
<model> | <provider> | <self-hosted|subscription|per-token> | <frontier|strong|light> | <yes|no> | <parent|delegate|profile:<name>|cron|(not assigned)>

# pstack role → executor for this Hermes profile. Read by the pstack-on-hermes and pstack-economy skills.
# parent = this session's chat model · delegate = delegate_task child (delegation.model) · profile:<name> = message_agent to that bot
# chat model: <model> · delegation.model: <model or "unset (= chat model)"> · cron model: <model or "none">
feature, refactoring: delegate
bug-fix: delegate
perf-issue: delegate
hillclimb: delegate
judgment and prose: parent
hardest tasks: parent
how explorer: delegate
how explainer: parent
why investigators: delegate
why synthesizer: parent
reflect tooling: delegate
reflect judgment, divergent, synthesizer: parent
arena runners: parent, delegate
arena cross-judge pool: parent
swarm workers: delegate
architect runners: parent
interrogate reviewers: delegate
```

These are the defaults. Replace them with whatever the user confirmed. Mark at most one model `cron`.

## 6. Confirm

Read the file back, and read `delegation.model` back with `config get`. Tell the user what changed. New sessions pick up the delegation model. Re-running this skill updates both.

## 7. Offer a verification skill (optional)

Check whether the project has a way to drive the real app for proof: a `verify-*` skill or an existing harness. If not, offer once: "want a project-local verification skill, so agents can drive the app the way a user does and prove changes work? I can generate one with create-verification-skill." On yes, load and follow `agent-plugin-pstack-7171b73f:create-verification-skill`. On no, move on without pushing.
````

- [ ] **Step 4: Run the tests and confirm they pass.** Run `python3 -m unittest tests.test_skills -v`. Expected: 7 tests OK.

- [ ] **Step 5: Append the ledger entry:**

```markdown

## C-003 — setup-pstack: model inventory and lean panel defaults  [active]
Intent: setup-pstack proposes and confirms an inventory of every reachable model (cost class, tier, tools, executor), recommends parent/delegate/cron slots by cost, and writes lean defaults for duplicated-work panels (architect runners: parent; arena runners: parent, delegate; arena cross-judge pool: parent; interrogate reviewers: delegate).
Why: routing by cost needs to know each model's cost class and capability, and old 3-entry panel defaults made duplicated work the norm.
Spec: https://github.com/scotu/agent-plugin-factory/blob/main/docs/specs/2026-10-04-pstack-economy-design.md
Touches: skills/setup-pstack/SKILL.md
Check: python3 -m unittest tests.test_skills.SetupInventoryTest passes
```

- [ ] **Step 6: Commit**

```bash
git add skills/setup-pstack/SKILL.md tests/test_skills.py CUSTOMIZATIONS.md
git commit -m "C-003: setup-pstack model inventory, slot recommendations, lean panel defaults"
```

---

### Task 4: C-004 lean live-verification lanes

**Files:**
- Create: `tests/test_check_plan.py`
- Modify: `skills/poteto-mode/scripts/check-plan.mjs`, `skills/poteto-mode/playbooks/multi-phase-plan.md` (the `**Verification.**` paragraph and the `**Verify, live.**` template), `CUSTOMIZATIONS.md`

**Interfaces:**
- Produces:
  - `check-plan.mjs` accepts either `Ten lanes on \`<model>\` at the PR head` (lanes numbered exactly 1 to 10) or `One lane per distinct check on \`<model>\` at the PR head (<N> lanes)` (lanes numbered exactly 1 to N, with N at least 1).
  - `tests/test_check_plan.py` with helper `plan(live_line, n_lanes, marker) -> str` and `check(text) -> tuple[int, str]`. Task 6 reuses both.

- [ ] **Step 1: Write the failing test** `tests/test_check_plan.py`:

```python
"""check-plan.mjs behavior for the lean lane count (C-004) and the split audit tick marker (C-005)."""
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "skills" / "poteto-mode" / "scripts" / "check-plan.mjs"
RULE = ("Tests alone are not sufficient verification. "
        "A PR is verified only when its unit, live, and perf boxes are all checked.")
TEN = "Ten lanes on `gpt-6.1-sol` at the PR head, per the boot recipe."
LEAN3 = "One lane per distinct check on `gpt-6.1-sol` at the PR head (3 lanes), per the boot recipe."
LOOP = "- [ ] Arm the audit tick as `/loop 1h` with the tick prompt."
SPLIT = "- [ ] Arm the split audit tick as cron job `pstack-audit-demo`."


def lanes(numbers):
    return "\n".join(f"- [ ] Lane {i}. Scenario {i}. Save `lane{i}.png`. Pass when it renders." for i in numbers)


def plan(live_line, n_lanes, marker=LOOP):
    numbers = range(1, n_lanes + 1) if isinstance(n_lanes, int) else n_lanes
    return f"""# Demo program

A short intro.

## How to read this

One box is one unit of work. Each box names the evidence. Check a box only when its evidence exists. The steps follow playbooks/ in pstack. {RULE}

## Program checklist

### Arm the program

- [ ] Read `git show origin/main:pstack/skills/swarm/SKILL.md` first.
{marker}
- [ ] Post a status message when something changes.

### Spawn owners

- [ ] Spawn one owner.

### PR mechanics

- [ ] Open the PR ready.

### Verdict and merge

- [ ] Merge on a clean verdict.

### Boot recipe

- [ ] Boot the app.

## PR 1. Demo change

**Depends on.** Nothing.

**Files.**

- [ ] `src/a.ts` changes.

**Build.**

- [ ] Build it.

**You see.**

- [ ] The demo works.

**Verify, unit.** {RULE}

- [ ] Run `npm test`.

**Verify, live.** {RULE} {live_line}

{lanes(numbers)}

**Verify, perf.** {RULE}

- [ ] Metric. Load time.
- [ ] Probe. Interleaved runs.
- [ ] Baseline. Trunk first.
- [ ] Rule. Fail above two seconds.

**Review gate.** None. PR 1 is not review-gated.

**Merge.**

- [ ] Squash-merge.

## Close the program

- [ ] Retro.

## Appendix A. Prototype evidence

Nothing yet.
"""


def check(text):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "plan.md"
        path.write_text(text)
        r = subprocess.run(["node", str(SCRIPT), str(path)], capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr


class LaneCountTest(unittest.TestCase):
    def test_ten_lanes_still_pass(self):
        code, out = check(plan(TEN, 10))
        self.assertEqual(code, 0, out)

    def test_lean_lane_count_passes(self):
        code, out = check(plan(LEAN3, 3))
        self.assertEqual(code, 0, out)

    def test_lean_count_mismatch_fails(self):
        for numbers in (4, [1, 2, 4]):
            code, out = check(plan(LEAN3, numbers))
            self.assertEqual(code, 1, out)
            self.assertIn("lanes are", out)

    def test_lean_without_count_fails(self):
        code, out = check(plan("One lane per distinct check on `gpt-6.1-sol` at the PR head.", 3))
        self.assertEqual(code, 1, out)

    def test_no_lane_line_fails(self):
        code, out = check(plan("Some lanes run.", 3))
        self.assertEqual(code, 1, out)
        self.assertIn("Verify, live lacks", out)

    def test_ten_lanes_with_three_fails(self):
        code, out = check(plan(TEN, 3))
        self.assertEqual(code, 1, out)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests and confirm they fail.** Run `python3 -m unittest tests.test_check_plan -v`. Expected:
  - `test_ten_lanes_still_pass`, `test_lean_count_mismatch_fails`, `test_lean_without_count_fails`, `test_no_lane_line_fails` and `test_ten_lanes_with_three_fails` pass.
  - `test_lean_lane_count_passes` fails, with exit 1 and output naming `Verify, live lacks`.

  If `test_ten_lanes_still_pass` fails, the fixture is wrong. Fix the fixture from the script's error output before touching the script.

- [ ] **Step 3: Change `check-plan.mjs`.** Apply this:

```bash
python3 - <<'EOF'
from pathlib import Path
p = Path("skills/poteto-mode/scripts/check-plan.mjs"); s = p.read_text()
def rep(a, b):
    global s
    assert s.count(a) == 1, a
    s = s.replace(a, b)
rep("const LANES = /Ten lanes on `[^`<>]+` at the PR head/;",
    "// C-004 (pstack-economy): \"Ten lanes\" is the go-wide width; lean plans state one lane per distinct check.\n"
    "const LANES = /(Ten lanes|One lane per distinct check) on `[^`<>]+` at the PR head(?: \\((\\d+) lanes?\\))?/;")
rep("""		if (!LANES.test(live.rest)) fail(live.n, `${pr.title}: Verify, live lacks "Ten lanes on \\`<swarm workers model>\\` at the PR head" with the model filled in`);""",
    """		const laneLine = live.rest.match(LANES);
		const expected = !laneLine ? 10 : laneLine[1] === "Ten lanes" ? 10 : Number(laneLine[2] ?? 0);
		if (!laneLine || expected < 1) fail(live.n, `${pr.title}: Verify, live lacks "Ten lanes on \\`<swarm workers model>\\` at the PR head" or "One lane per distinct check on \\`<swarm workers model>\\` at the PR head (<N> lanes)" with the model filled in`);""")
rep("""		if (numbers.join(",") !== "1,2,3,4,5,6,7,8,9,10") fail(live.n, `${pr.title}: lanes are [${numbers.join(",")}], expected 1 to 10`);""",
    """		const want = Array.from({ length: Math.max(expected, 1) }, (_, i) => i + 1).join(",");
		if (numbers.join(",") !== want) fail(live.n, `${pr.title}: lanes are [${numbers.join(",")}], expected 1 to ${Math.max(expected, 1)}`);""")
p.write_text(s)
EOF
```

- [ ] **Step 4: Run the tests and confirm they pass.** Run `python3 -m unittest tests.test_check_plan -v`. Expected: 6 tests OK.

- [ ] **Step 5: Update the playbook text** in `skills/poteto-mode/playbooks/multi-phase-plan.md`:

```bash
python3 - <<'EOF'
from pathlib import Path
p = Path("skills/poteto-mode/playbooks/multi-phase-plan.md"); s = p.read_text()
def rep(a, b):
    global s
    assert s.count(a) == 1, a
    s = s.replace(a, b)
rep("Ten lanes at the PR head drive the real surface through its control skill, per the **swarm** skill, on the `swarm workers` model (default `grok-4.7-xhigh-fast`).",
    "One lane per distinct check at the PR head drives the real surface through its control skill, per the **swarm** skill, on the `swarm workers` model (default `grok-4.7-xhigh-fast`). A distinct check is a scenario no other lane covers, and no lane repeats another. Ten lanes is the go-wide width from the **pstack-economy** skill, used only when the operator approves going wide.")
rep("Ten lanes on `<swarm workers model>` at the PR head, per the boot recipe.",
    "One lane per distinct check on `<swarm workers model>` at the PR head (<N> lanes), per the boot recipe.")
old_lanes = "".join(f"- [ ] Lane {i}. <Scenario.> Save `<slug>.png`. Pass when <predicate>.\n" for i in range(4, 11))
rep(old_lanes, "")
rep("- [ ] Lane 3. <Scenario.> Save `<slug>.png`. Pass when <predicate>.\n",
    "- [ ] Lane 3. <Scenario.> Save `<slug>.png`. Pass when <predicate>.\n\n"
    "Add Lane 4 and up only for scenarios no earlier lane covers, and set <N> to the lane count. Going wide restores ten lanes.\n")
p.write_text(s)
EOF
grep -c "Ten lanes" skills/poteto-mode/playbooks/multi-phase-plan.md
```
Expected: `1`. That one is the go-wide sentence.

- [ ] **Step 6: Append the ledger entry:**

```markdown

## C-004 — poteto-mode: one live lane per distinct check  [active]
Intent: multi-phase plans run one live-verification lane per distinct check (no repeats) and state "(N lanes)"; ten lanes only when going wide. check-plan.mjs accepts both phrasings and requires lanes numbered exactly 1..N.
Why: ten lanes repeat about five distinct checks; the repeats spend quota without adding coverage.
Spec: https://github.com/scotu/agent-plugin-factory/blob/main/docs/specs/2026-10-04-pstack-economy-design.md
Touches: skills/poteto-mode/scripts/check-plan.mjs, skills/poteto-mode/playbooks/multi-phase-plan.md
Check: python3 -m unittest tests.test_check_plan passes; grep -c "Ten lanes" skills/poteto-mode/playbooks/multi-phase-plan.md prints 1
```

- [ ] **Step 7: Commit**

```bash
git add skills/poteto-mode/scripts/check-plan.mjs skills/poteto-mode/playbooks/multi-phase-plan.md tests/test_check_plan.py CUSTOMIZATIONS.md
git commit -m "C-004: one live lane per distinct check; check-plan accepts (N lanes)"
```

---

### Task 5: C-005 watcher script and prompt

**Files:**
- Create: `skills/pstack-economy/audit-watch/pstack-audit-watch.py`, `skills/pstack-economy/audit-watch/watcher-prompt.md`, `tests/test_audit_watch.py`

**Interfaces:**
- Produces:
  - `pstack-audit-watch.py`, run with the program dir as cwd. It reads `owners.tsv` (columns `owner remote repo branch pr expected_minutes started_at`) and keeps `.pstack-audit-state.json`. The env var `PSTACK_AUDIT_NOW` (epoch seconds) overrides the clock, for tests.
  - It prints one line per owner: `<owner> branch=<branch> head=<sha7|missing|unknown> checks=<pass|pending|fail|none|unknown|nopr> bot_comments=<n|unknown|nopr>`, plus ` STUCK` when stuck. It always exits 0.
  - Error lines: `ERROR owners.tsv not found` and `ERROR owners.tsv line <n>: expected 7 columns`.

- [ ] **Step 1: Write the failing test** `tests/test_audit_watch.py`:

```python
"""pstack-audit-watch.py, the split audit tick's monitor script (C-005)."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "skills" / "pstack-economy" / "audit-watch" / "pstack-audit-watch.py"
HEADER = "owner\tremote\trepo\tbranch\tpr\texpected_minutes\tstarted_at\n"
GH_STUB = """#!/bin/sh
# Stub gh: `gh pr checks|view <n> ...` prints $GH_FIXTURES/<checks|view>-<n>.json and exits with the code in
# $GH_FIXTURES/<checks|view>-<n>.code (default 0); a missing fixture exits 1.
f="$GH_FIXTURES/$2-$3.json"
[ -f "$f" ] || exit 1
cat "$f"
c="$GH_FIXTURES/$2-$3.code"
[ -f "$c" ] && exit "$(cat "$c")"
exit 0
"""


def git(cwd, *args):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=cwd,
                          check=True, capture_output=True, text=True).stdout.strip()


class AuditWatchTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.remote = base / "remote.git"
        git(base, "init", "-q", "--bare", str(self.remote))
        self.work = base / "work"
        git(base, "clone", "-q", str(self.remote), str(self.work))
        self.push("1")
        self.bin = base / "bin"
        self.bin.mkdir()
        (self.bin / "gh").write_text(GH_STUB)
        (self.bin / "gh").chmod(0o755)
        self.fx = base / "fx"
        self.fx.mkdir()
        self.fixture("checks", [{"bucket": "pass"}, {"bucket": "pending"}])
        self.fixture("view", {"comments": [{"author": {"login": "cursor[bot]"}}, {"author": {"login": "matteo"}}]})
        self.program = base / "program"
        self.program.mkdir()
        self.owners(f"owner-a\t{self.remote}\tme/demo\tfeat-a\t7\t40\t1000\n")

    def tearDown(self):
        self._tmp.cleanup()

    def push(self, content):
        (self.work / "f").write_text(content)
        git(self.work, "add", "f")
        git(self.work, "commit", "-qm", content)
        git(self.work, "push", "-q", "origin", "HEAD:refs/heads/feat-a")
        return git(self.work, "rev-parse", "--short=7", "HEAD")

    def fixture(self, kind, data, code=0):
        (self.fx / f"{kind}-7.json").write_text(json.dumps(data))
        (self.fx / f"{kind}-7.code").write_text(str(code))

    def owners(self, rows):
        (self.program / "owners.tsv").write_text(HEADER + rows)

    def watch(self, now):
        env = {**os.environ, "PATH": f"{self.bin}{os.pathsep}{os.environ['PATH']}",
               "GH_FIXTURES": str(self.fx), "PSTACK_AUDIT_NOW": str(now)}
        r = subprocess.run([sys.executable, str(SCRIPT)], cwd=self.program, env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def test_line_format(self):
        head = git(self.work, "rev-parse", "--short=7", "HEAD")
        self.assertEqual(self.watch(1100),
                         f"owner-a branch=feat-a head={head} checks=pending bot_comments=1\n")

    def test_stable_output_without_changes(self):
        first, second = self.watch(1100), self.watch(1200)
        self.assertEqual(first, second)
        self.assertNotIn("1100", first)

    def test_new_push_changes_only_head(self):
        before = self.watch(1100)
        new = self.push("2")
        after = self.watch(1200)
        self.assertNotEqual(before, after)
        self.assertIn(f"head={new}", after)
        self.assertEqual(before.split("head=")[0], after.split("head=")[0])
        self.assertEqual(before.split(" checks=")[1], after.split(" checks=")[1])

    def test_stuck_after_expected_runtime(self):
        self.watch(1100)
        self.assertNotIn("STUCK", self.watch(1100 + 39 * 60))
        self.assertTrue(self.watch(1100 + 41 * 60).rstrip().endswith(" STUCK"))

    def test_stuck_clears_on_push(self):
        self.watch(1100)
        self.assertIn("STUCK", self.watch(1100 + 41 * 60))
        self.push("2")
        now = 1100 + 42 * 60
        self.assertNotIn("STUCK", self.watch(now))
        self.assertNotIn("STUCK", self.watch(now + 39 * 60))
        self.assertIn("STUCK", self.watch(now + 41 * 60))

    def test_checks_summary_reads_json_on_nonzero_exit(self):
        self.fixture("checks", [{"bucket": "pass"}, {"bucket": "fail"}], code=1)
        self.assertIn("checks=fail", self.watch(1100))
        self.fixture("checks", [{"bucket": "pending"}], code=8)
        self.assertIn("checks=pending", self.watch(1100))
        self.fixture("checks", [{"bucket": "pass"}, {"bucket": "skipping"}])
        self.assertIn("checks=pass", self.watch(1100))
        self.fixture("checks", [])
        self.assertIn("checks=none", self.watch(1100))

    def test_gh_failure_is_unknown(self):
        (self.fx / "checks-7.json").unlink()
        (self.fx / "view-7.json").unlink()
        self.assertIn("checks=unknown bot_comments=unknown", self.watch(1100))

    def test_no_pr_yet(self):
        self.owners(f"owner-a\t{self.remote}\tme/demo\tfeat-a\t-\t40\t1000\n")
        self.assertIn("checks=nopr bot_comments=nopr", self.watch(1100))

    def test_missing_branch(self):
        self.owners(f"owner-a\t{self.remote}\tme/demo\tnope\t7\t40\t1000\n")
        self.assertIn("head=missing", self.watch(1100))

    def test_missing_owners_file(self):
        (self.program / "owners.tsv").unlink()
        self.assertEqual(self.watch(1100), "ERROR owners.tsv not found\n")

    def test_malformed_row(self):
        self.owners("owner-a\tonly-two\n")
        self.assertEqual(self.watch(1100), "ERROR owners.tsv line 2: expected 7 columns\n")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests and confirm they fail.** Run `python3 -m unittest tests.test_audit_watch -v`. Expected: every test fails, because the script doesn't exist (`returncode` 2 with `can't open file`).

- [ ] **Step 3: Implement** `skills/pstack-economy/audit-watch/pstack-audit-watch.py`:

```python
#!/usr/bin/env python3
"""pstack split audit tick: monitor script for a Hermes cron job (pstack-economy, C-005).

Runs in the program dir. Reads owners.tsv (tab-separated, header row):
  owner  remote  repo  branch  pr  expected_minutes  started_at
and prints one stable line per owner, with no timestamps, so Hermes runs the watcher model only when
something changed:
  <owner> branch=<branch> head=<sha7|missing|unknown> checks=<pass|pending|fail|none|unknown|nopr>
  bot_comments=<n|unknown|nopr> [STUCK]
STUCK means both the owner and its current head have been idle longer than expected_minutes.
State (when each head was first seen) lives in .pstack-audit-state.json. PSTACK_AUDIT_NOW overrides the
clock for tests. Always exits 0: problems are reported as ERROR lines for the watcher to escalate.
"""
import csv
import json
import os
import subprocess
import time
from pathlib import Path

OWNERS = Path("owners.tsv")
STATE = Path(".pstack-audit-state.json")
COLUMNS = 7


def run(*cmd: str) -> tuple[int, str] | None:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.returncode, r.stdout


def head(remote: str, branch: str) -> str:
    result = run("git", "ls-remote", remote, f"refs/heads/{branch}")
    if result is None or result[0] != 0:
        return "unknown"
    return result[1].split()[0][:7] if result[1].strip() else "missing"


def gh_json(*args: str):
    """gh output as JSON. `gh pr checks` exits non-zero while checks pend or fail but still prints JSON."""
    result = run("gh", *args)
    if result is None:
        return None
    try:
        return json.loads(result[1])
    except ValueError:
        return None


def checks(repo: str, pr: str) -> str:
    data = gh_json("pr", "checks", pr, "-R", repo, "--json", "bucket")
    if not isinstance(data, list):
        return "unknown"
    buckets = {c.get("bucket") for c in data}
    if not buckets:
        return "none"
    if buckets & {"fail", "cancel"}:
        return "fail"
    if "pending" in buckets:
        return "pending"
    return "pass"


def bot_comments(repo: str, pr: str) -> str:
    data = gh_json("pr", "view", pr, "-R", repo, "--json", "comments")
    if not isinstance(data, dict):
        return "unknown"
    logins = [str((c.get("author") or {}).get("login", "")).lower() for c in data.get("comments", [])]
    return str(sum(1 for login in logins if login.endswith("[bot]") or login.endswith("bot")))


def main() -> None:
    if not OWNERS.exists():
        print("ERROR owners.tsv not found")
        return
    rows = list(csv.reader(OWNERS.read_text().splitlines(), delimiter="\t"))
    now = int(os.environ.get("PSTACK_AUDIT_NOW") or time.time())
    try:
        state = json.loads(STATE.read_text()) if STATE.exists() else {}
    except ValueError:
        state = {}
    lines = []
    for n, row in enumerate(rows[1:], start=2):
        if len(row) != COLUMNS:
            print(f"ERROR owners.tsv line {n}: expected {COLUMNS} columns")
            return
        owner, remote, repo, branch, pr, expected, started = row
        sha = head(remote, branch)
        seen = state.get(owner, {})
        if seen.get("sha") != sha:
            seen = {"sha": sha, "first_seen": now}
            state[owner] = seen
        limit = int(expected) * 60
        stuck = now - seen["first_seen"] > limit and now - int(started) > limit
        if pr == "-":
            status = "checks=nopr bot_comments=nopr"
        else:
            status = f"checks={checks(repo, pr)} bot_comments={bot_comments(repo, pr)}"
        lines.append(f"{owner} branch={branch} head={sha} {status}" + (" STUCK" if stuck else ""))
    STATE.write_text(json.dumps(state, indent=1, sort_keys=True))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the tests and confirm they pass.** Run `python3 -m unittest tests.test_audit_watch -v`. Expected: 11 tests OK.

- [ ] **Step 5: Write** `skills/pstack-economy/audit-watch/watcher-prompt.md`:

```markdown
You are the pstack audit watcher for one program. You are read-only. Never merge, dispatch, stand down, edit files, or contact anyone. Your reply is your only output, and it goes to the root session.

Each run you receive the monitor script's output and the diff since its last output. The script prints one line per owner, `<owner> branch=<branch> head=<sha> checks=<state> bot_comments=<n>`, ending in ` STUCK` when the owner has gone idle past its expected runtime. It may instead print one `ERROR ...` line.

Classify every changed line.

- Progress, stay silent: `head` changed to a new SHA, `checks` moved to `pending` or `pass`, a ` STUCK` flag cleared, or an owner line disappeared because the owner finished.
- Escalate: a ` STUCK` flag appeared, `checks` became `fail`, `bot_comments` went up, `head` became `missing`, `checks` or `head` became `unknown`, or any `ERROR` line.

On the first run there is no earlier output. Treat every line as new, and escalate only `STUCK`, `fail`, `missing`, `unknown`, and `ERROR`.

If nothing needs escalation, reply exactly `[SILENT]` and nothing else.

Otherwise reply with one line per escalation, `<owner>: <what changed> (<old> -> <new>)`, then this last line: `Root: run the judgment half of the audit tick for these owners (pstack-economy, Split audit tick step 5).`
```

- [ ] **Step 6: Commit** (the C-005 ledger entry comes with Task 6, which completes C-005):

```bash
git add skills/pstack-economy/audit-watch tests/test_audit_watch.py
git commit -m "C-005: split audit tick watcher script and prompt"
```

---

### Task 6: C-005 playbooks and the check-plan program marker

**Files:**
- Modify:
  - `skills/poteto-mode/scripts/check-plan.mjs` (`PROGRAM_MARKERS`)
  - `skills/poteto-mode/playbooks/multi-phase-plan.md` (the audit-tick box)
  - `skills/poteto-mode/playbooks/autopilot-full.md` (step 6)
  - `skills/poteto-mode/playbooks/autopilot-stack.md` (step 2)
  - `tests/test_check_plan.py`, `tests/test_skills.py`, `CUSTOMIZATIONS.md`

**Interfaces:**
- Consumes: `plan(live_line, n_lanes, marker)`, `check(text)`, `TEN`, `LOOP` and `SPLIT` from `tests/test_check_plan.py` (Task 4), and `skill()` from `tests/test_skills.py`.
- Produces: a program checklist passes with either `/loop 1h` or `pstack-audit-` as its audit marker.

- [ ] **Step 1: Write the failing tests.** Add to `tests/test_check_plan.py`, before `if __name__`:

```python
class ProgramMarkerTest(unittest.TestCase):
    def test_split_tick_marker_passes(self):
        code, out = check(plan(TEN, 10, marker=SPLIT))
        self.assertEqual(code, 0, out)

    def test_loop_marker_still_passes(self):
        code, out = check(plan(TEN, 10, marker=LOOP))
        self.assertEqual(code, 0, out)

    def test_no_tick_marker_fails(self):
        code, out = check(plan(TEN, 10, marker="- [ ] Audit when owners report back."))
        self.assertEqual(code, 1, out)
        self.assertIn("pstack-audit-", out)
```

Add to `tests/test_skills.py`, before `if __name__`:

```python
class SplitTickPlaybooksTest(unittest.TestCase):
    PLAYBOOKS = ROOT / "skills" / "poteto-mode" / "playbooks"

    def test_every_loop_1h_sentence_names_the_conditions(self):
        for name in ("multi-phase-plan.md", "autopilot-full.md", "autopilot-stack.md"):
            text = (self.PLAYBOOKS / name).read_text()
            for line in text.splitlines():
                if "`/loop 1h`" in line:
                    self.assertIn("going wide", line, f"{name}: {line[:80]}")
                    self.assertIn("pstack-audit-", line, f"{name}: {line[:80]}")
```

- [ ] **Step 2: Run the tests and confirm they fail.** Run `python3 -m unittest tests.test_check_plan.ProgramMarkerTest tests.test_skills.SplitTickPlaybooksTest -v`. Expected:
  - `test_split_tick_marker_passes` fails (it lacks `/loop 1h`).
  - `test_no_tick_marker_fails` fails on the `pstack-audit-` text check.
  - `test_every_loop_1h_sentence_names_the_conditions` fails on `multi-phase-plan.md`.
  - `test_loop_marker_still_passes` passes.

- [ ] **Step 3: Accept either marker in `check-plan.mjs`:**

```bash
python3 - <<'EOF'
from pathlib import Path
p = Path("skills/poteto-mode/scripts/check-plan.mjs"); s = p.read_text()
def rep(a, b):
    global s
    assert s.count(a) == 1, a
    s = s.replace(a, b)
rep('const PROGRAM_MARKERS = ["git show origin/main:", "/loop 1h", "status message"];',
    '// C-005 (pstack-economy): the audit tick is the split tick (cron job pstack-audit-<program>) or, going wide, /loop 1h.\n'
    'const PROGRAM_MARKERS = ["git show origin/main:", ["/loop 1h", "pstack-audit-"], "status message"];')
rep("""	for (const marker of PROGRAM_MARKERS) {
		if (!bodyText(program).includes(marker)) fail(program.n, `Program checklist lacks "${marker}"`);
	}""",
    """	for (const marker of PROGRAM_MARKERS) {
		const options = Array.isArray(marker) ? marker : [marker];
		if (!options.some((m) => bodyText(program).includes(m))) fail(program.n, `Program checklist lacks "${options.join('" or "')}"`);
	}""")
p.write_text(s)
EOF
```

- [ ] **Step 4: Rewrite the three tick sentences:**

```bash
python3 - <<'EOF'
from pathlib import Path
P = Path("skills/poteto-mode/playbooks")
def rep(name, a, b):
    p = P / name; s = p.read_text()
    assert s.count(a) == 1, (name, a[:60])
    p.write_text(s.replace(a, b))

rep("multi-phase-plan.md",
    "- [ ] On the operator's go, arm the audit tick as `/loop 1h` with the tick prompt below. Never leave the cadence to memory.",
    "- [ ] On the operator's go, arm the audit tick per the **pstack-economy** skill. With a `cron` model in `pstack-models.md`, arm the split tick as cron job `pstack-audit-<program>` and use the tick prompt below as the judgment half for its escalations. Without one, arm no tick and audit when owners report back. Only when the operator approves going wide, arm the full tick as `/loop 1h` with the tick prompt below. Never leave the cadence to memory.")

rep("autopilot-full.md",
    "Run an audit tick over all owners every hour. On the operator's go, arm `/loop 1h` with a prompt that runs this tick.",
    "Audit all owners per the **pstack-economy** skill. On the operator's go, arm the split tick when `pstack-models.md` has a `cron` model, which is a free watcher cron job named `pstack-audit-<program>` that escalates to you. Otherwise audit when owners report back. Arm the full hourly tick, `/loop 1h` with a prompt that runs this tick, only when the operator approves going wide (otherwise use the split tick `pstack-audit-<program>`).")

rep("autopilot-stack.md",
    "2. **Audit on a real loop.** The root runs an audit tick every hour. On the operator's go, the root arms `/loop 1h` with a prompt that runs this tick, per Autopilot-full step 6. Never leave the cadence to memory or lossy completion notifications.",
    "2. **Audit per the economy rules.** The root audits per Autopilot-full step 6 and the **pstack-economy** skill. With a `cron` model, the root arms the split tick (watcher cron job `pstack-audit-<program>`) on the operator's go and acts on its escalations. Without one, it audits when owners report back. Only when the operator approves going wide does the root arm `/loop 1h` with a prompt that runs this tick, in place of the split tick `pstack-audit-<program>`. Never leave the cadence to memory.")
EOF
```

- [ ] **Step 5: Run the whole suite and confirm it passes.** Run `python3 -m unittest discover -s tests -v`. Expected: all OK, which is 28 tests: 8 in `test_skills`, 9 in `test_check_plan`, 11 in `test_audit_watch`. Those counts include the 4 tests added in this task.

- [ ] **Step 6: Append the ledger entry:**

```markdown

## C-005 — poteto-mode: split audit tick instead of an hourly root loop  [active]
Intent: programs arm a split audit tick (free self-hosted cron watcher pstack-audit-<program> running pstack-audit-watch.py, escalating to the root, which does the judgment) when pstack-models.md has a cron model; otherwise no tick (audit on report-back); the hourly /loop 1h root tick only when going wide. check-plan.mjs accepts /loop 1h or pstack-audit- as the program marker.
Why: an hourly tick on a paid model re-audits unchanged state; mechanical liveness checks are free on a self-hosted model, and judgment is needed only when something changed.
Spec: https://github.com/scotu/agent-plugin-factory/blob/main/docs/specs/2026-10-04-pstack-economy-design.md
Touches: skills/poteto-mode/playbooks/multi-phase-plan.md, skills/poteto-mode/playbooks/autopilot-full.md, skills/poteto-mode/playbooks/autopilot-stack.md, skills/poteto-mode/scripts/check-plan.mjs, skills/pstack-economy/audit-watch/
Check: python3 -m unittest tests.test_check_plan tests.test_audit_watch tests.test_skills.SplitTickPlaybooksTest passes
```

- [ ] **Step 7: Commit**

```bash
git add skills/poteto-mode tests CUSTOMIZATIONS.md
git commit -m "C-005: playbooks arm the split audit tick; check-plan accepts pstack-audit- marker"
```

---

### Task 7: Validate, push, install

**Files:** none changed. This task releases and verifies.

- [ ] **Step 1: Run the whole suite and the ledger checks.** Run `python3 -m unittest discover -s tests -v`. Expected: 28 tests OK. Then run `grep -c "Ten lanes" skills/poteto-mode/playbooks/multi-phase-plan.md`. Expected: `1`.

- [ ] **Step 2: Validate the plugin.** Run `hermes plugins validate /Users/matteo/Development/agents/agent-plugin-factory/builds/hermes/pstack 2>&1 | tail -15`.
  - Expected: no manifest or skill-format errors.
  - Validation also runs the security scanner, so caution-level findings like those seen on 2026-10-03 may appear. Those are not failures here.
  - If `validate` refuses a path that isn't a catalog entry, use `hermes plugins doctor pstack` from a profile instead, and record which one ran.

- [ ] **Step 3: Push.** Run `git push -q origin main`, then `git status -sb | head -1`. Expected: `## main...origin/main` with no ahead or behind count.

- [ ] **Step 4: Update the profiles.** Run `hermes -p dr-eggbot plugins update pstack` and `hermes -p homelab-ops plugins update pstack`.
  - If either is blocked by the security scan (issue #9), stop. The user runs the reinstall themselves, after reviewing the findings:
    ```
    ! hermes -p <profile> plugins install file:///Users/matteo/Development/agents/agent-plugin-factory/builds/hermes/pstack --force --enable
    ```
  - Never pass `--force` yourself.

- [ ] **Step 5: Verify the installs.** From `/Users/matteo/Development/agents/agent-plugin-factory`, run `python3 -m factory status`. Expected: `0 active customizations` becomes `5 active customizations`, and both profiles show the new `main` SHA.

  Then, for each profile, run `diff -rq -x .git ~/.hermes/profiles/<p>/plugins/pstack builds/hermes/pstack`. Expected: no output.

  Check that pstack is still listed under `plugins.enabled` in each profile's `config.yaml`.

- [ ] **Step 6: Hand the manual checks to the user.** These are spec tests 3 and 7, and they spend tokens or need the self-hosted model:
  - **Run `/setup-pstack`** in one profile to build the inventory.
  - **Watcher wiring.** On a toy program dir with a fake `owners.tsv`, arm `pstack-audit-test` per `pstack-economy` step 4. Confirm that a progress change stays silent, and that an owner past its expected runtime produces a `STUCK` escalation in the bot chat. Then run `hermes -p <p> cron remove pstack-audit-test`.
  - **Live smoke test.** `interrogate` should spawn one reviewer. A request that would go wide should state its cost and wait for approval.
