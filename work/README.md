# work/ — the task backlog

Every unit of work lives in its own folder here. **One folder = one small, self-contained, independently
verifiable task.** The method (and the Definition of Done) is in [`../WORKFLOW.md`](../WORKFLOW.md).

## Layout

```
work/
  README.md        ← this file
  TEMPLATE.md      ← copy to <NNNN-slug>/TASK.md and fill in
  _index.md        ← registry of all items + status
  HANDOFF.md       ← the current program brief handed to the next agent
  NNNN-slug/
    TASK.md        ← goal + success criteria + test plan (written BEFORE coding)
    RESULT.md      ← evidence + status (written AFTER)
```

## Naming

- `NNNN` — zero-padded sequence (`0001`, `0002`, …) so folders sort chronologically.
- `slug` — short kebab-case, e.g. `0003-finn-ad-structured-fields`.

## Starting an item

1. Claim the next `NNNN` by appending a row to [`_index.md`](_index.md) — **never renumber existing items**.
2. Copy `work/TEMPLATE.md` to `work/NNNN-slug/TASK.md` and fill it in **before writing code**.
3. Follow the lifecycle in [`../WORKFLOW.md`](../WORKFLOW.md) §2.

## Decomposing an area into items

An area (e.g. "parse FINN ad pages into structured fields") becomes several items when a single item can
**not** be verified on its own, or can **not** finish in one context window. Split along **verification
boundaries** — each item should produce one runnable, testable result. When in doubt, split smaller.

> **Do not pre-decide the output schema for the agent doing an item.** Defining the success criteria and
> writing the tests is the item owner's job (see [`../WORKFLOW.md`](../WORKFLOW.md) §2–§4).
