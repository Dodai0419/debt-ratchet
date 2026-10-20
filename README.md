<div align="center">

# debt-ratchet

**Turn every `shortcut:` comment into a debt ledger, and fail CI only when new debt names no way out.**

[ponytail](https://github.com/DietrichGebert/ponytail) makes agents write `# shortcut: <ceiling>, <upgrade path>` comments, and its `/ponytail-debt` skill asks the model to collect them. debt-ratchet collects them with no model: same scan, same ledger, keys that survive moved lines, and a CI gate.

Works with **Claude Code** and **Codex**.

![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg) ![Status: prototype](https://img.shields.io/badge/status-prototype-orange.svg)

</div>

## Quick start
```bash
git clone https://github.com/Dodai0419/debt-ratchet && cd debt-ratchet
python debt_ratchet.py ledger examples/demo
```
```
billing.py:3, RATE = 0.19. ceiling: one VAT rate for every country. upgrade: read it per country when we sell outside Germany.
billing.py:7, return json.load(open(path, encoding="utf-8")). ceiling: whole file in memory. upgrade: -. no-trigger
poll.js:1, setInterval(() => fetch("/status").then(r => r.json()).then(render), 5000);. ceiling: polling every 5 s. upgrade: move to SSE when the server supports it.
poll.js:4, const fmt = new Intl.NumberFormat("en-US", { style: "currency", currency: "EUR" . ceiling: Intl.NumberFormat does this. upgrade: -. no-trigger

4 markers, 2 with no trigger.
```

## The problem
- Lazy-by-design agents leave `shortcut:` comments everywhere; a deferral nobody lists quietly becomes permanent.
- Asking a model for the ledger costs tokens on every run and the wording changes each time, so it cannot gate a pull request.
- Line numbers move on every edit, so "is this debt new?" needs a key that is not the line number.

## The solution
| Idea | Fixes |
|------|-------|
| **ponytail-debt's own scan** (`git grep --no-index --exclude-standard`, same pattern, same row format, same `no-trigger` tag and summary line) | Same ledger as the skill, from a plain CLI |
| **Stable keys from ai-job-search's `make_key`** (file slug + ceiling slug, length-capped with a hash) | Moving code does not create "new" debt; two different shortcuts never share a key |
| **`save` + `check` ratchet** | Old debt is accepted once; CI fails only on *new* markers with no upgrade trigger, and lists debt that was paid off |

```bash
python debt_ratchet.py save . --baseline .debt-ledger.json     # commit this file
python debt_ratchet.py check . --baseline .debt-ledger.json    # in CI: exit 1 on new untriggered debt
python debt_ratchet.py ledger . --word "TODO|FIXME"            # any marker words
python debt_ratchet.py ledger . --json                         # file, line, what, ceiling, upgrade, key
```

GitHub Actions step:
```yaml
- run: python debt_ratchet.py check . --baseline .debt-ledger.json
```

## Use with Claude Code
```bash
/plugin marketplace add Dodai0419/debt-ratchet
/plugin install debt-ratchet@debt-ratchet
```

## Use with Codex (ChatGPT)
```bash
git clone https://github.com/Dodai0419/debt-ratchet && cp -r debt-ratchet/skills/* ~/.codex/skills/
```
Or copy `AGENTS.md` to your project root.

## Benchmarks
Input: the ponytail repo itself (commit `09c434a`). Windows 11, Python 3.11.1, git 2.55, median of 7 process runs: `python bench/bench.py <ponytail checkout>`.

| | original | this repo |
|-|-|-|
| find the markers | 173 ms (`git grep` step of ponytail-debt) | same command, inside `ledger` |
| full ledger with ceiling / upgrade / no-trigger | not measured (the skill hands the grep output to the model) | 507 ms, 0 tokens |
| CI gate on new debt | not available | `check`, exit 0/1 |
| lines of code | 44 (ponytail-debt SKILL.md) + 251 (job_key.py) | 162 |
| dependencies | an LLM session | Python stdlib + git |

Parity (unit tests, `python -m unittest -q`):
- The markers found equal the hits of ponytail-debt's documented `git grep` command on a fixture tree (with a `.gitignore`d file excluded). One deliberate difference: a marker inside a string literal (`'// shortcut: ...'` in a test table) is skipped, as the skill tells the model to skip hits that are not a deferral. On the ponytail repo this skips 9 such lines in `tests/commands.test.js` (55 grep hits, 46 ledger rows).
- `make_key` returns the same key as ai-job-search's `tools/job_key.py` (commit `0f6480d`) for 14 inputs, including truncation, Cyrillic, Danish and ligature cases.

The trigger check is a word list (when, if, once, until, use, switch, move, replace, upgrade, lift, tune, pass...), not a model's judgment: a ceiling worded as "X does this" reads as `no-trigger`.

## Inspired by
- [DietrichGebert/ponytail](https://github.com/DietrichGebert/ponytail): the `shortcut:` convention and the `/ponytail-debt` ledger.
- [MadsLorentzen/ai-job-search](https://github.com/MadsLorentzen/ai-job-search): `make_key`, the deterministic, collision-safe dedup key for job postings, reused here for debt markers.

## Roadmap
- [ ] `git blame` owner and age per row (`--blame`)
- [ ] SARIF output so GitHub shows new debt inline on the pull request

## License
MIT. See `NOTICE` for the ported parts.
