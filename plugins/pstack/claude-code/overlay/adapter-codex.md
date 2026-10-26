## Codex

When Codex is available, it is pstack's second model family in Claude Code. Read `<pstack>/skills/pstack-codex/SKILL.md` for how to run a Codex agent. When Codex is available, this table overrides the Models row for non-Claude slugs. It also overrides the setup-pstack Defaults bullet that writes `grok-4.7-xhigh-fast` as `inherit-parent`: with Codex available, write `codex <model> <effort>` with a Codex model the user confirmed. `inherit-parent` stays the mapping only without Codex.

| Cursor | Claude Code |
| --- | --- |
| A role value `codex <model> <effort>` | A Codex agent per `pstack-codex`, with that model and effort. |
| A `grok-*`, `cursor-grok-*`, `composer-*`, or `gpt-*` slug | When Codex is available: a Codex agent on Codex's configured default model (no `-m`). When it is not: omit `model` as in the Models table, and say in one line that the panel lost its second family. |
