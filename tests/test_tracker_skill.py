"""Checks for the tracker skill (stdlib unittest).

The tracker page is published unchanged for every project, so it must carry no
project data, load nothing but Google Fonts, and read exactly the documents
reference.md describes. The skill's frontmatter must parse and name the skill.

Run: python3 -m unittest discover -s tests -v
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "tracker"

# Strings from the project the page was generalised from; none may survive.
PROJECT_STRINGS = re.compile(r"zim|zerion|tonic|laravel", re.IGNORECASE)
LOCAL_PATH = re.compile(r"(?<![\w$}])/(Users|private/tmp|home|tmp)/")
URL = re.compile(r"https?://[^\s\"'<>)`]+")
ALLOWED_HOSTS = {"fonts.googleapis.com", "fonts.gstatic.com"}
# Every document the page reads, and how the page reads it.
DATA_PATHS = {"items": 'db.collection("items")', "meta/status": 'db.doc("meta/status")',
              "meta/progress": 'db.doc("meta/progress")', "meta/config": 'db.doc("meta/config")'}
TRIGGERS = ("tracker", "progress board", "track this project")


def parse_frontmatter(text: str, label: str) -> tuple[dict[str, str], list[str]]:
    """Minimal frontmatter reader: `key: value` and folded `key: >` blocks."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, [f"{label}:1: no opening '---'"]
    fields: dict[str, str] = {}
    key = None
    for lineno, line in enumerate(lines[1:], 2):
        if line.strip() == "---":
            return {k: v.strip() for k, v in fields.items()}, []
        if line.startswith((" ", "\t")) and key is not None:
            fields[key] += " " + line.strip()
            continue
        m = re.match(r"^([a-z][a-z-]*):\s*(.*)$", line)
        if not m:
            return {}, [f"{label}:{lineno}: unparseable frontmatter line {line!r}"]
        key, value = m.group(1), m.group(2)
        fields[key] = "" if value in (">", "|") else value.strip("\"'")
    return {}, [f"{label}:1: no closing '---'"]


def check_frontmatter(text: str, label: str) -> list[str]:
    fields, problems = parse_frontmatter(text, label)
    if problems:
        return problems
    if fields.get("name") != "tracker":
        problems.append(f"{label}: frontmatter name is {fields.get('name')!r}; expected 'tracker'")
    description = fields.get("description", "").lower()
    problems += [f"{label}: description does not mention {t!r}" for t in TRIGGERS
                 if t not in description]
    return problems


def check_no_project_strings(text: str, label: str) -> list[str]:
    return [f"{label}: project-specific string {m.group(0)!r} at offset {m.start()}"
            for m in PROJECT_STRINGS.finditer(text)]


def check_no_local_paths(text: str, label: str) -> list[str]:
    return [f"{label}: absolute local path at offset {m.start()}"
            for m in LOCAL_PATH.finditer(text)]


def check_external_hosts(text: str, label: str) -> list[str]:
    return [f"{label}: external resource {m.group(0)!r}; only Google Fonts is allowed"
            for m in URL.finditer(text) if urlparse(m.group(0)).hostname not in ALLOWED_HOSTS]


def check_data_paths(template: str, reference: str) -> list[str]:
    problems = [f"template.html: never reads {path} ({call})"
                for path, call in DATA_PATHS.items() if call not in template]
    problems += [f"reference.md: no section for {path}" for path in DATA_PATHS
                 if not re.search(rf"^## `{re.escape(path)}(/<id>)?`", reference, re.MULTILINE)]
    return problems


class TrackerSkillTests(unittest.TestCase):
    def assertNoProblems(self, problems: list[str]) -> None:
        if problems:
            self.fail("\n" + "\n".join(problems))

    def read(self, name: str) -> str:
        return (SKILL_DIR / name).read_text(encoding="utf-8")

    def test_frontmatter_parses(self) -> None:
        self.assertNoProblems(check_frontmatter(self.read("SKILL.md"), "skills/tracker/SKILL.md"))

    def test_template_has_no_project_data(self) -> None:
        self.assertNoProblems(check_no_project_strings(self.read("template.html"), "template.html"))

    def test_template_loads_only_google_fonts(self) -> None:
        self.assertNoProblems(check_external_hosts(self.read("template.html"), "template.html"))

    def test_no_local_paths(self) -> None:
        problems: list[str] = []
        for path in sorted(SKILL_DIR.iterdir()):
            problems += check_no_local_paths(path.read_text(encoding="utf-8"), path.name)
        self.assertNoProblems(problems)

    def test_template_reads_documented_paths(self) -> None:
        self.assertNoProblems(check_data_paths(self.read("template.html"), self.read("reference.md")))


class TrackerCheckMutationTests(unittest.TestCase):
    """Every check reports injected drift."""

    def test_frontmatter_drift(self) -> None:
        good = "---\nname: tracker\ndescription: >\n  A tracker or progress board;\n  track this project.\n---\n"
        self.assertEqual(check_frontmatter(good, "s"), [])
        self.assertTrue(check_frontmatter(good.replace("name: tracker", "name: board"), "s"))
        self.assertTrue(check_frontmatter(good.replace("progress board", "board"), "s"))
        self.assertTrue(check_frontmatter("name: tracker\n", "s"))
        self.assertTrue(check_frontmatter("---\nname: tracker\n", "s"))

    def test_project_string_drift(self) -> None:
        self.assertTrue(check_no_project_strings("<h1>ZIM Port Tracker</h1>", "t"))
        self.assertTrue(check_no_project_strings("github.com/ZerionSoftware/x", "t"))

    def test_local_path_drift(self) -> None:
        self.assertTrue(check_no_local_paths("copy to " + "/private" + "/tmp/x/scratchpad", "t"))
        self.assertTrue(check_no_local_paths("see " + "/Users" + "/someone/repo", "t"))
        self.assertEqual(check_no_local_paths("${CLAUDE_PLUGIN_ROOT}/skills/tracker", "t"), [])

    def test_external_host_drift(self) -> None:
        self.assertEqual(check_external_hosts('href="https://fonts.googleapis.com/css2"', "t"), [])
        self.assertTrue(check_external_hosts('<script src="https://cdn.example.com/x.js">', "t"))

    def test_data_path_drift(self) -> None:
        template = " ".join(DATA_PATHS.values())
        reference = "## `items/<id>`\n## `meta/status`\n## `meta/progress`\n## `meta/config`\n"
        self.assertEqual(check_data_paths(template, reference), [])
        self.assertTrue(check_data_paths(template.replace('"meta/config"', '"meta/cfg"'), reference))
        self.assertTrue(check_data_paths(template, reference.replace("## `meta/config`\n", "")))


if __name__ == "__main__":
    unittest.main()
