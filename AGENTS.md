# AGENTS.md — Inocras Initial Data Layer

Operating context for any AI agent (Claude Code, Copilot, Cursor, etc.) working in
this repository. Read this file end to end before taking any action.

---

## 0. Context loading protocol — do this first, every session

The authoritative, evolving project context lives in [`working_contexts/`](working_contexts/).
This file (`AGENTS.md`) holds only the **stable** operating rules. Anything about the
current problem statement, chosen architecture, or open decisions lives in the context
directory and **changes frequently**.

Before proposing an approach, answering a design question, or writing a line of code:

1. List `working_contexts/`.
2. Select the file with the **highest version number** `v<N>`. If two share a version,
   take the **latest timestamp**.
3. Read it in full.
4. Where it conflicts with this file, **the context file wins**.

**Naming convention** (do not deviate):

```
working_contexts/initial_data_layer_context_v<N>_<UTC-timestamp>.md
                                              │     └── YYYYMMDDTHHMMSSZ
                                              └── integer, monotonically increasing
```

Example: `initial_data_layer_context_v1_20260822T232329Z.md`

**Context files are append-only.** Never edit a published context file in place — that
would destroy the record of how a decision was reached, which is the whole point of
version-controlling the context. To revise the context, write a **new** file at `v<N+1>`
carrying forward what is still true, and record what changed in its Changelog section.

This mirrors the same immutability principle the pipeline itself applies to the landing
zone: raw history is never rewritten, only superseded.

---

## 1. What this project is

A take-home exercise for Inocras: build the **first slice of a genomic data foundation**.

Somatic variant call files (VCF) plus per-batch sample manifests arrive in a landing
zone (here, a local folder; in production, an S3 prefix). The task is to ingest,
validate and clean them into a **governed curated zone** that is:

- reliably queryable by researchers writing SQL today, and
- reliably queryable by a **natural-language assistant** later.

That second consumer is the real thesis of the exercise. The assignment states it
plainly: *"that assistant is only as reliable as the foundation underneath it."*
Every schema and naming decision should be defensible as **"an LLM writing SQL against
this cannot get it wrong."**

### Current status

> **PROBLEM FRAMING — architecture is NOT settled.**
>
> Do **not** scaffold a pipeline, pick a storage engine, or write ingestion code until
> the active context document marks the relevant decision `RESOLVED`. Open decisions are
> tracked in the context file's *Open Decisions* register. Proposing options with
> tradeoffs is welcome; committing to one unilaterally is not.

---

## 2. Repository layout

```
inocras_initial_data_layer/
├── AGENTS.md                  ← you are here (stable operating rules)
├── CLAUDE.md                  ← Claude-specific environment + conventions
├── working_contexts/          ← versioned, append-only project context
│   └── initial_data_layer_context_v<N>_<ts>.md
└── candidate_bundle/          ← AS PROVIDED BY INOCRAS — do not modify
    ├── README.md              ← the assignment brief
    └── data/                  ← THE IMMUTABLE LANDING ZONE
        ├── batch_2026_01/     ← 14 VCFs + sample_manifest.csv
        └── batch_2026_02/     ← 5 VCFs + sample_manifest.csv (drifted schema)
```

Anything the pipeline produces (curated tables, Parquet, a DuckDB file, quarantine
output, logs) is **generated** and belongs in a gitignored output directory — never
committed, never written inside `candidate_bundle/`.

---

## 3. Hard rules

These are non-negotiable and hold regardless of what the context file says.

1. **`candidate_bundle/data/` is immutable.** Never write to it, never hand-edit a CSV
   or VCF, never "fix" a malformed file at rest. Treat it as a read-only S3 raw zone.
   Every defect must be handled in code, at read time.

2. **No paid infrastructure.** Local, free engines only (DuckDB / SQLite /
   Parquet-on-disk). No cloud accounts, no managed services. The reviewer clones and
   runs; there must be nothing to provision.

3. **Never silently drop, and never impute.** A record that fails validation is
   **quarantined with a machine-readable reason code**, not deleted and not guessed at.
   Row counts must reconcile: `rows_read = rows_loaded + rows_quarantined`. Silently
   discarding a record is as destructive as fabricating one — it is just harder to
   notice. This matters more here than in most domains: these are clinical oncology
   records, and an undercount of a patient's variants is a clinically misleading result,
   not a rounding error.

4. **Schema evolution is additive only.** A later batch that introduces new fields must
   not break queries written against an earlier batch. No destructive migrations, no
   renaming columns out from under a consumer, no dropping a field because a new batch
   stopped emitting it.

5. **Parse contracts, don't hardcode them.** VCF files are self-describing: `##INFO`,
   `##FORMAT` and `##FILTER` header lines declare the fields, their types and their
   cardinality, and the `CSQ` description declares its own pipe-delimited sub-field
   order. Read those declarations at runtime. Hardcoding field positions is the specific
   failure this exercise is built to expose — batch 2's `CSQ` grows from 6 sub-fields to
   7, and a positional parser survives that only by luck.

6. **Every decision carries a written rationale.** The assignment is explicit that the
   reasoning is graded at least as heavily as the code. An undocumented decision is an
   incomplete decision. This includes decisions *not* to do something — deliberate
   non-goals are worth stating.

7. **Reproducibility.** Running the pipeline twice must not duplicate or corrupt data.
   A clean checkout plus one documented command must reproduce the full result.

---

## 4. Claude-specific context

Claude-only environment notes, tool constraints and session conventions live in
[`CLAUDE.md`](CLAUDE.md). Read it in addition to this file.

@CLAUDE.md

*(Agents that do not support `@`-imports: open `CLAUDE.md` and read it directly.)*

---

## 5. Working agreement

The author of this repository will be asked to **walk through this code live and extend
it in a pairing session.** That constraint shapes everything:

- **Comprehensibility beats cleverness.** No metaprogramming, no dense one-liners, no
  framework the author has not used. If it cannot be explained aloud in thirty seconds,
  it is the wrong implementation.
- **Less, done well, beats more, done hastily.** The brief says so directly. Scope cut
  with a documented reason scores better than a half-working feature.
- **Surface tradeoffs, don't hide them.** When there are two defensible options, say so,
  give the case for each, and let the author choose. Do not quietly pick one and move on.
- **Explain as you go.** The author must own every decision well enough to defend it
  under questioning from the people who wrote the exercise.

### Note on AI assistance

The assignment explicitly encourages AI tooling and asks for a short note in the
submission README on **how it was used and where it was not trusted.** Keep this
honest and specific — as work progresses, record in the active context file which
parts were AI-drafted, which were hand-verified, and which AI suggestions were
rejected and why. That note is part of the deliverable, not an afterthought.
