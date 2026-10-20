import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import debt_ratchet as dr  # noqa: E402

UPSTREAM_GREP = ["git", "grep", "--no-index", "--exclude-standard", "-nE", "(#|//|/[*]) ?(shortcut|ponytail):"]

FILES = {
    ".gitignore": "build/\n",
    "build/out.js": "// shortcut: generated, ignored by .gitignore\n",
    "app.py": (
        "import re\n"
        "# shortcut: regex, not a parser; nested definitions are missed. Use tree-sitter if it matters.\n"
        "DEF = re.compile(r'def (\\w+)')\n"
        "total = sum(rows)  # shortcut: whole file in memory\n"
        "# ponytail: flat frontmatter only, the shape every shipped SKILL.md uses. A\n"
        "# nested key would need a real YAML parser; switch when one appears.\n"
        "x = 1\n"
        "# keyboard shortcut: ctrl+k opens search\n"
    ),
    "web/app.js": "/* shortcut: polling every 5 s; move to SSE when the server supports it */\nsetInterval(poll, 5000)\n",
}


def make_repo(files=FILES):
    d = Path(tempfile.mkdtemp())
    for name, text in files.items():
        (d / name).parent.mkdir(parents=True, exist_ok=True)
        (d / name).write_text(text, encoding="utf-8", newline="\n")
    return d


class ScanMatchesPonytailDebt(unittest.TestCase):
    def setUp(self):
        self.repo = make_repo()

    def tearDown(self):
        shutil.rmtree(self.repo, ignore_errors=True)

    def test_same_hits_as_the_documented_git_grep(self):
        out = subprocess.run(UPSTREAM_GREP, cwd=self.repo, capture_output=True, text=True).stdout
        want = sorted(":".join(l.split(":", 2)[:2]) for l in out.splitlines())
        got = sorted(f"{m['file']}:{m['line']}" for m in dr.scan(self.repo))
        self.assertEqual(got, want)
        self.assertNotIn("build/out.js", " ".join(got))

    def test_ceiling_upgrade_and_no_trigger(self):
        by_line = {(m["file"], m["line"]): m for m in dr.scan(self.repo)}
        regex = by_line[("app.py", 2)]
        self.assertEqual(regex["ceiling"], "regex, not a parser; nested definitions are missed")
        self.assertEqual(regex["upgrade"], "Use tree-sitter if it matters.")
        self.assertEqual(regex["what"], "DEF = re.compile(r'def (\\w+)')")
        memory = by_line[("app.py", 4)]
        self.assertEqual(memory["what"], "total = sum(rows)")
        self.assertEqual(memory["upgrade"], "")
        self.assertIn("switch when one appears", by_line[("app.py", 5)]["upgrade"])  # continuation line read
        self.assertEqual(by_line[("web/app.js", 1)]["upgrade"], "move to SSE when the server supports it")

    def test_ledger_text(self):
        text = dr.ledger(dr.scan(self.repo))
        self.assertIn("app.py:4, total = sum(rows). ceiling: whole file in memory. upgrade: -. no-trigger", text)
        self.assertTrue(text.rstrip().endswith("4 markers, 1 with no trigger."))
        self.assertEqual(dr.ledger([]), "No shortcut debt. Clean ledger.")

    def test_marker_inside_a_string_literal_is_not_debt(self):
        repo = make_repo({"t.js": "cases = ['// shortcut: hash marker', true]\nx = 1 // shortcut: real one\n"})
        try:
            self.assertEqual([m["line"] for m in dr.scan(repo)], [2])
        finally:
            shutil.rmtree(repo, ignore_errors=True)

    def test_custom_marker_word(self):
        repo = make_repo({"a.py": "# TODO: cache this, when traffic grows\n# shortcut: x\n"})
        try:
            self.assertEqual([m["line"] for m in dr.scan(repo, word="TODO")], [1])
        finally:
            shutil.rmtree(repo, ignore_errors=True)


class KeysMatchJobKey(unittest.TestCase):
    def test_make_key_parity(self):
        cases = json.loads((ROOT / "tests" / "fixtures" / "job_key_parity.json").read_text(encoding="utf-8"))
        for company, title, url, want in cases:
            self.assertEqual(dr.make_key(company, title, url), want, (company, title))

    def test_key_survives_line_moves(self):
        a, b = make_repo(), make_repo({**FILES, "app.py": "\n\n\n" + FILES["app.py"]})
        try:
            self.assertEqual({m["key"] for m in dr.scan(a)}, {m["key"] for m in dr.scan(b)})
        finally:
            shutil.rmtree(a, ignore_errors=True), shutil.rmtree(b, ignore_errors=True)


class Ratchet(unittest.TestCase):
    def test_new_untriggered_marker_fails_old_one_passes(self):
        repo = make_repo()
        try:
            base = repo / ".debt-ledger.json"
            self.assertEqual(dr.main(["save", str(repo), "--baseline", str(base)]), 0)
            self.assertEqual(dr.main(["check", str(repo), "--baseline", str(base)]), 0)
            (repo / "new.py").write_text("y = 2  # shortcut: hardcoded rate\n", encoding="utf-8")
            self.assertEqual(dr.main(["check", str(repo), "--baseline", str(base)]), 1)
            (repo / "new.py").write_text("y = 2  # shortcut: hardcoded rate, read it from config when a second region ships\n", encoding="utf-8")
            self.assertEqual(dr.main(["check", str(repo), "--baseline", str(base)]), 0)
        finally:
            shutil.rmtree(repo, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
