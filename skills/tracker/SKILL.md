---
name: tracker
description: >
  Create and keep a live project progress board: one shared claude.ai Artifact page
  (the same template for every project) backed by the artifact's database. Use when
  the user says "tracker", "progress board", "project board", "status board",
  "track this project", "set up a tracker", "update the tracker", "log this on the
  board", or asks to recount progress, rebuild the board, or share it.
  Actions: create, item updates, log, progress recount, rebuild, sharing.
allowed-tools: Bash, Read, Write, Artifact, ArtifactData
argument-hint: "[create | start <item> | finish <item> | backlog <item> | log <text> | recount | rebuild | share]"
---

# Tracker - Live Progress Board

One HTML page, identical for every project, published as a claude.ai Artifact with
the `db` capability. The page holds no project data: its title, subtitle, repo link,
work items, status, activity log and progress all come from the artifact's database,
and every open view updates live. Updating the board means writing documents with
`ArtifactData`, never editing HTML.

- Page: `${CLAUDE_PLUGIN_ROOT}/skills/tracker/template.html`
- Data shape, with one example of each document: `${CLAUDE_PLUGIN_ROOT}/skills/tracker/reference.md`

Read `reference.md` before the first write in a session.

## Hard rules

1. **Real timestamps only.** Every `updatedAt`, `measuredAt` and log `at` comes from
   `date -u +%Y-%m-%dT%H:%M:%SZ`, run at the moment of the write, or, for a done item,
   from the PR's `mergedAt` (`gh pr view <n> --json mergedAt -q .mergedAt`). Never
   hand-typed, never rounded, never in the future.
2. **Progress is measured, never estimated.** Every number in `meta/progress` comes
   from a count you ran, and `basis` says what was counted.
3. **Milestone status comes from the code or the real state**, not just the issue's
   open/closed state. A closed issue whose work is not merged is not `done`; an open
   issue whose work is merged and live is.
4. **Pin every write with `if_version`.** Read the doc, keep the version it returns,
   and pass it on the `update`. On a version conflict, re-read and re-apply; never
   write blind over someone else's change.
5. **Update at every start, merge and new finding**, in the same turn the event
   happens. A stale board is worse than none.
6. **Spell `area` names consistently.** Filters group by exact string: `Auth` and
   `auth` are two areas. Reuse the names already on the board (`list` `items` first).

## Tools

- **Artifact** publishes the page. If the session's Artifact tool asks you to run
  its quickstart first, run it before anything else.
- **ArtifactData** reads and writes the database. Load it with ToolSearch the first
  time you need it. Operations: `get`, `list`, `query`, `set`, `update`,
  `str_replace`, `delete`, `batch`. Follow the tool's own schema for field names.
- **Batch** whenever one change needs more than 2 writes (for example: finish an
  item, start the next, and log both).

## Actions

### create

1. Run the Artifact tool's quickstart if the session's Artifact tool asks for it.
2. Copy `template.html` unchanged to the session scratchpad and publish that copy
   with the Artifact tool:
   - `capabilities: {db: {rules: [{path: "items", read: "view", write: "admin"}, {path: "meta", read: "view", write: "admin"}]}}`
   - icon `checklist`
   - a title naming the project (the page's own heading comes from `meta/config`)

   Do not edit the copy: anything project-specific belongs in the database.
3. Seed with `ArtifactData` (one `batch`), using a fresh `date -u` timestamp:
   - `meta/config`: `{title, subtitle, repoUrl}`. Omit `repoUrl` when the project
     has no web repo; issue and PR numbers then show as plain `#N` text.
   - `meta/status`: `{current, next, updatedAt, log: [{at, text: "Tracker created."}]}`
   - `meta/progress`: either the first measured recount (see **progress recount**)
     or nothing yet. The progress panel and milestones stay hidden until it exists.
   - `items/*`: the work already known, if any.
4. Record the artifact URL in the project's memory or notes (wherever this project
   keeps durable pointers), with the date and the account that owns it.

### item updates

Each item is one doc, `items/<id>`. Use a stable, readable id: the issue number
(`items/142`) or a short kebab slug (`items/login-rate-limit`). Every change sets
`updatedAt`. Use `update` with `if_version` on an existing item; `set` only to
create one.

| Event | Write |
| ----- | ----- |
| Start work | `status: "active"`, `updatedAt` now; also set `meta/status.current` |
| Queue it | `status: "queued"`, `order` (lower shows first) |
| Finish (merged) | `status: "done"`, `pr: <number>`, `updatedAt` = the PR's `mergedAt` |
| Park it | `status: "backlog"`, `flag: "security"`, `"decision"` or `"drift"` when it needs one, and a `note` saying why |
| Note edit | `note` (plain text; line breaks are kept), `updatedAt` now |

A finish usually comes with a start (the next item), a `meta/status` change and a
log line: send them as one `batch`.

`flag` drives the left-pane tiles: open items flagged `security` count under
Security; open items flagged `decision` or `drift` count under "Parked sign-offs".
Those are items parked for a sign-off later, before cutover. They never block
work and are not a request for input: keep working, and do not stop to ask about
them. A `decision` item's card reads "sign-off later".

### log

The Recent activity pane shows `meta/status.log`, newest first.

1. `get` `meta/status` and keep its version.
2. Build the new log: `[{at: <date -u now>, text}, ...old log]`, cut to at most
   40 entries.
3. `update` `meta/status` with the new `log` and `updatedAt`, pinned with
   `if_version`. Change `current` / `next` in the same write when they moved.

One line per event, in plain words a reader outside the session understands
("Merged PR #57: rate limit on sign-in"), with no local paths or secrets.

### progress recount

Recount instead of adjusting: run the measurement, then overwrite `meta/progress`
with what it found and `measuredAt` from `date -u`. Pick one basis per project,
write it in `basis`, and keep it.

- **Routes declared vs served** (a port or rewrite): count the routes the old
  system declares per area (`total`) and the ones the new system serves and passes
  tests for (`done`). `unit`: `"legacy routes ported"`.
- **Issues or stories closed** (feature work): count the issues or stories in scope
  per area (`total`) and the closed ones whose work is merged (`done`), for example
  with `gh issue list --label <area> --state all --json number,state`. `unit`:
  `"stories done"`.

`areas` give the per-area meters and the headline (`{pct}% of {unit} (done of
total)`; without a `unit` it reads `{pct}% complete`). `components` are the chips
under the meters; `milestones` are the left-pane list, each linked to its issue.
Set each milestone and component status (`done`, `active` or `todo`) from what the
code and the real state show (hard rule 3).

### rebuild after an account change

An artifact belongs to the account that published it. After an account change the
old artifact and its database become unreadable, so the board is rebuilt:

1. If the old board is still readable, dump it first: `list` `items` and `get`
   `meta/config`, `meta/status` and `meta/progress`, and save the result as JSON in
   the session scratchpad.
2. Republish `template.html` from the new account, exactly as in **create**.
3. Reseed from the dump. With no dump, rebuild from GitHub: open issues become
   `queued` or `backlog` items, merged PRs become `done` items with `updatedAt` =
   `mergedAt`, then run a fresh progress recount. Do not invent past log entries:
   start the log with one line saying the board was rebuilt and from what.
4. Replace the old URL in the project's memory or notes.

### sharing

The artifact is private to its owner when published. Only the owner can share it,
from the page's Share menu on claude.ai; Claude cannot share it. Tell the user so
when they ask who can see the board. Viewers can read; only the owner and Editors
can write (`write: "admin"` in the rules).

## Report

After any action, report the artifact URL, the docs written (paths), and for a
recount the new headline and `basis`.
