"""Tests for the paired-reviewer SendMessage guard (stdlib unittest).

The guard is the runtime enforcement of the Paired Reviewers rule in
`.claude/rules/ironman-delegation.md`: a PreToolUse hook on SendMessage that allows
`main` and the agentIds IronMan registered in `<project>/.avengers/pairs.json`,
and denies every other target. Covers:

1. `scripts/sendmessage-guard.sh` end to end, fed a hook payload on stdin: allowed
   targets exit 0, denied ones exit 2 with a reason on stderr.
2. Fail closed: no registry, an unreadable or malformed one, no
   CLAUDE_PROJECT_DIR, a bad payload, or a guard that cannot run leave only `main`
   (or nothing) allowed - never an exit other than 0 or 2.
3. `pair-registry.py register|unregister|list`, the commands IronMan runs.
4. The hook is wired in `hooks/hooks.json`.

Every subprocess gets HOME and CLAUDE_PROJECT_DIR pointed into a tmpdir.

Run: python3 -m unittest discover -s tests -v
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUARD_HOOK = ROOT / "scripts" / "sendmessage-guard.sh"
REGISTRY_SCRIPT = ROOT / "scripts" / "pair-registry.py"
HOOKS_JSON = ROOT / "hooks" / "hooks.json"
HOOK_COMMAND = "bash ${CLAUDE_PLUGIN_ROOT}/scripts/sendmessage-guard.sh"

THOR_ID = "a1b2c3d4e5f6-thor"
CAPTAIN_ID = "a9f8e7d6c5b4-captain"
ALLOW, DENY = 0, 2


def payload(to: object, tool: str = "SendMessage") -> str:
    return json.dumps({"session_id": "s", "hook_event_name": "PreToolUse",
                       "tool_name": tool,
                       "tool_input": {"to": to, "message": "round 1 review request"}})


class GuardFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.project = self.tmp / "project"
        self.project.mkdir()
        self.registry = self.project / ".avengers" / "pairs.json"

    def env(self, project_dir: Path | None = None, **extra: str) -> dict[str, str]:
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PROJECT_DIR"}
        env["HOME"] = str(self.tmp)
        if project_dir is not None:
            env["CLAUDE_PROJECT_DIR"] = str(project_dir)
        env.update(extra)
        return env

    def hook(self, stdin: str, project_dir: Path | None = None,
             env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
        return subprocess.run(["bash", str(GUARD_HOOK)], input=stdin, capture_output=True,
                              text=True, timeout=30, check=False, cwd=str(self.tmp),
                              env=env or self.env(project_dir or self.project))

    def registry_cmd(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(REGISTRY_SCRIPT), *args,
                               "--project-dir", str(self.project)],
                              capture_output=True, text=True, timeout=30, check=False,
                              cwd=str(self.tmp), env=self.env())

    def write_registry(self, data: object) -> None:
        self.registry.parent.mkdir(parents=True, exist_ok=True)
        self.registry.write_text(data if isinstance(data, str) else json.dumps(data))

    def register_pair(self) -> None:
        self.write_registry({"version": 1,
                             "pairs": {"team-a": {"thor": THOR_ID, "captain": CAPTAIN_ID}}})

    def assertDecision(self, proc: subprocess.CompletedProcess, code: int) -> None:
        self.assertEqual(proc.returncode, code, f"stderr:\n{proc.stderr}")
        if code == DENY:
            self.assertIn("SendMessage denied", proc.stderr)


class GuardDecisionTests(GuardFixture):
    def test_main_is_allowed(self) -> None:
        self.register_pair()
        self.assertDecision(self.hook(payload("main")), ALLOW)

    def test_registered_pair_ids_are_allowed(self) -> None:
        self.register_pair()
        for agent_id in (THOR_ID, CAPTAIN_ID):
            with self.subTest(to=agent_id):
                self.assertDecision(self.hook(payload(agent_id)), ALLOW)

    def test_unregistered_id_is_denied(self) -> None:
        self.register_pair()
        proc = self.hook(payload("a0000000-other"))
        self.assertDecision(proc, DENY)
        self.assertIn("not a paired agentId", proc.stderr)

    def test_session_and_agent_names_are_denied(self) -> None:
        self.register_pair()
        for name in ("worker", "researcher", "captain", "thor", "ironman", "Main"):
            with self.subTest(to=name):
                self.assertDecision(self.hook(payload(name)), DENY)

    def test_name_with_ref_is_denied(self) -> None:
        """`name [ref]` addresses another session, even when the name part is a
        registered id."""
        self.register_pair()
        for target in ("worker [3fa9c1]", f"{THOR_ID} [3fa9c1]", f"{THOR_ID}[x]",
                       "two words", f" {THOR_ID}", f"{THOR_ID}\n", "main [3fa9c1]"):
            with self.subTest(to=target):
                proc = self.hook(payload(target))
                self.assertDecision(proc, DENY)
                self.assertIn("whitespace or `[`", proc.stderr)

    def test_bad_targets_are_denied(self) -> None:
        self.register_pair()
        for target in ("", None, 42, [THOR_ID], {"id": THOR_ID}):
            with self.subTest(to=target):
                self.assertDecision(self.hook(payload(target)), DENY)

    def test_unparsable_payload_is_denied(self) -> None:
        self.register_pair()
        for stdin in ("", "not json", "[]", json.dumps({"tool_name": "SendMessage"})):
            with self.subTest(stdin=stdin):
                self.assertDecision(self.hook(stdin), DENY)

    def test_other_tools_pass_through(self) -> None:
        self.assertDecision(self.hook(payload("anything", tool="Bash")), ALLOW)


class GuardFailClosedTests(GuardFixture):
    def assertOnlyMain(self, env: dict[str, str] | None = None) -> None:
        self.assertDecision(self.hook(payload("main"), env=env), ALLOW)
        for target in (THOR_ID, CAPTAIN_ID, "worker"):
            with self.subTest(to=target):
                self.assertDecision(self.hook(payload(target), env=env), DENY)

    def test_no_registry_allows_only_main(self) -> None:
        self.assertFalse(self.registry.exists())
        self.assertOnlyMain()

    def test_malformed_registry_allows_only_main(self) -> None:
        cases = {
            "not json": "{",
            "wrong version": {"version": 2, "pairs": {"t": {"thor": THOR_ID}}},
            "pairs not an object": {"version": 1, "pairs": [THOR_ID]},
            "extra role": {"version": 1, "pairs": {"t": {"thor": THOR_ID, "hulk": "a1"}}},
            "id with a space": {"version": 1,
                                "pairs": {"t": {"thor": THOR_ID, "captain": "x [ref]"}}},
            "bad team name": {"version": 1, "pairs": {"a team": {"thor": THOR_ID}}},
            "top level list": [THOR_ID, CAPTAIN_ID],
        }
        for name, data in cases.items():
            with self.subTest(case=name):
                self.write_registry(data)
                self.assertOnlyMain()

    def test_unreadable_registry_allows_only_main(self) -> None:
        self.register_pair()
        self.registry.chmod(0)
        self.addCleanup(self.registry.chmod, 0o600)
        if os.access(self.registry, os.R_OK):
            self.skipTest("running as a user that can read a mode-000 file")
        self.assertOnlyMain()

    def test_registry_is_a_directory(self) -> None:
        self.registry.mkdir(parents=True)
        self.assertOnlyMain()

    def test_no_project_dir_allows_only_main(self) -> None:
        self.register_pair()
        self.assertOnlyMain(env=self.env(None))

    def test_guard_that_cannot_run_denies(self) -> None:
        """A crash or a missing interpreter is exit 2, never a non-blocking error."""
        self.register_pair()
        fake_bin = self.tmp / "bin"
        fake_bin.mkdir()
        broken = fake_bin / "python3"
        broken.write_text("#!/bin/sh\nexit 1\n")
        broken.chmod(0o755)
        env = self.env(self.project, PATH=f"{fake_bin}{os.pathsep}{os.environ['PATH']}")
        for target in ("main", THOR_ID):
            with self.subTest(to=target):
                proc = self.hook(payload(target), env=env)
                self.assertDecision(proc, DENY)
                self.assertIn("fails closed", proc.stderr)


class RegistryCommandTests(GuardFixture):
    def test_dispatch_order_registers_both_sides(self) -> None:
        """Captain first, then its Thor: each id is allowed once registered."""
        proc = self.registry_cmd("register", "--team", "team-a", "--captain", CAPTAIN_ID)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertDecision(self.hook(payload(CAPTAIN_ID)), ALLOW)
        self.assertDecision(self.hook(payload(THOR_ID)), DENY)
        proc = self.registry_cmd("register", "--team", "team-a", "--thor", THOR_ID)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["pairs"],
                         {"team-a": {"thor": THOR_ID, "captain": CAPTAIN_ID}})
        self.assertDecision(self.hook(payload(THOR_ID)), ALLOW)

    def test_unregister_revokes(self) -> None:
        self.register_pair()
        proc = self.registry_cmd("unregister", "--team", "team-a")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["pairs"], {})
        self.assertDecision(self.hook(payload(THOR_ID)), DENY)
        # Unregistering an absent team is a no-op, not an error.
        self.assertEqual(self.registry_cmd("unregister", "--team", "gone").returncode, 0)

    def test_register_rejects_bad_input(self) -> None:
        for args in (("--team", "team-a"),
                     ("--team", "team-a", "--thor", "worker [3fa9c1]"),
                     ("--team", "a team", "--thor", THOR_ID)):
            with self.subTest(args=args):
                self.assertNotEqual(self.registry_cmd("register", *args).returncode, 0)
        self.assertFalse(self.registry.exists())

    def test_an_id_belongs_to_one_team(self) -> None:
        self.register_pair()
        proc = self.registry_cmd("register", "--team", "team-b", "--thor", THOR_ID)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("already registered to team team-a", proc.stderr)

    def test_register_refuses_a_malformed_registry(self) -> None:
        self.write_registry("{")
        proc = self.registry_cmd("register", "--team", "team-a", "--thor", THOR_ID)
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(self.registry.read_text(), "{")

    def test_list_and_help(self) -> None:
        proc = self.registry_cmd("list")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout), {"version": 1, "pairs": {}})
        proc = subprocess.run([sys.executable, str(REGISTRY_SCRIPT), "--help"],
                              capture_output=True, text=True, timeout=30, check=False)
        self.assertEqual(proc.returncode, 0)
        self.assertIn("guard", proc.stdout)


class HookWiringTests(unittest.TestCase):
    def test_pretooluse_hook_guards_sendmessage(self) -> None:
        hooks = json.loads(HOOKS_JSON.read_text())["hooks"]["PreToolUse"]
        commands = [h["command"] for entry in hooks if entry.get("matcher") == "SendMessage"
                    for h in entry["hooks"]]
        self.assertEqual(commands, [HOOK_COMMAND])

    def test_hook_scripts_are_executable(self) -> None:
        for script in (GUARD_HOOK, REGISTRY_SCRIPT):
            with self.subTest(script=script.name):
                self.assertTrue(os.access(script, os.X_OK))


if __name__ == "__main__":
    unittest.main()
