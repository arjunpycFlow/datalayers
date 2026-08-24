# Product Guidelines — inocras_datalayers

## Voice and tone

Concise and direct, reasoning-forward. Every claim about the data is backed by a
command actually run, not inferred from file names (`../CLAUDE.md` §1). Every non-obvious
decision states its tradeoff, not just its verdict — the take-home brief grades the
README's reasoning at least as heavily as the code.

## Design principles

1. **Never silently drop, never impute.** A record that can't be represented cleanly is
   quarantined with a machine-readable reason, never deleted, never guessed at.
2. **Comprehensibility beats cleverness.** No metaprogramming, no dense one-liners, no
   framework the author hasn't used. The author pairs on this code live — if it can't be
   explained aloud in thirty seconds, it's the wrong implementation.
3. **Schema evolution is additive only.** A later batch's new fields extend the schema;
   they never break a query written against an earlier batch.
4. **Every decision carries a written rationale**, including decisions *not* to do
   something — deliberate non-goals are stated, not left implicit.

See `../AGENTS.md` §3 (Hard rules) and §5 (Working agreement) for the full, authoritative
list — this file summarizes, it doesn't supersede.
