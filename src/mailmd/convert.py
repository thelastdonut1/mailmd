"""Pipeline: .eml file -> Thread -> a self-contained thread folder.

2026-11-25_project-kickoff/
├── 2026-11-25_project-kickoff.md
├── attachments/          (only when the message has attachments)
└── source.eml            (a byte-for-byte copy of the input, unless include_source=False)
"""

import shutil
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path

from mailmd import parse
from mailmd.clean import clean_messages
from mailmd.model import Thread
from mailmd.naming import folder_name, safe_filename, unique
from mailmd.render import render

ATTACHMENTS_DIR = "attachments"
SOURCE_FILE = "source.eml"


class OutputExistsError(Exception):
    """The thread folder already exists and replacing it was not requested."""


@dataclass
class Result:
    folder: Path
    markdown_path: Path
    message_count: int
    attachment_paths: list[Path]


def build_thread(path: Path) -> Thread:
    msg = parse.load(path)
    messages = parse.split_thread(msg)
    messages.reverse()  # quoted history is newest first; a thread reads oldest first
    removed = clean_messages(messages)
    return Thread(
        subject=str(msg.get("Subject", "")),
        messages=messages,
        attachments=parse.attachments(msg),
        boilerplate_removed=removed,
        sent_at=_sent_at(str(msg.get("Date", ""))),
    )


def default_folder_name(path: Path) -> str:
    """The folder name `convert` would use for this file when no name is given."""
    thread = build_thread(path)
    return folder_name(thread.subject, thread.sent_at)


def convert(
    path: Path,
    parent: Path,
    name: str | None = None,
    include_source: bool = True,
    force: bool = False,
) -> Result:
    """Write the thread folder for `path` inside `parent` and return what was written."""
    # Read everything before touching the disk: with force=True the input may live inside the folder being
    # replaced (rebuilding from its own source.eml).
    thread = build_thread(path)
    source_bytes = path.read_bytes()

    folder = parent / (name or folder_name(thread.subject, thread.sent_at))
    if folder.exists():
        if not force:
            raise OutputExistsError(f"{folder} already exists (use --force to replace it)")
        shutil.rmtree(folder)
    folder.mkdir(parents=True)

    saved = _save_attachments(thread, folder / ATTACHMENTS_DIR)
    if include_source:
        (folder / SOURCE_FILE).write_bytes(source_bytes)

    markdown = render(
        thread,
        source=SOURCE_FILE if include_source else path.name,
        attachment_paths=[f"{ATTACHMENTS_DIR}/{p.name}" for p in saved],
    )
    markdown_path = folder / f"{folder.name}.md"
    markdown_path.write_text(markdown, encoding="utf-8")
    return Result(
        folder=folder, markdown_path=markdown_path, message_count=len(thread.messages), attachment_paths=saved
    )


def _save_attachments(thread: Thread, directory: Path) -> list[Path]:
    saved: list[Path] = []
    used: set[str] = set()
    for item in thread.attachments:
        item.filename = unique(safe_filename(item.filename), used)
        directory.mkdir(exist_ok=True)
        target = directory / item.filename
        target.write_bytes(item.data)
        saved.append(target)
    return saved


def _sent_at(date_header: str) -> datetime | None:
    try:
        return parsedate_to_datetime(date_header).astimezone()
    except (TypeError, ValueError):
        return None
