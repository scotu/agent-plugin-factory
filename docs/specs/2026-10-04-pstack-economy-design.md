# pstack economy: design

## Goal

Upstream pstack assumes LLM calls are cheap. It races several agents on the same task, gathers panels of reviewers with the same prompt, runs ten verification lanes, and arms hourly audit loops. For a solo developer who pays mostly through subscription quotas, plus some self-hosted and pay-per-token models, that spending is wasted.

This customization makes pstack economical by default without weakening its rigor. It is a set of personal customizations, C-001 to C-005, on `main` of the build repo `scotu/pstack-hermes`, tracked in its `CUSTOMIZATIONS.md`. It is not part of the factory's Hermes port: the overlay in `plugins/pstack/hermes/overlay/` stays a faithful port.

Decisions:
- **Posture: lean by default, escalate on approval.** Going wider is approved per task, never permanently.
- **Lean removes duplicated work, not divided work.** When several agents do different pieces of work, they keep upstream's subagents, used as needed. Lean only cuts copies of the same work: several attempts at one task, several reviewers given the same prompt, repeated verification lanes, and polling loops. Collapsing divided work onto fewer agents saves almost nothing.
- **Model knowledge comes from a per-profile inventory** built by `setup-pstack` and confirmed by the user. It is not a catalog shipped with the plugin.
- **Approach C:** a new `pstack-economy` skill, which as a new file never conflicts with upstream; a one-line hook in `pstack-on-hermes`; the inventory in `setup-pstack`; and targeted edits only where upstream text or tooling enforces width.

Success means:
- With no "go wide", no pstack skill runs duplicated work beyond the lean widths below.
- Every going-wide step states its cost and waits for approval, unless the user asked to go wide for that task.
- Divided work behaves exactly as upstream.
- `setup-pstack` produces an inventory with cost class and tier for every model it can reach.
- The five ledger entries survive upstream merges. Each has a Check that shows it still holds.

## Hermes constraint

`delegate_task` has no per-task model (`~/.hermes/hermes-agent/tools/delegate_tool.py`). Every child uses the profile's single `delegation.model`. Inside one profile pstack therefore has three executors:
- **`parent`:** the chat model.
- **`delegate`:** `delegation.model`, used by every subagent.
- **`profile:<name>`:** a teammate bot with its own model, reached through `message_agent`. It is asynchronous and costs that bot a turn.

Routing by tier therefore means choosing which executor runs a role, and choosing well which models fill the parent and delegate slots.

## Lean widths

| Pattern | Kind of work | Lean default | Go wide (upstream) |
|---|---|---|---|
| swarm, coverage slices | divided | as upstream: one worker per slice, no cap | — |
| swarm, races and best-of | duplicated | no races: one worker per arm | upstream races |
| architect | duplicated | one design by the parent that names the alternatives it rejected and why | 2–3 runners |
| arena | duplicated | 2 candidates on different model families or executors, judged by the parent against the rubric, with no separate cross-judge | 3 candidates plus a cross-judge |
| interrogate | duplicated | 1 reviewer, on an executor whose model differs from the code's author | one per configured model |
| reflect | divided (3 lenses) | as upstream | — |
| why | divided (evidence categories) | as upstream | — |
| how | divided (exploration angles) | as upstream | — |
| poteto-mode subagents | divided | as upstream | — |
| Live verification ("Ten lanes") | partly duplicated | one lane for each distinct check, with no repeats: re-run the gates, live proof on the real surface, diff audits (one per declared focus), and regression against trunk | 10 lanes |
| Autopilot audit tick (`/loop 1h`) | duplicated over time | not armed. The root checks owners when they report back and when the user asks. | armed hourly |
| Second-opinion profiles (`message_agent`) | duplicated | only when the user asks | as configured |

Event-driven waits stay as upstream, for example `/loop` in `autonomous-run.md` watching CI or a merge. They wait for something to happen; they don't repeat work.

## Go-wide protocol

Before any step wider than lean, the agent posts one message that names:
- the pattern, for example "arena";
- the width it wants and the lean width it would replace;
- the executors involved, with their models and cost classes from the inventory;
- a rough relative cost, for example "about 3× one pass; 2 of the 3 runs are subscription, 1 is per-token".

Then it waits for an explicit yes. "Go wide", "spare no expense", or naming a width for the current task ("arena with 3") counts as approval for that task only. Approval never carries over to later tasks or sessions. When unattended (autopilot, figure-it-out, a user who stepped away), the agent stays lean and records in its report the steps it would have widened.

## Tier routing

The inventory gives each model a **cost class** and a **capability tier**:
- **Cost classes:** `self-hosted` (no cost per call), `subscription` (quota), `per-token` (money per call).
- **Tiers:** `frontier` (best reasoning and judgment), `strong` (solid coding and review), `light` (mechanical reading, searching, summarizing).

Which work goes to which tier:
- **light:** exploration and grep sweeps, running tests and reporting results, reading transcripts or logs.
- **strong:** code-writing delegates, reviewers, investigators.
- **frontier:** judgment, synthesis, the hardest tasks, and final picks (arena base, verdicts).

Rules:
- Route each role to the cheapest executor whose model meets the role's tier.
- At equal tier, prefer `self-hosted`, then `subscription`, then `per-token`.
- **Per-token rule:** never pick a per-token executor unless it is the only executor at the tier the role needs. When a role would land on one, say so before spending.
- A light model reachable only as `profile:<name>` is used for light work only when that role is already a `profile:` entry in the role table. pstack never routes there implicitly, because it is asynchronous and costs that bot a turn.

