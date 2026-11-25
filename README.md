# mailmd

Convert exported Outlook email threads (`.eml`) into clean Markdown, for pasting into AI chats or keeping next to
project files.

An Outlook reply carries the whole conversation as quoted text, wrapped in signatures, confidentiality notices,
link-scanner URLs and image placeholders. `mailmd` turns one exported message into a readable thread:

1. Splits the quoted history on Outlook's `From: / Sent: / To: / Subject:` header blocks
2. Drops noise: paragraphs repeated across messages (notices, signatures), inline-image placeholders,
   `<mailto:...>` duplicates, link-scanner wrappers and Outlook's hidden preview line
3. Orders the messages oldest first
4. Saves real attachments (not inline logos) to a folder next to the Markdown

## Install

```
uv tool install .      # or: just install
```

## Use

In new Outlook: right-click the newest message in the thread, then **Save as > Save as EML**.

```
mailmd convert ~/Downloads/RE_x.eml                                     # creates ./2026-11-16_x/
mailmd convert ~/Downloads/RE_x.eml -o notes/correspondence             # create it somewhere else
mailmd convert ~/Downloads/RE_x.eml --name acme-quote               # pick the folder name yourself
mailmd convert ~/Downloads/*.eml                                        # several files, one folder each
```

Each conversion creates one folder, in the current directory unless `-o` says otherwise:

```
2026-11-16_project-kickoff/
├── 2026-11-16_project-kickoff.md   Markdown with YAML front matter, one section per message
├── attachments/                    real attachments (not inline logos), only when there are any
└── source.eml                      a copy of the original export
```

- The folder is named `YYYY-MM-DD_subject-slug`, dated by the newest message. The slug drops `Re:`/`Fw:` prefixes
  and bracketed labels (`[EXTERNAL]`, `【ご案内】`, `(rev 2)`), and is at most 40 characters. `--name` replaces the
  whole name.
- No path mailmd writes is longer than 250 characters (Windows tools fail past 260). In a deep folder, a generated
  name is shortened to fit; a `--name` that doesn't fit is an error.
- `source.eml` is the record the Markdown is derived from. Running `mailmd convert` on it again with `--force`
  rebuilds the folder in place. `--no-source` leaves it out.
- An existing folder is never overwritten unless you pass `--force`.

Known gaps and planned behavior are tracked in the GitHub issues.

## Develop

Routine commands are recipes in the `justfile` ([just](https://github.com/casey/just)); run `just` to list them.

```
just sync              # install dependencies
just check             # everything that must pass before pushing: lint, types, tests, leakcheck
just test -k naming    # tests, with extra arguments passed to pytest
just fmt               # fix what ruff can fix, then format
just convert samples/case/thread.eml -o out
```

On Windows the recipes run in Git Bash; the `windows-shell` setting at the top of the `justfile` points to it.
Without `just` installed, `uvx --from rust-just just <recipe>` runs it, or see the commands inside each recipe.

Tests use synthetic exports in `tests/fixtures/`. Real email exports are git-ignored and must never be committed.

### Keeping real email details out of this repo

This repository is public, and examples for an email tool are easily modeled on real messages. A guard runs on every
commit:

```
just hooks                                      # once per clone: installs the pre-commit and commit-msg hooks
cp .leakcheck.local.example .leakcheck.local    # then list your real domains, names and companies in it
```

- **Every staged file and the commit message** are checked against `.leakcheck.local`, a git-ignored list of real
  terms matched case-insensitively. The list is never committed, since a list of real names would itself be a leak.
- **Fixtures** in `tests/fixtures/` must use reserved example domains (`example.com`, `*.example`, `*.test`, ...) and
  may not contain Exchange transport headers, whether or not a deny-list exists.
- Nothing local checks GitHub issues, PR descriptions or comments: use made-up examples there too.
