---
name: pstack-codex
description: Run a Codex agent as pstack's second model family in Claude Code. Read when a pstack role, panel seat, or slug maps to Codex.
---

# pstack Codex executor

Codex is pstack's second model family in Claude Code. A role value `codex <model> <effort>` runs here, and so does a non-Claude slug (`grok-*`, `cursor-grok-*`, `composer-*`, `gpt-*`) when Codex is available. In the slug case, Codex uses its own configured default model and you pass no model. `pstack-economy` decides when a seat goes to Codex. This skill covers how to run it.

## Available

Codex is available when all three checks pass:
- `codex --version` succeeds;
- `codex login status` reports logged in;
- the work is in a git repository.

Check once per session and remember the result. There are two ways to run Codex:
- **The companion** (preferred). This is the `codex-companion.mjs` script from OpenAI's `codex` Claude Code plugin. Its path is the newest match of `~/.claude/plugins/cache/openai-codex/codex/*/scripts/codex-companion.mjs`. It provides `task [--background] [--write] [--model <m>] [--effort <e>] [--cwd <dir>]`, `status [job] --json`, `result [job] --json`, and `cancel [job]`. It keeps jobs per workspace, so pass the same `--cwd` to every call about one job.
- **`codex exec`** (fallback when the plugin isn't installed). Run `codex exec -C <dir> -s <sandbox> [-m <model>] [-c model_reasoning_effort=<effort>] --json -o <dir>/.codex-last.md "<brief>"`, in the background with Bash `run_in_background`.

When Codex is not available, run the seat on Claude as the adapter's Models table says, and say in one line that the step lost its second family.

A role value `codex <model> <effort>` names the model. `codex default <effort>` means Codex's own configured model: pass no `--model` or `-m`, only the effort.

The companion takes efforts up to `xhigh`. Run a `max` seat through `codex exec` with `-c model_reasoning_effort=max`, and only on a model whose `supported_reasoning_levels` in `~/.codex/models_cache.json` lists `max`. `ultra` adds Codex's own delegation, and a Codex seat is a leaf (see Limits), so pstack runs at most `max`.

Codex sees only the brief you give it. Put the whole task in it: the goal, the files and paths in scope, the checks to run, and the shape of the answer you expect.

## Advisory seat

Use this for a reviewer, judge, verifier, explorer, or any seat that only reads. Run Codex without `--write`, through the companion's `task` or `codex exec -s read-only`, from the repository or worktree being judged. Read its result directly. An advisory seat never edits files, and nobody commits on its behalf.

## Code-writing owner

Use this when Codex writes the code for a unit of work: a feature, a fix, or a candidate in a race. A Codex job is paired with a **wrapper**, which is an `Agent` subagent on a light Claude model. The pair is the branch's one writer.

1. The wrapper creates the worktree and branch with `git worktree add <path> -b <branch> <base>`, or takes the ones the playbook names.
2. It starts Codex in that worktree, in the background and able to write: companion `task --background --write --cwd <worktree>`, or `codex exec -C <worktree> -s workspace-write`. Codex edits files only. Under `workspace-write`, the network is off and git metadata is out of reach, and that is intended.
3. It records the pair in the program dir's `owners.tsv` (see `pstack-economy`, Audit tick):
   - `executor` is `codex`;
   - `job` is the Codex job id and the wrapper's agent id, separated by `+`. Under the `codex exec` fallback there is no job id: record the session id from `exec`'s `--json` output in its place. The watcher can't query it and shows `codex=-`, so a fallback pair is surfaced only when it goes STUCK;
   - plus the worktree branch and expected minutes.

   The wrapper commits, pushes and opens the PR (`gh pr create`). Codex never does.

## Wrapper loop

1. **Wait.** Wait for the Codex job to end with one blocking call at a time, which costs no model turns while Codex works.
   - **With the companion,** run `status <job> --wait --timeout-ms 540000 --cwd <worktree> --json` as a single Bash call with a 600000 ms timeout. When its JSON has `waitTimedOut: true`, run the same call again.
   - **With the fallback,** the background `codex exec` call notifies you when it exits. Act on that notification.
2. **Check scope.** Read the worktree's diff for scope only: files outside the brief, deleted tests, or debris. The wrapper doesn't rewrite code. It sends anything out of scope back to Codex.
3. **Check and commit.** Run the repo's checks for the touched paths. Then commit what Codex wrote, with a message that names the Codex job, push, and open or update the PR with `gh pr create` or `gh pr edit`.
4. **Fix rounds.** For each round (failed checks, review findings, bot comments), resume the same Codex session on the same worktree with the finding, and a red test where the playbook asks for one.
   - **With the companion,** run `task --resume-last --background --write --cwd <worktree> "<finding>"`.
   - **With the fallback,** run, from inside the worktree, `codex exec resume <session id> -c sandbox_mode="workspace-write" --json "<finding>"`. `resume` accepts neither `-C` nor `-s`. Name the session id rather than `--last`, because other pairs run sessions in parallel.

   Each round is a new Codex job, so update the `job` column in `owners.tsv` with its id. Then go back to step 2.
5. **Report.** Report the head SHA at each push, as the playbook asks of any owner.

Judge progress by side effects, never by summaries: Codex's file changes, then the wrapper's commits and pushes.

## Standing down

Cancel the Codex job (companion `cancel <job> --cwd <worktree>`, or stop the background `codex exec`), then stop the wrapper. Leave the worktree in place for inspection. Mark the pair stood down in `owners.tsv`.

## Limits

- Codex does not commit, push, or reach the network. Only its wrapper touches git and the forge.
- Codex is a leaf. It does not spawn pstack subagents or run pstack skills of its own.
- The pair writes only its own branch. Merge authority follows the playbook, as for any owner.
- Model names are whatever this user's Codex accepts, as `setup-pstack` records them in `~/.claude/rules/pstack-models.md`. Never assume a catalog.
