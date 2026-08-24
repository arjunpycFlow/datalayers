# Implementation Plan: Documentation — bullets-first README + docs/ deep-dives

**Track ID:** docs-restructure_20260824
**Spec:** [spec.md](./spec.md)
**Created:** 2026-08-24
**Status:** [x] Complete

## Overview

Work outward from the existing, already-verified README content: relocate full
detail into `docs/` first (nothing invented, everything moved), then rewrite the
README section by section as bullets-first with links back. Verify content parity by
diffing/grepping against the pre-restructure README, not by eye.

## Phase 1: Scaffold `docs/` + governance and operations deep-dives

### Tasks

- [x] Task 1.1: Create `docs/governance.md` — move the full Governance posture
      content (4 paragraphs + S3/IAM mermaid diagram) from `README.md` verbatim.
- [x] Task 1.2: Create `docs/operations.md` — move the full Operational posture
      content (idempotency semantics, reconciliation invariants, troubleshooting,
      the next-phase unmapped-vocabulary flow + its mermaid diagram) from
      `README.md` verbatim.

### Verification

- [x] Diff each new `docs/` file's prose against the corresponding pre-restructure
      README section — content matches, not just "looks similar." Diffed both;
      only deltas are heading level (`##`→`#`, standalone file), removal of
      same-doc cross-refs ("above"/"below" → standalone phrasing), and the added
      back-link footer. No fact dropped.

## Phase 2: `docs/data_architecture/` — bronze, silver, gold deep-dives

### Tasks

- [x] Task 2.1: Create `docs/data_architecture/bronze.md` — move the full Bronze
      layer section content (what it does, output shape, exit codes, the `S-0011`/
      `S-0020` real findings, the status block's numbers) from `README.md`.
- [x] Task 2.2: Create `docs/data_architecture/silver.md` — same shape, + the `VAF`
      ×100 scale-drift finding.
- [x] Task 2.3: Create `docs/data_architecture/gold.md` — same shape, + the
      `n_samples_with_unknown_patient` finding.
- [x] Task 2.4: Add one **new** mermaid diagram to each of the three files, showing
      that layer's internal flow — bronze: parse VCF+manifest → join → land-or-
      quarantine; silver: read bronze → normalize+split-grain → land-or-quarantine;
      gold: read silver → apply 4-tier contract → mart-or-quarantine. These are
      distinct from the cross-layer diagram (which stays in the README) — they show
      what happens *inside* one layer.

### Verification

- [x] All three files diffed against their pre-restructure README sections for
      content parity. Only deltas: heading level, and one same-doc cross-ref
      turned into a real link (silver → operations.md anchor).
- [x] All three new diagrams render with balanced fences (3 blocks each, verified)
      and don't duplicate the cross-layer diagram's content (each shows internal
      per-record routing, not the cross-layer bronze→silver→gold shape).

## Phase 3: Rewrite README's per-layer sections as bullets + links

### Tasks

- [x] Task 3.1: Replace the Bronze layer section with: 3-6 bullets (what it
      ingests, what it outputs, the one-line real numbers, the `S-0011` handling in
      one bullet) + a link to `docs/data_architecture/bronze.md`.
- [x] Task 3.2: Same for Silver (bullets include the `VAF` finding as its own
      bullet, not buried) + link to `docs/data_architecture/silver.md`.
- [x] Task 3.3: Same for Gold (bullets include the `n_samples_with_unknown_patient`
      finding as its own bullet) + link to `docs/data_architecture/gold.md`.

### Verification

- [x] Each rewritten section is bullets-first — the picture is clear from the
      bullets alone, confirmed by reading only the bullets and checking nothing
      essential requires the (now-removed) prose to understand.
- [x] Every specific number that was in the old prose (795/295 rows, `TP53`
      57/19/17/1, etc.) is still present — either in the README's bullets or in the
      linked `docs/` file — checked with `grep` against the old content, not
      assumed. Confirmed via automated grep sweep across all 6 files.

## Phase 4: Rewrite Governance and Operational posture as bullets + links

### Tasks

- [x] Task 4.1: Replace the Governance posture section with 5-6 bullets (per-tier
      de-id, access-not-anonymisation, the `GRANT` limitation, what an AI assistant
      needs) + link to `docs/governance.md`. Dropped the S3 diagram from the README
      (now lives in the linked doc only) per the "short" requirement.
- [x] Task 4.2: Replace the Operational posture section with 5-6 bullets
      (idempotency asymmetry, each layer's invariant in one line, troubleshooting)
      + link to `docs/operations.md`. Kept "Next phase: unmapped-vocabulary
      review" as bullets + link, not the full flow inline.

### Verification

- [x] Both sections bullets-first; the `GRANT`-is-unsupported fact and the Bronze
      two-invariant fact (both real, previously-verified findings) are still present
      as bullets, not silently dropped in the compression.

## Phase 5: Rewrite the AI assistance note

### Tasks

- [x] Task 5.1: Restructure the AI assistance note into one bullet-set per finding
      (bronze's `S-0011` gap, silver's `VAF` finding + the `MAX_POP_AF` self-
      correction, gold's `n_samples_with_unknown_patient` gap, the documentation
      pass's agentic-authoring-gap note) — each a short bullet list plus 1-2
      sentences of "why it mattered," not a full paragraph. Stays in `README.md` —
      it's the brief's required deliverable, not a deep-dive to defer.

### Verification

- [x] Every finding's key fact (the specific numbers, the specific bug in each
      case) survives the compression — checked against the pre-restructure text.

## Phase 6: Final verification

### Tasks

- [x] Task 6.1: Grep every `docs/...` link in the finished README and confirm each
      path resolves on disk. All 5 links (governance, operations x2, bronze,
      silver, gold) resolve; anchor links (`#operational-posture`,
      `#next-phase-unmapped-vocabulary-review`) match real headings.
- [x] Task 6.2: Line-count the finished README against the pre-restructure 429
      lines — confirm a real reduction, not cosmetic. 428 → 273 lines (36%
      reduction).
- [x] Task 6.3: Full top-to-bottom read-through of the finished README — checking
      tone (warm, short, not clinical), that every section's bullets alone convey
      the picture, and that nothing contradicts another section (same check as the
      last doc track, which caught a real bug that way). No contradictions found.
- [x] Task 6.4: Confirm `uv run pytest` still 100% passing (docs-only change,
      confirmed anyway, never assumed inert). 105 passed.

### Verification

- [x] All four tasks pass; any gap found gets fixed before this track is marked
      complete, not deferred silently.

## Final Verification

- [x] All acceptance criteria in `spec.md` met.
- [x] `scratch_pad.md`'s content-inventory table cross-checked against what
      actually shipped — every row's "destination" is real and correct.
- [x] Ready for review.

---

_Generated by Conductor from `scratch_pad.md`. Tasks will be marked [~] in progress and
[x] complete._
