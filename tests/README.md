# tests/

Home for the repo's tests. The non-negotiable rules live in [`../WORKFLOW.md`](../WORKFLOW.md) §4 —
above all: **never edit, weaken or delete a test to make it pass.** A red test is a finding to report.

## Running (uv only — never bare `python`)

Tests are self-contained runnable scripts with their own PEP 723 `# /// script` metadata, so a single
command works with no prior environment setup:

```bash
uv run tests/test_<slug>.py
```

- **Default to the standard library `unittest`** — it needs no third-party dependency at all, which keeps
  the "run with `uv run <script>.py`" rule trivially satisfied.
- If a test genuinely needs `pytest` (or another package), add it to that script's PEP 723 block via the
  **`uv-dependency-injector` skill** (`uv add --script`). **Never hand-edit the `# /// script` block** and
  never reach for `uv run --with` / `uv pip install`.

## Conventions

- One test module per work item where practical: `tests/test_<slug>.py`.
- Test the **real behaviour** of `finn/`, `pokewallet/`, `sheet/` and `tools/` code — not mocks echoing input.
- Fixtures are small, committed, **real** captures under `tests/fixtures/` (never bulk/raw data).
- Tests must be able to **fail**: assert on observable output and error loudly on mismatch.
- Print counts and the actual values compared, so a run is self-evidencing (per `AGENTS.md` §4).
