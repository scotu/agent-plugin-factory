## Codex

When Codex is available, it is pstack's second model family in Claude Code. Load the `pstack-codex` skill (`/pstack:pstack-codex`) for how to run a Codex agent.

| Cursor | Claude Code |
| --- | --- |
| A role value `codex <model> <effort>` | A Codex agent per `pstack-codex`, with that model and effort. |
| A `grok-*`, `cursor-grok-*`, `composer-*`, or `gpt-*` slug | When Codex is available: a Codex agent on Codex's configured default model (no `-m`). When it is not: omit `model` as in the Models table, and say in one line that the panel lost its second family. |
