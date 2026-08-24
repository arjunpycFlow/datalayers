# CLAUDE.md — Claude-specific context

Supplements [`AGENTS.md`](AGENTS.md). **Read `AGENTS.md` first** — it holds the shared
operating rules and the context-loading protocol. This file covers only what is specific
to Claude and to this environment.

---

## 1. Environment constraints

Work on this repository frequently happens from a **Claude Cowork cloud session** with
the project folder bridged from the local machine (`mac-lan`). That bridge has sharp
edges worth knowing before you waste a turn on them:

| Constraint | Consequence |
|---|---|
| The device shell (`device_bash`) **cannot delete files** — `rm`/`rmdir`/`unlink` fail with `Operation not permitted` | **Git cannot be run inside the mounted folder.** Git must unlink `index.lock` and its temp objects after every operation; it leaves them behind and wedges the repo. |
| The mounted folder is read/write but delete-denied | Writes and `mv` succeed; cleanup does not. Prefer writing new files over rewriting in place. |
| `/tmp` on the device VM is a normal filesystem | Full read/write/delete. Use it as scratch space for anything that needs deletes. |
| The cloud container's filesystem is separate from the device | A file written in one is not visible to the other. Move files with `device_stage_files` (device → cloud) and `SendUserFile` + `device_commit_files` (cloud → device). |
| `/mnt/user-data/uploads/` is read-only | Copy staged files elsewhere before modifying. |
| `gh` CLI is installed on neither machine | GitHub repo creation and pushes are done by the user from their own terminal. |

### Git workflow in this repo

**Do not run `git add` / `git commit` against the mounted working tree.** It will fail
and leave `.git` in a broken state requiring manual cleanup.

If a commit must be made from a Claude session, use the scratch-dir pattern:

```bash
# 1. build in /tmp where deletes work
rm -rf /tmp/gitbuild && mkdir -p /tmp/gitbuild
cp -r "$HOME/mnt/inocras_initial_data_layer/." /tmp/gitbuild/
rm -rf /tmp/gitbuild/.git          # drop any wedged .git

# 2. do all git work there
cd /tmp/gitbuild && git init -q -b main && git add -A && git commit -q -m "..."

# 3. install the finished .git back into the real folder
cp -r /tmp/gitbuild/.git "$HOME/mnt/inocras_initial_data_layer/.git"
```

**By strong preference, don't do that at all** — hand the user the git commands to run
in their own terminal, where none of these restrictions apply. Reserve the scratch-dir
pattern for repository bootstrap.

---

## 2. Session conventions

- **Use the task list.** Create tasks with `TaskCreate` at the start of any multi-step
  piece of work and close them with `TaskUpdate`. The user sees this rendered as a
  progress widget; it is how they follow along and how they pick the thread back up in a
  later session.
- **Include a verification step.** Any non-trivial change ends with an explicit check —
  run the tests, re-read the diff, re-run the query and compare counts. Do not report
  work as done on the strength of the code having been written.
- **Ask before assuming on design forks.** See the working agreement in `AGENTS.md`.
  Use `AskUserQuestion` for genuine forks; do not use it for things discoverable in the
  repo or the data.
- **Profile before theorising.** The dataset is ~250 KB and fully inspectable. Any claim
  about what is in it should be backed by a command that was actually run, not by
  inference from the file names. Several of the traps in this data are invisible unless
  you look.

---

## 3. Proposing a context bump

When a design decision gets resolved, or the problem statement moves materially:

1. Read the current highest-version file in `working_contexts/`.
2. Draft a **new** file at `v<N+1>` with a fresh UTC timestamp — never edit the old one.
3. Carry forward everything still true; move resolved items out of *Open Decisions* into
   *Resolved Decisions* **with the reasoning that settled them**, not just the verdict.
4. Fill in the Changelog section describing what changed relative to `v<N>` and why.
5. Tell the user what moved. Do not bump the version for cosmetic edits — the version
   history should read as a decision log, not a save history.

---

## 4. Tone for this project

The user is deliberately in a **thinking and understanding phase**, not a build phase.
They have said so explicitly. Respect it:

- Lead with analysis, options and tradeoffs, not with generated code.
- When the user floats an idea that rests on a factual error, **correct it directly and
  early** — the value of this collaboration is catching a wrong premise before it becomes
  an architecture. Say what is wrong, why, and what it changes.
- Be concrete. "This has privacy implications" is worthless; "the collection date alone
  takes the cohort from 15% uniquely-identifiable to 100%, here is the count" is the
  standard.
- The user will have to defend all of this to the people who wrote the exercise. Never
  hand them a conclusion they cannot reconstruct themselves.
