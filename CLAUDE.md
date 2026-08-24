# CLAUDE.md — Claude-specific context

Supplements [`AGENTS.md`](AGENTS.md). **Read `AGENTS.md` first** — it holds the shared
operating rules and the context-loading protocol. This file covers only what's specific
to Claude.

---

## 1. Session conventions

- **Use the task list.** Create tasks with `TaskCreate` at the start of any multi-step
  work and close them with `TaskUpdate` — it's how the user tracks progress and picks
  the thread back up later.
- **Include a verification step.** Any non-trivial change ends with an explicit check —
  run the tests, re-read the diff, re-run the query and compare counts. Don't report
  work as done on the strength of the code having been written.
- **Ask before assuming on design forks.** Use `AskUserQuestion` for genuine forks; not
  for things discoverable in the repo or the data.
- **Profile before theorising.** The dataset is ~250 KB and fully inspectable. Any claim
  about its contents should be backed by a command actually run, not inferred from file
  names — several of its traps are invisible unless you look.

---

## 2. Proposing a context bump

When a design decision resolves, or the problem statement moves materially:

1. Read the current highest-version file in `working_contexts/`.
2. Draft a **new** file at `v<N+1>` with a fresh local timestamp
   (`date +%Y%m%dT%H%M%S`, no `Z`/UTC suffix — `AGENTS.md` §0). Never edit the old one.
3. Carry forward what's still true; move resolved items from *Open Decisions* to
   *Resolved Decisions* **with the reasoning that settled them**, not just the verdict.
4. Fill in the Changelog: what changed relative to `v<N>`, and why.
5. Tell the user what moved. Don't bump the version for cosmetic edits — the version
   history is a decision log, not a save history.

---

## 3. Tone for this project

Architecture is resolved and we're in the **implementation phase** — build to the
active context file's plan (`working_contexts/`), don't re-litigate settled decisions.

- Write code directly for work covered by a resolved plan (e.g. bronze's `data_loader`
  task breakdown). Flag it, don't just proceed, when a task requires a call the plan
  doesn't cover.
- When an idea rests on a factual error, **correct it directly and early** — catching a
  wrong premise before it becomes code is the point of this collaboration. Say what's
  wrong, why, and what it changes.
- Be concrete. "This has privacy implications" is worthless; "the collection date alone
  takes the cohort from 15% uniquely-identifiable to 100%, here's the count" is the
  standard.
- The user has to defend all of this to the people who wrote the exercise. Never hand
  them a conclusion they can't reconstruct themselves.
