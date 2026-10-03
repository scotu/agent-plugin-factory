# {{NAME}} customizations

This file lists the personal changes made on top of the {{TARGET}} build of {{NAME}}. It exists only on the `main` branch.

- `upstream` holds the exact build output from agent-plugin-factory. Never edit it by hand.
- `main` is `upstream` plus the changes listed here. Install this branch.
- `git diff refs/heads/upstream main --` shows the full set of changes.
- Upstream comes in by merge (`python3 -m factory sync {{NAME}}`). Never rebase or rewrite `main`: `hermes plugins update` only fast-forwards.

Each change has one entry. Its commits start with its ID, for example `C-001: …`. When resolving a merge conflict, re-apply the **Intent** instead of keeping the old wording. Status is `active` or `retired`. Retire an entry when upstream covers it or you no longer want it, and keep it as history.

Entry format:

```
## C-NNN — <area>: <short title>  [active]
Intent: what must be true afterwards, written so it survives upstream rewording.
Why: the reason for the change.
Touches: path/to/file, path/to/folder/
Check: how to confirm it still holds.
```

<!-- entries below, newest last -->
