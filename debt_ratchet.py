#!/usr/bin/env python3
"""debt-ratchet: the ponytail `shortcut:` debt ledger as a deterministic CLI, with a CI ratchet.

Scan rule and ledger format: DietrichGebert/ponytail skills/ponytail-debt (MIT).
Stable marker keys: MadsLorentzen/ai-job-search tools/job_key.py make_key (MIT).
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

TRIGGER = re.compile(r"\b(if|when|once|until|upgrade|use|switch|replace|move|lift|tune|re-?pick|pass|swap|add)\b", re.I)
CLAUSE = re.compile(r"(?<=[;,.])\s+")
COMMENT = re.compile(r"^\s*(#|//|/\*|\*)\s?")


# ---- make_key, ported from ai-job-search tools/job_key.py ----

COMPANY_MAX, TITLE_MAX, HASH_LEN = 40, 60, 6
_NON_SLUG = re.compile(r"[^a-z0-9]+")
_JOB_ID = re.compile(r"(\d{6,})")


def slugify(text):
    ascii_only = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode("ascii")
    return _NON_SLUG.sub("-", ascii_only.lower()).strip("-")


def _lost_letters(text):
    """True when the ASCII fold dropped non-Latin letters (Cyrillic, CJK...), so the slug under-identifies."""
    return any(ord(ch) >= 128 and ch.isalpha() and not unicodedata.name(ch, "LATIN").startswith("LATIN")
               for ch in unicodedata.normalize("NFKD", str(text or "")))


def _sha(s):
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:HASH_LEN]


def _cap(slug, limit):
    return slug if len(slug) <= limit else f"{slug[:limit].rstrip('-')}-{_sha(slug)}"


def make_key(company, title, url=""):
    company_slug = _cap(slugify(company), COMPANY_MAX)
    if not company_slug or _lost_letters(company):
        name = unicodedata.normalize("NFC", str(company or "").strip().casefold())
        if not name:
            company_slug = "unknown-company"
        else:
            company_slug = f"{company_slug}-{_sha(name)}" if company_slug else f"company-{_sha(name)}"
    title_slug = _cap(slugify(title), TITLE_MAX)
    if not title_slug or _lost_letters(title):
        fragment = title_slug
        match = _JOB_ID.search(url or "")
        if match:
            title_slug = f"{fragment}-{match.group(1)}" if fragment else match.group(1)
        else:
            basis = slugify(unicodedata.normalize("NFKD", str(title or url or "")))
            digest = _sha(str(url) if url else str(title))
            title_slug = f"{fragment}-{digest}" if fragment else (basis or f"untitled-{digest}")
    return f"{company_slug}_{title_slug}"


# ---- scan + ledger (ponytail-debt) ----

def _split(text):
    """`shortcut: <ceiling>, <upgrade path>` -> (ceiling, upgrade); upgrade '' when no trigger is named."""
    clauses = CLAUSE.split(text)
    for i, c in enumerate(clauses[1:], 1):
        if TRIGGER.search(c):
            return " ".join(clauses[:i]).rstrip(";,. "), " ".join(clauses[i:])
    return text.rstrip("."), "named in the ceiling" if TRIGGER.search(clauses[0]) else ""


def scan(root=".", word=None):
    words = word or "shortcut|ponytail"
    cmd = ["git", "grep", "--no-index", "--exclude-standard", "-z", "-nE", f"(#|//|/[*]) ?({words}):"]
    p = subprocess.run(cmd, cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode > 1:
        raise SystemExit(f"git grep failed: {p.stderr.strip()}")
    marker = re.compile(rf"(#|//|/[*]) ?({words}):\s*(.*)")
    files, out, seen = {}, [], {}
    for hit in p.stdout.splitlines():
        name, line_no, _ = hit.split("\0", 2)
        lines = files.setdefault(name, (Path(root) / name).read_text(encoding="utf-8", errors="replace").splitlines())
        i = int(line_no) - 1
        m = marker.search(lines[i])
        before = lines[i][:m.start()]
        if any(before.count(q) % 2 for q in "'\"`"):
            continue  # marker inside a string literal (a test fixture, a regex): not a deferral
        text = m.group(3).replace("*/", "").strip()
        before = before.strip()
        j = i + 1
        while j < len(lines) and j <= i + 3 and COMMENT.match(lines[j]) and not marker.search(lines[j]) and not before:
            text += " " + COMMENT.sub("", lines[j]).replace("*/", "").strip()  # comment continues on the next line
            j += 1
        what = before
        while not what and j < len(lines):
            what = lines[j].strip() if lines[j].strip() and not COMMENT.match(lines[j]) else ""
            j += 1
        ceiling, upgrade = _split(text.strip())
        key = make_key(name, ceiling)
        seen[key] = seen.get(key, 0) + 1
        out.append({"file": name, "line": i + 1, "what": what[:80], "ceiling": ceiling, "upgrade": upgrade,
                    "key": key if seen[key] == 1 else f"{key}-{seen[key]}"})
    return sorted(out, key=lambda m: (m["file"], m["line"]))


def ledger(markers):
    if not markers:
        return "No shortcut debt. Clean ledger."
    rows = [f"{m['file']}:{m['line']}, {m['what'] or '(end of file)'}. ceiling: {m['ceiling']}. "
            f"upgrade: {m['upgrade'].rstrip('.') or '-'}." + ("" if m["upgrade"] else " no-trigger") for m in markers]
    bare = sum(not m["upgrade"] for m in markers)
    return "\n".join(rows) + f"\n\n{len(markers)} markers, {bare} with no trigger."


# ---- CLI ----

def main(argv=None):
    for s in (sys.stdout, sys.stderr):
        getattr(s, "reconfigure", lambda **_: None)(encoding="utf-8")  # Windows pipes default to cp1252
    ap = argparse.ArgumentParser(prog="debt-ratchet", description=__doc__.splitlines()[0])
    ap.add_argument("cmd", choices=["ledger", "save", "check"], help="ledger: print; save: write baseline; check: CI gate")
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--word", help="marker word(s) instead of shortcut|ponytail, e.g. TODO or 'TODO|FIXME'")
    ap.add_argument("--baseline", default=".debt-ledger.json")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    markers = scan(args.root, args.word)

    if args.cmd == "ledger":
        print(json.dumps(markers, indent=1, ensure_ascii=False) if args.json else ledger(markers))
        return 0
    if args.cmd == "save":
        Path(args.baseline).write_text(json.dumps({m["key"]: m for m in markers}, indent=1, ensure_ascii=False) + "\n",
                                       encoding="utf-8")
        print(f"saved {len(markers)} markers to {args.baseline}")
        return 0
    try:
        base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"cannot read baseline {args.baseline}: {e}. Run `save` first.", file=sys.stderr)
        return 2
    now = {m["key"]: m for m in markers}
    new = [m for k, m in now.items() if k not in base]
    bad = [m for m in new if not m["upgrade"]]
    gone = [m for k, m in base.items() if k not in now]
    for m in new:
        print(f"+ {m['file']}:{m['line']} {m['ceiling']}" + ("  <- no upgrade trigger" if not m["upgrade"] else ""))
    for m in gone:
        print(f"- {m['file']} {m['ceiling']} (paid off)")
    print(f"{len(markers)} markers: {len(new)} new, {len(gone)} paid off, {len(bad)} new with no trigger.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
