# work index

One row per work item. Append only; **never renumber**. Status: `todo` / `in-progress` / `done` / `blocked`.

| ID | Title | Status | Notes |
|---|---|---|---|
| — | *(no items yet — create the first by copying `TEMPLATE.md`)* | — | — |

---

## Candidate areas (NOT yet scoped — an agent must decompose each and define success)

These come from the roadmap and the pipeline spec. They are **areas, not tasks**: split each into small,
independently verifiable items, then let the item owner define the output shape + tests
(see [`../WORKFLOW.md`](../WORKFLOW.md) §1–§4).

- FINN **ad page → structured machine-read fields** (title, price, status, location, gallery UUIDs, …).
- FINN **search pages → discovery + delta detection** (new / still-active / gone), with pagination verified.
- **Card-list structuring** (LLM-derived) with provenance, plus count reconciliation (title vs description).
- **Matcher quality** on real ads: FINN-kode → ranked PokeWallet candidates → NOK estimate.
- End-to-end **golden path** on one saved ad: raw capture → parsed JSON → matched price → Sheet row.
- **Sheet ingestion** of parsed ads (two-layer, append-only: raw + current).
- **Test fixtures**: collect a few real captures (active / sold / weird-format) as fixed parser inputs.

> Keep each item small. If it can't be verified alone, or can't fit in one context window, split it.
