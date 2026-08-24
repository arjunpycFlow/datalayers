# Workflow — inocras_datalayers

## TDD policy

**Flexible** — add tests where they make sense, not mandated line-by-line. In practice
that means: tests for parsing logic and the known data-edge-cases (schema drift in
`CSQ`, the `HOTSPOT` Flag field, `S-0011`'s conflicting duplicate, `S-0020`'s
truncation), not full coverage for its own sake. Given a track's Plan phases already
name their "test first" per phase (see `../scratch_pad.md` for the bronze-layer
example), follow that where a plan specifies it.

## Commit strategy

**Conventional Commits** (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, etc.).

## Code review

**Self-review via the verification step.** Solo project, no second engineer. Every
non-trivial change ends with an explicit check — run the tests, re-read the diff,
re-run the query and compare counts (`../CLAUDE.md` §1) — standing in for what a second
reviewer would otherwise catch.

## Verification checkpoints

**After each phase completion.** Run all tests written so far, verify, then commit —
don't accumulate uncommitted work across phase boundaries. Matches the phase-checkpoint
convention already used in `../scratch_pad.md`'s bronze-layer plan.

## Task lifecycle

1. Track created with a Spec (what/why, data contract, resolved design decisions,
   schemas, acceptance criteria) and a phased Plan (each phase: goal, test-first, steps,
   done-when, depends-on).
2. Each phase implemented in dependency order — don't start a phase before its
   dependency phase is committed.
3. Verification checkpoint at the end of each phase (see above).
4. Track-level acceptance criteria (in the Spec) checked off only once every phase is
   done and verified — not self-reported from the code having been written.
