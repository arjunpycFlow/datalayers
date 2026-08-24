# Specification: Documentation — bullets-first README + docs/ deep-dives

**Track ID:** docs-restructure_20260824
**Type:** Chore
**Created:** 2026-08-24
**Status:** Complete

## Summary

Split `README.md`'s long, prose-first sections (Bronze/Silver/Gold/Governance/
Operational posture — 429 lines total) into a new `docs/` directory holding the full
detail, and rewrite the README itself to be bullets-first, warm, and short — every
topic gets a scannable bullet list before any explanation, with a link to the
matching `docs/` file for the full reasoning. Add per-layer internal-flow mermaid
diagrams that don't exist yet.

## Context

Direct user feedback, verbatim: *"there are portions which are really long,
containing valuable information. they are not in a easily consumable format...
Ensure the value and gold hidden inside those description is laid out in a bullet
point or a very short summary first then present the explanation."* And: *"README.md
should be intuitive, warm and welcoming - short but contains the information and
directives on where you can find additional information... One should be able to get
a clear picture on each item from the readme.md itself. When they need deep dive
they can look into the docs references."* Full content-migration plan (exactly what
moves where, verified against the current README) is in `../../../scratch_pad.md`.

## Acceptance Criteria

- [x] `docs/governance.md`, `docs/operations.md`,
      `docs/data_architecture/{bronze,silver,gold}.md` exist, each holding the full
      prose currently in the corresponding README section — checked by diff, not
      assumed equivalent.
- [x] Every major README section leads with a bulleted list, not a paragraph.
- [x] Every `docs/` link in the README resolves (relative path actually checked).
- [x] Each of the three layer docs has its own **new** mermaid diagram of that
      layer's internal flow (parse/join/normalize/contract-apply → land-or-quarantine)
      — distinct from the existing cross-layer diagram, which stays in the README.
- [x] The AI assistance note is bullets-first per finding, not four long paragraphs
      — it stays in `README.md` (explicit submission requirement from the brief, not
      a deep-dive to defer).
- [x] No fact is lost — every specific number currently in the README (795/295 rows,
      `TP53` 57/19/17/1, the `VAF` ×100 confirmation, `S-0003`/`S-0011`/`S-0012`'s
      gold-mart quarantine reasons, etc.) is still present somewhere, verified by
      grep against the old content, not assumed carried over.
- [x] The finished README is noticeably shorter than 429 lines while still giving a
      complete picture — deep-dive detail is one click away, not gone. 428 → 273.

## Dependencies

None new — restructures existing, already-verified content. No code or test changes.

## Out of Scope

- Any change to `data_loader`/`silver_builder`/`gold_builder` code or tests.
- Building the unmapped-vocabulary review CLI (still a documented next-phase
  recommendation, now living in `docs/operations.md` instead of the README).
- Re-verifying facts already verified in the prior documentation track — this track
  relocates and reformats content, it doesn't re-derive it from scratch. (Any
  genuinely new inconsistency found during the move is still fixed, same standard
  as always — just not a from-scratch re-audit.)

## Technical Notes

Full migration table (exactly which README content moves to which `docs/` file) is
in `../../../scratch_pad.md`. The restructure works from the README as it stands
after the last documentation track (`conductor/tracks/_archive/documentation_20260824/`),
not from an earlier version.
