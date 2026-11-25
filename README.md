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
uv tool install .
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

```
uv sync
uv run pytest
uv run ruff check . && uv run ruff format --check . && uv run ty check src
```

Tests use the synthetic export in `tests/fixtures/`. Real email exports are git-ignored and must never be committed.
