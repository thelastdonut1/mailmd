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
mailmd convert "RE_ Project kickoff.eml"            # writes "RE_ Project kickoff.md" next to the .eml
mailmd convert thread.eml -o notes/correspondence   # or into another folder
mailmd convert *.eml                                # several files, each converted on its own
```

Output is Markdown with YAML front matter (subject, participants, first and last send time, attachment paths),
followed by one section per message.

Known gaps and planned behavior are tracked in the GitHub issues.

## Develop

```
uv sync
uv run pytest
uv run ruff check . && uv run ruff format --check . && uv run ty check src
```

Tests use the synthetic export in `tests/fixtures/`. Real email exports are git-ignored and must never be committed.
