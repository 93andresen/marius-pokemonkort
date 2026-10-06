# WORKFLOW.md — how work is done in this repo

> Read this **once at the start of a task**. It is deliberately *not* auto-loaded (keeping the always-on
> [`AGENTS.md`](AGENTS.md) small). The whole point: every task is **small, self-contained and verified
> end-to-end**, so we never end up with half-wired code, tests that pass by lying, or a context window
> that is full before work even starts.

---

## 1. The unit of work

A **work item** is one folder under `work/`, named `NNNN-short-slug` (zero-padded, lexically sortable —
e.g. `0001-finn-ad-structured-fields`). It holds:

| File | Written | Contains |
|---|---|---|
| `TASK.md` | by the agent, **before** coding | goal, scope, out-of-scope, **success criteria**, **test plan** |
| `RESULT.md` | by the agent, when done | what ran, real evidence, status, what is left |

Scaffold and templates: [`work/README.md`](work/README.md) and [`work/TEMPLATE.md`](work/TEMPLATE.md).
A single work item must be:

- **Self-contained** — verifiable on its own, without having finished another item.
- **Finishable in one context window** — target well under ~60k tokens of actual work.
- **One thing** — if the goal needs the word "and", split it.
- **Independently valuable** — it moves the pipeline forward without a companion task.

If an area is too big, split it along **verification boundaries**: each item should produce one runnable,
testable result. When in doubt, split smaller.

## 2. Lifecycle (follow in order, every time)

1. **Pick** the smallest next item from [`work/_index.md`](work/_index.md).
2. **Scope it — define success yourself.** Copy `work/TEMPLATE.md` to `work/<id>/TASK.md`. *You* decide
   what "done" means and what the output shape is; nobody pre-decides it for you. Write the success
   criteria as things **a test can check**, not vibes.
3. **Write the tests first.** Add real tests under `tests/` (see [`tests/README.md`](tests/README.md)).
   They must **fail before** you implement and **pass after**. Prefer testing real input over testing a
   mock of your own code.
4. **Implement end-to-end.** Not a stub. The code must actually run on representative data — a real saved
   raw capture, a committed fixture, or (within budget) a live call — and produce output.
5. **Verify.** Run the tests **and** run the thing for real. Capture the actual output (counts, sample
   rows, error lines) and compare it against the success criteria you wrote. A mismatch means **not done**.
6. **Record `RESULT.md`**: exact commands run, observed output, status, and any follow-ups.
7. **Stop and hand back.** Report status. Do not silently expand scope or chain into the next item.

## 3. Definition of Done

An item is done only when **all** of these are true:

- [ ] Every `TASK.md` success criterion is backed by a passing test and/or shown real output.
- [ ] The **end-to-end** path runs on real-ish input — not only unit mocks.
- [ ] Evidence (commands + observed results) is written in `RESULT.md`.
- [ ] New behaviour that writes data is idempotent/resumable (per [`AGENTS.md`](AGENTS.md) §4).
- [ ] Nothing was deleted; failures are visible; no "success" is printed without a check behind it.
- [ ] Anything that could **not** be done is written down as a blocker — never hidden.

## 4. The test rules (never break these)

- **Never edit, weaken, skip or delete a test to make it pass.** A red test is a *finding*.
- If you believe a test is genuinely wrong: **stop and say so explicitly**, explain why, and leave it red
  (or marked `xfail` with the reason) until the user confirms. Do **not** "fix" it by matching the bug.
- Tests assert the **observable behaviour of the real code** — not that a mock echoed your input back.
- Fixtures are small, committed and real (e.g. a couple of saved captures); never bulk data.
- A test that can never fail is theatre, not evidence. Make it able to fail.

## 5. Context discipline while working

- Start with only `AGENTS.md` + your `TASK.md`; open more files **one at a time**, smallest slice first.
- Prefer `search_files` (grep) over reading whole large files.
- Keep a short running "what I've learned / where I am" note inside `TASK.md` so a compaction is recoverable.
- When the item is done, the knowledge lives in `RESULT.md` + the tests — not in your head.
