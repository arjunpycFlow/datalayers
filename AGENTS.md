# AGENTS.md — Inocras Initial Data Layer

Operating context for any AI agent (Claude Code, Copilot, Cursor, etc.) working in this
repository. Read this file end to end before taking any action.

---

## 0. Context loading protocol — do this first, every session

`working_contexts/` holds the authoritative, evolving project context — problem
statement, architecture, open decisions. This file holds only the **stable** operating
rules. Before proposing an approach or writing code:

1. In `working_contexts/`, find the file with the highest version number `v<N>` (ties
   broken by latest timestamp) and read it in full.
2. Read [`data_context.md`](data_context.md) — how the raw data lands, the `sample_id`
   join contract, and the grain (patient → sample → variant call).
3. Where either conflicts with this file, **the context file / `data_context.md` wins**.

@data_context.md

*(Agents without `@`-import support: open `data_context.md` directly.)*

**Naming convention:**

```
working_contexts/initial_data_layer_context_v<N>_<timestamp>.md
                                              │     └── YYYYMMDDTHHMMSS, from
                                              │        `date +%Y%m%dT%H%M%S` — run, never guessed
                                              └── integer, monotonically increasing
```

No timezone suffix: an agent claiming `Z` (UTC) without actually converting its clock is
fabricating a fact. `v<N>` is the real tie-break; the timestamp is provenance only.

**Context files are append-only.** Never edit a published one in place — that destroys
the record of how a decision was reached. To revise, write a **new** file at `v<N+1>`,
carrying forward what's still true and logging the change in its Changelog. Same
immutability principle the pipeline applies to the landing zone: history is superseded,
never rewritten.

---

## 1. What this project is

A take-home exercise for Inocras: build the **first slice of a genomic data foundation**.
Somatic VCF files plus per-batch sample manifests arrive in a landing zone (a local
folder here; an S3 prefix in production). Ingest, validate, and clean them into a
**governed curated zone** that's reliably queryable both by researchers writing SQL
today and by a **natural-language assistant** later.

That second consumer is the real thesis: *"that assistant is only as reliable as the
foundation underneath it."* Every schema and naming decision should be defensible as
**"an LLM writing SQL against this cannot get it wrong."**

### Current status

> **ARCHITECTURE RESOLVED — bronze implementation underway.**
>
> Medallion architecture is settled (Parquet bronze → DuckDB silver → DuckDB gold
> marts; full design and rationale in the active context file). Storage engine, schema
> shape, idempotency mechanism, and defect policy are all `RESOLVED` — don't reopen
> them without a stated reason.
>
> **Bronze** has a task-by-task implementation plan (the `data_loader` CLI) — build to
> it. **Silver** has a readiness checklist for what bronze must guarantee, but no task
> breakdown yet — write that after bronze ships, against its actual output schema.
> **Gold** is untouched until silver ships. Don't skip layers out of order.
>
> A few questions remain genuinely open — see the active context file's *Open
> questions*: multi-sample VCFs, variant normalisation, which of two disagreeing
> population-frequency fields a mart should prefer, testing depth. Propose options with
> tradeoffs on those; don't commit to one unilaterally.

---

## 2. Repository layout

```
inocras_datalayers/
├── AGENTS.md                  ← you are here (stable operating rules)
├── CLAUDE.md                  ← Claude-specific conventions
├── data_context.md            ← how raw data lands: file relationships, join keys, grain
├── working_contexts/          ← versioned, append-only project context
│   └── initial_data_layer_context_v<N>_<ts>.md
├── warehouse/                 ← GENERATED — bronze/silver/gold output, gitignored
└── candidate_bundle/          ← AS PROVIDED BY INOCRAS — do not modify
    ├── README.md              ← the assignment brief
    └── data/                  ← THE IMMUTABLE LANDING ZONE
        ├── batch_2026_01/     ← 14 VCFs + sample_manifest.csv
        └── batch_2026_02/     ← 5 VCFs + sample_manifest.csv (drifted schema)
```

Anything the pipeline produces — curated tables, Parquet, a DuckDB file, quarantine
output, logs — is generated: it belongs in `warehouse/` (gitignored), never committed,
never written inside `candidate_bundle/`.

---

## 3. Hard rules

Non-negotiable, regardless of what the context file says.

1. **`candidate_bundle/data/` is immutable.** Never write to it, hand-edit a file, or
   "fix" a malformed file at rest — treat it as a read-only S3 raw zone. Every defect is
   handled in code, at read time.

2. **No paid infrastructure.** Local, free engines only (DuckDB / SQLite /
   Parquet-on-disk). The reviewer clones and runs; nothing to provision.

3. **Never silently drop, never impute.** A record that fails validation is
   **quarantined with a machine-readable reason code** — not deleted, not guessed at.
   `rows_read = rows_loaded + rows_quarantined` must always reconcile. Silently
   discarding a record is as destructive as fabricating one, just harder to notice — and
   in clinical oncology data, an undercount of a patient's variants is a misleading
   result, not a rounding error.

4. **Schema evolution is additive only.** A later batch adding fields must not break
   queries written against an earlier one. No destructive migrations, no renaming
   columns out from under a consumer, no dropping a field a new batch stopped emitting.

5. **Parse contracts, don't hardcode them.** VCF files self-describe: `##INFO`,
   `##FORMAT`, `##FILTER` header lines declare fields, types, and cardinality; `CSQ`'s
   description declares its own sub-field order. Read those at runtime. Hardcoding
   positions is the specific failure this exercise is built to expose — batch 2's `CSQ`
   grows from 6 sub-fields to 7, and a positional parser survives that only by luck.

6. **Every decision carries a written rationale.** Reasoning is graded at least as
   heavily as the code. This includes decisions *not* to do something — state deliberate
   non-goals.

7. **Reproducibility.** Running the pipeline twice must not duplicate or corrupt data. A
   clean checkout plus one documented command reproduces the full result.

---

## 4. Claude-specific context

Claude-only environment notes and session conventions live in
[`CLAUDE.md`](CLAUDE.md).

@CLAUDE.md

*(Agents without `@`-import support: open `CLAUDE.md` directly.)*

---

## 5. Working agreement

The author will walk through this code live and extend it in a pairing session. That
shapes everything:

- **Comprehensibility beats cleverness.** No metaprogramming, no dense one-liners, no
  framework the author hasn't used. If it can't be explained aloud in thirty seconds,
  it's the wrong implementation.
- **Less, done well, beats more, done hastily.** The brief says so directly. Scope cut
  with a documented reason scores better than a half-working feature.
- **Surface tradeoffs, don't hide them.** When two options are defensible, say so, give
  the case for each, and let the author choose.
- **Explain as you go.** The author must own every decision well enough to defend it to
  the people who wrote the exercise.

### Note on AI assistance

The brief asks for a short README note on how AI tooling was used and where it wasn't
trusted. Keep it honest and specific — record in the active context file which parts
were AI-drafted, which were hand-verified, and which AI suggestions were rejected and
why. That note is part of the deliverable, not an afterthought.
