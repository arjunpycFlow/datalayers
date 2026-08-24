# Product Definition — inocras_datalayers

## Description

A CLI pipeline that ingests somatic VCF + sample manifest batches into a governed,
queryable curated zone (bronze/silver/gold) for researchers and an eventual
natural-language assistant.

## Problem statement

Somatic VCF + manifest batches arrive messy and change shape over time (schema drift,
malformed files, referential gaps). Researchers need to query them reliably, and a
future NL assistant needs a foundation trustworthy enough to answer questions without a
human sanity-checking its SQL. This is the take-home exercise's stated thesis: *"that
assistant is only as reliable as the foundation underneath it."*

## Target users

- **SQL-writing researchers, today** — want flexibility, full raw detail, the ability to
  reach fields a modeller didn't anticipate.
- **A natural-language assistant, later** — wants rigidity: a small, stable, fully
  documented surface with no ambiguity about which column answers which question.

These two consumers have opposing preferences; schema and naming decisions have to
serve both (see `working_contexts/` for how that tension gets resolved).

## Key goals

- Reliably queryable curated zone.
- Reproducible re-runs — running the pipeline twice must not corrupt or duplicate data.
- Never silently drop or impute a record — every record is accounted for.
- Additive schema evolution — a later batch's new fields must not break earlier queries.

## Source of truth for scope and status

This file is a stable summary. For the *current* architecture, resolved decisions, and
what's actively being built, read the highest-version file in `../working_contexts/`
(per `../AGENTS.md` §0) — it changes frequently and this file does not track it
line-for-line.
