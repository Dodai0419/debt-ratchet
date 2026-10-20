# AGENTS.md: debt-ratchet

Use debt-ratchet when someone asks what shortcuts or deferred work the code carries ("ponytail debt", "list the shortcuts", "what did we defer"), wants the debt ledger written to a file, or wants CI to stop new `shortcut:` comments that name no upgrade trigger. Run the CLI instead of grepping and summarizing by hand: it gives the same ledger in well under a second and no tokens.

## Commands (run from the repo root; Python 3.9+ and git, no other dependencies)

```bash
python debt_ratchet.py ledger /path/to/repo                 # one row per marker + "N markers, M with no trigger."
python debt_ratchet.py ledger /path/to/repo --word "TODO|FIXME"   # your own marker words
python debt_ratchet.py ledger /path/to/repo --json          # file, line, what, ceiling, upgrade, stable key
python debt_ratchet.py save /path/to/repo --baseline .debt-ledger.json    # accept today's debt
python debt_ratchet.py check /path/to/repo --baseline .debt-ledger.json   # exit 1 only for NEW markers with no trigger
```

Row format: `<file>:<line>, <code the marker sits on>. ceiling: <the limit named>. upgrade: <the trigger>.` Rows with no trigger end in `no-trigger`.

## Rules
- Marker convention: `# shortcut: <ceiling>, <upgrade path>` (also `//` and `/*`; older code may say `ponytail:`). A trigger is a clause with when/if/once/until/use/switch/move/replace/upgrade/lift/tune/pass.
- Files ignored by `.gitignore` are skipped; markers inside string literals are skipped.
- Keys come from file + ceiling text, not line numbers, so moving code does not create "new" debt. Editing the ceiling text does.
- Reads and reports only. `save` writes only the baseline file you name.
