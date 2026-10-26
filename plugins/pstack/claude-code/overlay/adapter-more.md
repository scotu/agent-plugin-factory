## More Cursor names

Upstream's tables above leave these out.

| Cursor | Claude Code |
| --- | --- |
| `cursor-team-kit` | Not available. Its skills map as follows. |
| `deslop` / `/deslop` (from `cursor-team-kit`) | pstack's `unslop` skill over the diff. |
| `control-ui` (from `cursor-team-kit`) | The session's browser tools: Claude in Chrome, the built-in browser, or a Chrome DevTools MCP, whichever the session has. For native apps, computer use. |
| `control-cli` (from `cursor-team-kit`) | `Bash`, driving the real binary. |
| A named driver the project already has (a `verify-*` skill) | Use it. It wins over the rows above. |
| `/create-skill` (Cursor built-in) | Write `SKILL.md` with `name` and `description` frontmatter in `.claude/skills/<name>/` or `~/.claude/skills/<name>/`. |
| `/loop` (Cursor built-in) | Claude Code's own `/loop`, which has the same idea. Give it a check that can pass or fail. |
| `/visualize` (Cursor's chart renderer) | Not available. Draw numbers as a Mermaid `xychart-beta` or `pie` block, or give them in one sentence. |
| `/orchestrate` | poteto-mode's Orchestrate playbook (`playbooks/orchestrate.md`). The separate `orchestrate` plugin is not installed. |
