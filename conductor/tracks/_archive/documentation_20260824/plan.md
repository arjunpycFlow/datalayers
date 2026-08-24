# Implementation Plan: Documentation — README restructure

**Track ID:** documentation_20260824
**Spec:** [spec.md](./spec.md)
**Created:** 2026-08-24
**Status:** [x] Complete

## Overview

The restructured `README.md` content already exists in the working tree. This plan
verifies it section-by-section against `spec.md`'s acceptance criteria — no markdown
test suite exists, so "verification" means actually reading the rendered content and
checking each specific claim, the same rigor as code verification, just applied to
prose and diagrams instead of test assertions.

## Phase 1: Architecture + repository layout

### Tasks

- [x] Task 1.1: Confirmed **Architecture at a glance** exists with one mermaid
      `flowchart` showing landing → bronze → silver → gold; all three quarantine
      branches (`BQ`, `SQ`, `GQ`) are distinct, labeled `-.->` edges, not folded
      into the main flow.
- [x] Task 1.2: Confirmed **Repository layout** against a fresh `ls -la` of the repo
      root, not memory. **Found and fixed a real gap:** `pyproject.toml` (the actual
      dependency/CLI-entry-point config) was missing from the tree — added.
      `main.py` correctly left out — confirmed it's a dead scaffold stub, unreferenced
      by any of the three real CLIs (each has its own `cli.py`, wired via
      `pyproject.toml`), and noted that explicitly in the README rather than silently
      omitting it with no explanation.

### Verification

- [x] Both sections present; the layout tree's entries checked against a fresh
      `ls -la` of the repo root — one real gap found and fixed, not just confirmed
      clean.

## Phase 2: How to operate

### Tasks

- [x] Task 2.1: Confirmed the quickstart block exists exactly as required (clean
      checkout → `uv sync` → all three CLIs → `uv run pytest`) before the per-layer
      detail.
- [x] Task 2.2: Diffed the working tree against the last-committed README
      (`git diff ad9fd4a -- README.md`) line by line for every removed line — all
      were reorganizations (exit codes moved into the new comparison table,
      module-form/flags condensed from a code block to inline text) or
      pointer-summarized with the source cited (S3 per-prefix-policy detail now
      says "Full detail: v2 §6.3" rather than restating it) — nothing substantive
      lost.
- [x] Task 2.3: Cross-checked the CLI reference table's exit codes against the real
      `return` statements in all three `cli.py` files, condition by condition — all
      match exactly (bronze: batch missing/empty → 1, reconciliation → 2; silver:
      `FileNotFoundError` → 1, `ReconciliationError` → 2; gold: silver-db missing →
      1, reconciliation/schema-leak → 2).
- [x] Task 2.4: Confirmed **Running tests** subsection exists; re-ran
      `uv run pytest` fresh — 105 passed, matches the README's claimed count exactly.

### Verification

- [x] `uv run pytest` count in the README matches the real count (105/105, checked
      this session, not carried over from an earlier claim).
- [x] Exit-code table cross-checked against `data_loader/cli.py`,
      `silver_builder/cli.py`, `gold_builder/cli.py` directly — exact match.

## Phase 3: Governance posture

### Tasks

- [x] Task 3.1: Confirmed retitled **Governance posture**. All four required
      paragraphs present and intact: per-tier de-identification, the k-anonymity
      limitation ("access not anonymisation"), the `GRANT` caveat + S3 diagram, and
      what an AI assistant needs.
- [x] Task 3.2: Re-read `working_contexts/` v2 §6.3 fresh (not from memory) and
      checked the mermaid diagram against it directly: same 5 zones, same roles per
      zone (ingestion/transform/gold-job roles; broad researcher vs. named
      time-boxed CloudTrail-audited access for the two gold tiers). Cross-cutting
      details (SSE-KMS, VPC endpoints) correctly left to the "Full detail: v2 §6.3"
      pointer rather than cluttering the diagram.

### Verification

- [x] Diagram's zone names/roles checked directly against `working_contexts/` v2
      §6.3 this session — exact match, no drift.

## Phase 4: Operational posture + next-phase recommendation

### Tasks

- [x] Task 4.1: Confirmed **Operational posture** exists with the idempotency
      asymmetry stated as deliberate, a troubleshooting note, and per-layer
      reconciliation invariants. **Found and fixed a real internal contradiction:**
      Bronze's invariant was stated as one combined formula
      (`rows_read == rows_written + rows_quarantined + duplicates_collapsed`), but
      the actual code (`data_loader/run.py`) runs **two independent checks**
      (manifest-side, VCF-side) — the exact same fact this README's own AI
      assistance note already states further down. Fixed to match the real
      implementation instead of contradicting the section beneath it.
- [x] Task 4.2: Confirmed **Next phase: unmapped-vocabulary review** exists,
      labeled "Not built this pass," with the full mermaid flow
      (quarantine → on-demand review → agent proposes → human approves/rejects →
      crosswalk YAML commit → next run resolves).
- [x] Task 4.3: Confirmed the flow is explicitly described as on-demand and
      separate from the three pipeline CLIs, not part of any deterministic run.

### Verification

- [x] Re-read `working_contexts/` v2 §4.4 directly (not from memory) — its own
      ASCII propose/review diagram matches the README's framing exactly: the
      authoring-loop shape was already designed, just never turned into working
      tooling. Also cross-checked Silver's and Gold's stated invariants directly
      against `silver_builder/run.py` and `gold_builder/run.py` — both accurate as
      written, only Bronze's needed the fix above.

## Phase 5: Final polish + stale-path check

### Tasks

- [x] Task 5.1: Grepped the full README — zero non-archived
      `conductor/tracks/gold-layers_20260823/` hits (both remaining references
      correctly go through `_archive/`).
- [x] Task 5.2: 26 fence lines = 13 balanced pairs, verified alternating open/close
      by listing every fence line number. 3 `mermaid` blocks, all properly closed.
- [x] Task 5.3: Full top-to-bottom read-through done (not skipped) — this is what
      caught Phase 4's Bronze-invariant contradiction in the first place. No other
      duplication, no broken internal cross-references (`**Next phase:...**` and
      `**Operational posture**` both link to real, present sections), no remaining
      contradictions between sections.

### Verification

- [x] Fence-balance check passes; zero stale-path hits; full read-through done and
      it found a real issue (Phase 4's), confirming it wasn't a rubber-stamp pass.

## Final Verification

- [x] All acceptance criteria in `spec.md` met — plus two real issues found and
      fixed *during* verification that weren't anticipated in the plan (the
      `pyproject.toml` layout gap, the Bronze reconciliation-invariant
      contradiction) — the point of verifying against reality instead of just
      checking the plan off.
- [x] `uv run pytest` still 105/105 passing (docs-only change, confirmed anyway,
      not assumed inert).
- [x] `scratch_pad.md`'s full 8-item gap audit cross-checked against the shipped
      README — all 8 addressed, nothing quietly dropped between drafting and
      delivery.
- [x] Ready for review.

---

_Generated by Conductor from `scratch_pad.md`. Tasks will be marked [~] in progress and
[x] complete._
