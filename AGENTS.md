# Instructions for agents working on mailmd

mailmd converts exported Outlook emails (`.eml`) into clean Markdown for AI chats and project files. It is built
almost entirely by AI agents, so this file is the project's memory: read it before changing anything.

## The rule that matters most: no real email details, anywhere

This repository is **public**. Its subject, real work email, is exactly what must never appear in it.

- **Never put real names, email addresses, domains, company names, subject lines or message text** in code,
  comments, tests, fixtures, docs, commit messages, branch names, issues, PR descriptions or review comments.
- Use made-up examples: people like Alice Smith, Bob Jones and Carol Lee; companies like Acme, Globex and Initech;
  addresses on `example.com`, `example.org` or `example.co.jp`.
- **`samples/` holds real exports.** It is git-ignored and exists only on the maintainer's machine (or in a session
  where they shared files). Read samples to understand a pattern. Never copy from them.
- **Write fixtures from scratch.** Never create a fixture by copying a real export and replacing names: something
  always survives (a phone number in a signature, a name in a `References` header, a domain inside a link-scanner
  URL). A fixture should be the smallest synthetic email that shows the pattern being tested.
- When describing a real case in an issue or PR, describe its **structure** with made-up content ("Bob's questions,
  with Alice's answers inserted under each one"), never its content.
- `tools/leakcheck.py` runs as prek pre-commit and commit-msg hooks. It catches some mistakes, not all: it can't see
  GitHub issue, PR or comment text, and its deny-list (`.leakcheck.local`) is only present where the maintainer put
  it. Passing the hook does not make text safe.

If a task seems to require real details (for example, reproducing a bug from a sample), describe the pattern and
build a synthetic reproduction instead. If that isn't possible, stop and ask.

## Commands

Routine commands are recipes in the `justfile`. If `just` isn't installed in your environment, run it with
`uvx --from rust-just just <recipe>`.

| Recipe | Runs |
|---|---|
| `just sync` | `uv sync` |
| `just check` | `lint`, `types`, `test` and `leakcheck` below. **Must pass before pushing.** |
| `just test [ARGS]` | `uv run pytest ARGS` |
| `just lint` | `uv run ruff check .` and `uv run ruff format --check .` |
| `just fmt` | `uv run ruff check --fix .` and `uv run ruff format .` |
| `just types` | `uv run ty check src tools` |
| `just leakcheck` | `git ls-files -z \| xargs -0 uv run python tools/leakcheck.py` |
| `just hooks` | `uvx prek install` (once per clone: leakcheck hooks) |
| `just convert ARGS` | `uv run mailmd convert ARGS` |

Recipes use bash syntax; on Windows the `justfile` runs them in Git Bash.

## Layout

```
src/mailmd/
  cli.py      Typer CLI; `mailmd convert`
  convert.py  plan() decides every name and path without touching disk; write() creates the thread folder
  parse.py    reads the .eml; splits Outlook's From/Sent/To/Subject blocks into messages; finds attachments
  clean.py    removes noise: image placeholders, mailto duplicates, link-scanner wrappers, repeated paragraphs
  render.py   Markdown with YAML front matter
  naming.py   folder/file naming rules, kept as named constants at the top of the file
  model.py    Message, Attachment, Thread
tools/leakcheck.py   the commit guard
justfile             routine commands (see Commands)
tests/               pytest; tests/fixtures/ holds synthetic .eml files, optionally in per-case subfolders
samples/             real exports, git-ignored, never committed or copied from
```

Design decisions to preserve:

- **Plan, then write.** `convert.plan()` reads the input and decides every path first; `write()` only executes the
  plan. This is what makes `--force` safe when the input is the folder's own `source.eml`, and what lets the CLI
  reject over-long paths and same-name collisions before anything is written.
- **No written path exceeds 250 characters.** Generated names shrink to fit; user-supplied `--name` values are never
  rewritten, only rejected.
- **A quoted copy is evidence, not a faithful copy.** Quoted history inside a reply may have been edited (answers
  inserted inline) and its headers are reformatted by the replier's client. Never discard or trust it blindly.
- Output layout: one folder per thread holding `<folder>.md`, `attachments/` and `source.eml`.

## Tests

- Every test has a `# Promise:` comment stating, in plain English, the behavior it pins. A test that can't earn an
  honest Promise doesn't belong.
- Test behavior through public functions and the CLI (`typer.testing.CliRunner`), not private helpers, unless the
  helper is the unit under test (as with naming rules).
- Fixtures: synthetic `.eml` files in `tests/fixtures/`, written with CRLF line endings (`.gitattributes` keeps them
  byte-exact). Group fixtures for one case in a subfolder, e.g. `tests/fixtures/branches/`.

## Workflow

- **Issues are the specs.** Work from an issue; if the scope changes while working, update the issue text first so
  it stays an accurate record.
- **Branches:** `feat/...` for features, `fix/...` for bugs, `docs/...` for documentation.
- **Commits:** plain, descriptive English summaries (not Conventional Commits), with a body that explains why,
  what was decided, and how it was verified. Commit in logical steps, and make sure tests pass at every commit.
- **Pull requests:** say which issue they close (`Closes #N`), list the decisions made and the alternatives
  considered, and say how the change was verified. Record changes made during review in the PR description.
- **Merging:** merge commits, not squash, so the individual commits stay in `main`'s history.
- Ruff line length is 120; target Python 3.13.
