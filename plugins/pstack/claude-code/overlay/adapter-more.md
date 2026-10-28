## More Cursor names

Upstream's tables above leave these out.

| Cursor | Claude Code |
| --- | --- |
| `cursor-team-kit` | Not available. Its skills map as follows. |
| `deslop` / `/deslop` (from `cursor-team-kit`) | pstack's `unslop` skill over the diff. |
| `control-ui` (from `cursor-team-kit`) | The session's browser tools: Claude in Chrome, the built-in browser, or a Chrome DevTools MCP, whichever the session has. For native apps, computer use. |
| `control-cli` (from `cursor-team-kit`) | `Bash`, driving the real binary. |
| A named driver the project already has (a `verify-*` skill) | Use it. It wins over the rows above. |
| `/create-skill` (Cursor built-in) | Write `SKILL.md` with `name` and `description` frontmatter in `.claude/skills/<name>/` or `~/.claude/skills/<name>/`. Its YAML and writing rules: kebab-case `name` matching the folder, and a `description` that says what the skill does and when to use it. Its draft, test and iterate loop and its description-optimization loop: use a skill-creator skill if the session has one, otherwise read the draft through once yourself. |
| `/loop` (Cursor built-in) | Claude Code's own `/loop`, which has the same idea. Give it a check that can pass or fail. |
| `/visualize` (Cursor's chart renderer) | Not available. Draw numbers as a Mermaid `xychart-beta` or `pie` block, or give them in one sentence. |
| `/orchestrate` | poteto-mode's Orchestrate playbook (`playbooks/orchestrate.md`). The separate `orchestrate` plugin is not installed. |
| `allow_multiple: true` on `AskQuestion` | `multiSelect: true` on `AskUserQuestion`. |
| Matching a transcript by its first JSONL line | Match the first `type: user` record. In Claude Code the first lines are metadata. |
| The agent's store ("path in the system prompt") | `~/.claude/pstack-programs/<program>/`, the program dir that `pstack-economy`'s Audit tick uses. Decision trails, subagent records, orchestrate's project folder, and the store's `docs/` live there. Create it if it is missing. |
| `pstack/<path>`, `git show origin/main:pstack/<path>` | `<pstack>/<path>`, read locally. "Re-read the playbook from trunk" means re-read the installed copy. |
| A Cursor restart | A Claude Code session that ends or restarts. Its subagents and background tasks are gone; worktrees and pushed branches remain. |
| Nested subagents (a sub-coordinator spawning workers) | If a subagent cannot spawn subagents of its own, the coordinator spawns every worker, and sub-coordinators become tracks it keeps in its records. |
| A live lane's own cloud VM, or a video on a lane VM | A worktree on this machine. Give each lane distinct ports, or run live lanes one at a time. Record video with the session's browser or computer-use tools, otherwise skip it with the line. |
| Pinned or active chats, the sidebar | Ask the user which sessions are live, and check for running `claude` processes. |
| `.cursor/worktrees/`, `~/Library/Application Support/Cursor` caches | `.claude/worktrees/`; skip the Cursor caches. |
| Cursor's `mcps/` directory, the enabled MCP servers | The session's MCP tools (`mcp__<server>__*`) and their server instructions. |
| The image-generation tool, a generated image | Not available. Draw a Mermaid or ASCII diagram, and say the picture was skipped. |
| Embedding a screenshot or video inline in the reply | Give its absolute path, or an Artifact link when the session offers one. |
| A Custom Mode, "Use as Mode", Option+Enter, the Agents Window, Plan Mode | Not available. Start each task with `/pstack:poteto-mode`. For planning, use the Multi-phase plan playbook. |
| The Project tracker (`notes.md`) and the Project store | `notes.md` and the files beside it in the program dir, `~/.claude/pstack-programs/<program>/`. |
| PR and CI event subscriptions | The background watcher from `pstack-economy`'s Audit tick. It exits when a head moves, checks change, or a bot comments, and costs nothing while nothing changes. List each PR in `owners.tsv`. |
| A Cursor Project (one persistent coordinator thread) | One long-lived Claude Code session per program, with worktree subagents. |
| `/in-cloud` | `isolation: "worktree"` on the `Agent` call. |
| `/add-plugin pstack`, Customize in the sidebar, `/plugin marketplace add cursor/plugins` | `claude plugin marketplace add scotu/pstack-claude-code`, then `claude plugin install pstack@scotu-pstack`. This fork, not upstream's marketplace. |
| `/make-bot-ui` | Not in this build. It drives Cursor Automations (routines and webhooks), which Claude Code does not have. |
