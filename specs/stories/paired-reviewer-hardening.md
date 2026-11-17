# Paired reviewers: enforce the recipient, tie the ship gate to the reviewed commit

## Objective
The paired-reviewer protocol (a Thor and its own Captain running the
build-review-fix loop with `SendMessage`) was enforced only by documentation and a
text check. Harden it: enforce the message recipient at runtime, treat findings as
claims rather than commands, tie the ship gate to the reviewed sha, keep the Fleet
rules from disturbing a pair mid-loop, state the dispatch mechanism and its
fallback, exclude the `/bmad` and `/sdd` relays, and reconcile the persona's
Quality Gate and Closure Loop with the paired loop.

## Scope

**Files to Create/Modify**
- `scripts/pair-registry.py` — the project-local pair registry (`.avengers/pairs.json`: `register`, `unregister`, `list`) and the `guard` decision
- `scripts/sendmessage-guard.sh` — PreToolUse hook entry; turns every outcome but an explicit allow into exit 2
- `hooks/hooks.json` — `PreToolUse` hook on `SendMessage`
- `.claude/rules/ironman-delegation.md` — Paired Reviewers rewritten (dispatch order and registry, verdict copy with range and finding list, ship gate tied to the sha, claims not commands, guard and forbidden targets, pair messages as agent output, resume-by-message fallback, relay exclusion); Keep the Fleet Busy item 8; Exceptions item 6 (registry calls)
- `agents/thor.md`, `agents/captain.md` — When Paired updated to match
- `personas/ironman.md` — pairing pointer, Fleet exemption, Quality Gate and Closure Loop reconciled
- `scripts/compact-resume.sh` — the Fleet exemption in the post-compaction reminder
- `tests/test_sendmessage_guard.py` — hook unit tests
- `tests/test_doc_consistency.py` — tightened messaging checker
- `README.md`, `TESTING.md`, `.github/workflows/tests.yml` — hook docs, test docs, byte-compile `scripts`

## Design & Structure
- **Guard.** `sendmessage-guard.sh` runs `pair-registry.py guard`, which reads the hook payload on stdin. Allowed: `to` exactly `main`, or an agentId in a valid registry under `CLAUDE_PROJECT_DIR`. Denied, exit 2 with the reason on stderr: everything else, including other sessions, names, `name [ref]` targets, unregistered ids, and any target with whitespace or `[`.
- **Fail closed.** A missing, unreadable or malformed registry, or an unset `CLAUDE_PROJECT_DIR`, leaves only `main`. An unparsable payload is denied. Claude Code treats any exit other than 0 and 2 as non-blocking, so the shell entry maps a crash or a missing `python3` to exit 2.
- **Registry.** `{"version": 1, "pairs": {"<team>": {"thor": "<id>", "captain": "<id>"}}}`, written atomically. An agentId belongs to one team. IronMan registers each id as it gets it and unregisters the team when the loop ends.

## Mechanism and open item
- **Relied on:** resume-by-message. Each side ends its run after sending, and the partner's message resumes it. This supersedes, for paired builder teams only, the "no SendMessage path" note in `agent-escalation-path.md`.
- **Open item:** verify resume-by-message end to end (a finished subagent resumed by a `SendMessage` from its partner, and from `main`) on the Claude Code versions the plugin supports.
- **Fallback:** if a Captain run ends with no verdict copy to `main` for the round, or a partner never resumes, IronMan unregisters the pair and runs the review loop by re-dispatch, as for an unpaired team.

## Acceptance Criteria
- [ ] The hook allows `main` and registered pair ids, and denies an unregistered id, a session name and `name [ref]`; with no registry only `main` is allowed; a guard that cannot run denies
- [ ] Paired sections are allowed only in the three protocol files and not inside code fences
- [ ] A messaging verb in a paired section must be followed by an allowed recipient
- [ ] Every agent has a frontmatter `tools:` line; the `tools:` skip applies to frontmatter only
- [ ] `python3 -m unittest discover -s tests` passes

## Status
- [ ] Spec approved by user (written from the operator's brief for this follow-up)
