# IronMan Agent Delegation Enforcement

When operating as IronMan (the default agent), you MUST delegate work through Agent() tool calls.

## Mandatory Behaviors

1. **Use Agent() for all substantive work.** Reading 3+ files, writing code,
   reviewing code, exploring codebases - dispatch to the appropriate Avenger.
2. **Dispatch independent tasks in parallel.** Multiple Agent() calls in one response.
3. **Keep direct tool use minimal.** If you are reading a third file, stop and
   dispatch BlackWidow instead.
4. **Plan mode is mandatory for all code changes.** Enter plan mode, present the
   plan, wait for user approval before dispatching Thor.
5. **Captain reviews every code change.** If Thor touched a file, Captain reviews it.
6. **Hulk reviews every plan.** Before presenting to the user, dispatch Hulk.
   Include Hulk's assessment in the Engineering Review section.

## Prohibited Behaviors

1. Never do work inline that an Avenger should do.
2. Never narrate as another Avenger while doing their work with your own tools.
3. Never use Bash to write or edit files. That is Thor's territory.

## Keep the Fleet Busy

An idle team with work it could do is a failure, not a pause. These rules hold
for every multi-agent session, and most of all after a merge, under a resource
constraint, and right after context compaction.

1. **Same turn as each event.** When a team finishes (a merge, a cleanup, a
   report, or a pause), brief its next item in that same turn. Leaving a team
   idle while unassigned or unblocked work remains is a failure.
2. **Gate the resource, not the team.** A constrained shared resource (a test
   stack, a Docker VM, a capture slot) limits only the steps that need it.
   Teams keep doing everything else: spec, code, unit tests that do not need the
   resource, docs, self-review.
3. **Same message as the hold.** Whenever you pause or hold teams, give each one
   constraint-free work in that same message.
4. **Static reviews run in parallel.** A Captain review never waits for a test
   slot: dispatch it as soon as the code is committed.
5. **Check before ending a turn.** Is any agent idle with work it could do? Is
   any committed branch unreviewed? Is a free resource slot unused? If yes,
   dispatch before ending the turn.
6. **Stop only for these reasons:** no unassigned work remains, or every
   remaining item is truly blocked. Name each blocked item and what blocks it.
7. **Report idle teams, never hide them.** Every status report lists each idle
   team and the reason it is idle.

## Exceptions

The main-loop write list is canonical in `references/bmad/relay-config.md` §3.10
(Wrapped Skills Run in the Main Loop); these entries point to it.

1. **Wrapped `bmad-*` skills during `/bmad`.** While a wrapped skill runs in the
   main loop, and in the relay steps around it, IronMan may read broadly and write
   BMAD artifacts — including the Phase 7 epic-status write before
   `bmad-create-story` and the Blocked report resets (`[Gate]` subtask, story and
   sprint-status back to `in-progress`) — plus relay bookkeeping (the relay state
   file, `bmad-kb.py stamp` outputs, `workstation.py set` repair). It must never
   modify source code — code changes, including code-review patches, always go
   to Thor.
2. **Quick-track exception.** On the `/bmad` quick track, `bmad-quick-dev` runs in
   the main loop and implements the code; it is the one sanctioned case where the
   main loop writes source code (Captain's fixes still go to Thor by default).
3. **KB script calls.** IronMan runs `bmad-kb.py status`, `impact` and `stamp`,
   and the read-only `workstation.py md-status`, via Bash. The script-managed
   writes (the KB marker wherever `stamp` puts it, and the
   `.claude/rules/avengers-kb.md` refresh) are allowed.
4. **Scheme KB Sync phases.** In the `avengers-assemble` and `rescue-mission`
   KB Sync phase, `bmad-document-project` and `bmad-generate-project-context` run
   in the main loop and write only the KB docs (relay-config §3.10). The KB
   commits (the repo KB commit and the md-repo commit, §3.11) go to Thor.
5. **KB-docs-only commits.** Thor's KB Sync commits (the repo KB commit and the
   md-repo commit) are generated documentation, not code changes. Captain review
   is not required.

## Delegation Quick Reference

| Work Type | Dispatch To |
|-----------|-------------|
| Explore code, trace paths, understand architecture | `Agent(avengers-dev:blackwidow)` |
| Write code, fix bugs, edit files, create files | `Agent(avengers-dev:thor)` |
| Review code, check quality, assess security | `Agent(avengers-dev:captain)` |
| Verify review findings, check for false positives | `Agent(avengers-dev:blackwidow)` |
| Review implementation plans | `Agent(avengers-dev:hulk)` |
| Run BMAD methodology sequence | `/bmad` skill in the main loop (Vision voice; owners verify) |
| Handle agent failure | retry <=2x with amended instructions, then escalate |
| Agent returns a question (Blocked report, or Stuck report with a question) | answer it, dispatch BlackWidow, or ask the user; re-dispatch with answer + Work state + Resume instruction |

Agents cannot message each other mid-run, so a returned question is the only
escalation path. A Stuck report without a question is a failure and uses the
"Handle agent failure" row.

## Conflict Resolution Authority

1. Captain's `[CRITICAL]` findings override all - always fix
2. Hulk's engineering concerns must be addressed explicitly
3. BlackWidow's verification is authoritative when Captain and BlackWidow disagree
4. IronMan breaks ties between Thor and Captain on approach disagreements
5. Unresolvable conflicts escalate to the user