## Model inventory (`setup-pstack`)

`pstack-models.md` gains a section at the top:

```
# Models this profile can reach (re-run setup-pstack when they change)
# model | provider | cost class | tier | executor
<model> | <provider> | self-hosted|subscription|per-token | frontier|strong|light | parent|delegate|profile:<name>|(not assigned)
```

`setup-pstack` changes:
1. **Detect** models from the providers' cached model lists. This step already exists, and only confirmed models are written. It also lists the teammate profiles and their models.
2. **Propose the cost class from the provider type:**
   - a local or self-hosted base URL (Ollama, LM Studio, vLLM, llama.cpp) means `self-hosted`;
   - a plan login through OAuth (for example the Codex/ChatGPT plan or a Claude subscription) means `subscription`;
   - an API key means `per-token`.

   When unsure, ask.
3. **Propose the tier** from the agent's own knowledge of the model, marked as a proposal.
4. **Recommend the slots:**
   - parent: the best `subscription` model;
   - delegate: the cheapest model rated `strong` or better, preferring `self-hosted`, then `subscription`.

   Explain that the delegate slot decides most of the spend. Say plainly that self-hosted light models help only through a teammate profile.
5. **Confirm everything in one `clarify` step**, then write `delegation.model`/`provider` (announced as a config write, as now) and overwrite `pstack-models.md` completely. Re-runs stay idempotent.
6. **Lean role defaults** for duplicated-work roles:
   - `architect runners: parent`
   - `arena runners: parent, delegate`
   - `arena cross-judge pool: parent`
   - `interrogate reviewers: delegate`

   Divided-work roles keep their current defaults. The go-wide widths are the upstream defaults, listed in `pstack-economy` so the agent knows what to propose.

## Ledger entries

Each entry is one commit on `scotu/pstack-hermes` `main`, with an entry in `CUSTOMIZATIONS.md` linking to this spec.

| ID | Change | Touches | Check |
|---|---|---|---|
| C-001 | New skill `pstack-economy`: posture, duplicated-versus-divided rule, lean widths table, go-wide protocol, tier routing, per-token rule, upstream go-wide widths | `skills/pstack-economy/` | the folder exists, and its frontmatter `name: pstack-economy` matches the folder |
| C-002 | `pstack-on-hermes`: one line, "before any fan-out, load and apply `<NS>:pstack-economy`" | `skills/pstack-on-hermes/SKILL.md` | `grep -c pstack-economy` gives 1 or more |
| C-003 | `setup-pstack`: model inventory, cost-class and tier proposals, slot recommendations, lean defaults for duplicated-work roles | `skills/setup-pstack/SKILL.md` | `grep "cost class"` matches, and the defaults block has `architect runners: parent` |
| C-004 | Live verification counts each distinct check once. The plan template says "One lane per distinct check on `<swarm workers model>` at the PR head (N lanes)". `check-plan.mjs` accepts "Ten lanes" or "One lane per distinct check … (N lanes)". | `skills/poteto-mode/playbooks/multi-phase-plan.md`, `skills/poteto-mode/scripts/check-plan.mjs` | no "Ten lanes" left in `multi-phase-plan.md`, and both phrasings pass `check-plan.mjs` |
| C-005 | The audit tick is not armed by default. The `/loop 1h` instructions say to arm it only when going wide or when the user asks. `check-plan.mjs` no longer requires the `/loop 1h` program marker. | `skills/poteto-mode/playbooks/multi-phase-plan.md`, `skills/poteto-mode/playbooks/autopilot-full.md`, `skills/poteto-mode/playbooks/autopilot-stack.md`, `skills/poteto-mode/scripts/check-plan.mjs` | each `/loop 1h` sentence includes the go-wide condition, and a program plan without `/loop 1h` passes `check-plan.mjs` |

C-004 and C-005 change the wording in place, rather than adding override notes beside the old text. Readers then never see two contradicting rules, and a merge conflict shows exactly which sentence upstream changed.

## Testing

1. **`check-plan.mjs`:** sample plans in a temp dir. A plan with "Ten lanes" passes. A plan with "One lane per distinct check … (5 lanes)" passes. A plan with neither fails. A program plan without `/loop 1h` passes. The script's existing behavior otherwise stays unchanged. If the script has its own tests, run them.
2. **Plugin validity:** run `hermes plugins validate` (or `doctor`) on `builds/hermes/pstack`, and check that every `SKILL.md` `name:` matches its folder.
3. **Ledger checks:** run every entry's Check command.
4. **Install:** run `python3 -m factory sync pstack --install`, or, if the scan blocks per issue #9, the user runs the `--force` reinstall. Then check that both profiles match the build clone and still have pstack enabled.
5. **Optional live smoke test (user-run, since it spends tokens):** in one profile, `interrogate` should spawn one reviewer. A request that would go wide should show the cost statement and wait for approval.

## Out of scope

- Per-subagent model selection inside Hermes, which Hermes doesn't support.
- Token counting or measuring spend.
- Changing divided-work skills (`reflect`, `why`, `how`, swarm coverage, poteto-mode subagents).
- Factory changes. This is entirely build-repo customization.
