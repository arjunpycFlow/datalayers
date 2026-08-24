# Specification: Documentation — README restructure + governance/operational posture

**Track ID:** documentation_20260824
**Type:** Chore
**Created:** 2026-08-24
**Status:** Draft

## Summary

Audit the existing documentation for gaps, then restructure `README.md` to cover
five things it currently doesn't (well enough): architecture at a glance, repository
layout, a consolidated how-to-operate quickstart, governance posture, and a new
operational posture section — with mermaid diagrams where a picture beats a table.
Also records, as an explicit next-phase recommendation rather than new scope, the
unmapped-vocabulary review flow that closes a documentation gap found mid-track (the
agentic crosswalk-authoring loop designed in `working_contexts/` v2 §4.4 was never
demonstrated as its own artifact).

## Context

From `conductor/product.md`: documentation good enough that "someone (or an agent)
could trust the data without asking you" is one of the brief's explicit grading
criteria. Bronze, silver, and gold (all complete — `conductor/tracks/_archive/`) each
added their own README section as they shipped, but the file was never looked at as
a whole — no picture of the full pipeline, no repository map, no single "how would I
actually run and troubleshoot this" narrative, and no mention that a 105-test suite
exists at all. Full requirements and the audit that produced them are in
`../../../../scratch_pad.md`.

## Acceptance Criteria

- [ ] `README.md` gains an **Architecture at a glance** section — one mermaid
      diagram showing landing → bronze → silver → gold with each layer's quarantine
      branch shown explicitly.
- [ ] `README.md` gains a **Repository layout** section — compact directory tree,
      one line of purpose per top-level entry.
- [ ] The three existing per-layer "Running the X-layer" sections are consolidated
      under **How to operate**, preceded by a single copy-pasteable quickstart
      (clean checkout → all three layers → tests) and followed by a **CLI reference**
      comparison table (all three tools' reads/writes/exit-codes/idempotency side by
      side) and an explicit **running tests** subsection — `uv run pytest` is
      currently mentioned nowhere in the README.
- [ ] The existing **Governance note** is retitled **Governance posture** and gains
      one mermaid diagram (the S3-to-S3 IAM zone mapping from `working_contexts/` v2
      §6.3, currently only a table).
- [ ] A new **Operational posture** section states the bronze-vs-silver/gold
      idempotency asymmetry explicitly as a deliberate design choice (not an
      inconsistency), each layer's reconciliation invariant, and a troubleshooting
      note for non-zero exit codes.
- [ ] The agentic vocabulary-authoring gap is documented as a **named next-phase
      recommendation** with its own mermaid flow diagram, kept explicitly separate
      from the three existing pipeline CLIs — not built this pass.
- [ ] Two stale `conductor/tracks/gold-layers_20260823/` path references (predating
      the archive move) are fixed to `_archive/gold-layers_20260823/`.
- [ ] Every mermaid code fence is balanced and every diagram uses syntax already
      confirmed to work (quoted multi-line node labels, `-.->` for quarantine
      branches, `{{...}}` for the human-review decision point).

## Dependencies

None new. References bronze/silver/gold (all complete, archived) and
`working_contexts/` v1 §4, v2 §4.4, §6.2, §6.3 for content already resolved
elsewhere — this track restructures and diagrams existing decisions, it does not
make new ones.

## Out of Scope

- Building the unmapped-vocabulary review CLI itself — recorded as a next-phase
  recommendation only, per direct instruction not to build it this pass.
- Any change to `data_loader`/`silver_builder`/`gold_builder` code or tests — this
  track touches documentation only.
- Re-litigating any already-resolved architecture decision — this track diagrams and
  organizes what's already decided, it doesn't reopen it.

## Technical Notes

Full detail (the 8-item gap audit, the exact mermaid diagram content, the
next-phase flow's design rationale) is in `../../../../scratch_pad.md`. The
restructured `README.md` content already exists in the working tree (written before
this track was formally opened, per the user's request to draft it first and
formalize the record after) — this track's plan verifies it against the acceptance
criteria above rather than writing it from scratch.
