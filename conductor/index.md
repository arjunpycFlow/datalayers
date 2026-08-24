# Conductor - inocras_datalayers

Navigation hub for project context.

## Quick Links

- [Product Definition](./product.md)
- [Product Guidelines](./product-guidelines.md)
- [Tech Stack](./tech-stack.md)
- [Workflow](./workflow.md)
- [Tracks](./tracks.md)

## Relationship to the rest of this repo

Conductor's artifacts sit alongside, not instead of, the project's own operating docs:

- [`../AGENTS.md`](../AGENTS.md) — stable operating rules, hard rules, working agreement.
- [`../data_context.md`](../data_context.md) — landing-zone structure and data contract.
- [`../working_contexts/`](../working_contexts/) — versioned, append-only architecture
  decisions (highest `v<N>` is authoritative).

Where a Conductor artifact and `working_contexts/` disagree, `working_contexts/` wins —
same precedence rule as `AGENTS.md` §0.

## Active Tracks

None currently active.

<!-- Auto-populated by /conductor:new-track -->

## Completed

- [bronze-layer_20260823](./tracks/_archive/bronze-layer_20260823/index.md) — Bronze
  Layer — data_loader CLI (6/6 phases, archived)
- [silver-layer_20260823](./tracks/_archive/silver-layer_20260823/index.md) — Silver
  Layer — silver_builder CLI (6/6 phases, archived)
- [gold-layers_20260823](./tracks/_archive/gold-layers_20260823/index.md) — Gold
  Layer — gold_builder CLI (6/6 phases, archived)
- [documentation_20260824](./tracks/_archive/documentation_20260824/index.md) —
  Documentation — README restructure (5/5 phases, archived)

## Getting Started

Run `/conductor:new-track` for the next piece of work.
