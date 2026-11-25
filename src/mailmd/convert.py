"""Pipeline: .eml file -> Thread -> a self-contained thread folder.

    2026-11-25_project-kickoff/
    ├── 2026-11-25_project-kickoff.md
    ├── attachments/          (only when the message has attachments)
    └── source.eml            (a byte-for-byte copy of the input, unless include_source=False)

Converting happens in two steps. `plan()` reads the input and decides every name and path without touching the
disk; `write()` creates the folder. The CLI uses the plan to catch problems (an over-long path, two inputs mapping
to the same folder) before anything is written.
"""

import shutil
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path

from mailmd import parse
from mailmd.clean import clean_messages
from mailmd.model import Thread
from mailmd.naming import MAX_SLUG_CHARS, MIN_SLUG_CHARS, folder_name, safe_filename, unique
from mailmd.render import render

ATTACHMENTS_DIR = "attachments"
SOURCE_FILE = "source.eml"
# Windows tools (Explorer, OneDrive, zip, upload dialogs) fail past 260 characters; leave room for later renames.
MAX_PATH_CHARS = 250


class OutputExistsError(Exception):
    """The thread folder already exists and replacing it was not requested."""


class PathTooLongError(Exception):
    """Even the shortest allowed folder name would produce a path over MAX_PATH_CHARS."""


@dataclass
class Plan:
    source: Path
    source_bytes: bytes
    thread: Thread
    folder: Path
    include_source: bool

    @property
    def markdown_path(self) -> Path:
        return self.folder / f"{self.folder.name}.md"

    def paths(self) -> list[Path]:
        """Every file this plan will write."""
        written = [self.markdown_path, *(self.folder / ATTACHMENTS_DIR / a.filename for a in self.thread.attachments)]
        if self.include_source:
            written.append(self.folder / SOURCE_FILE)
        return written

    def longest_path(self) -> int:
        return max(len(str(p.absolute())) for p in self.paths())


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
    thread = Thread(
        subject=str(msg.get("Subject", "")),
        messages=messages,
        attachments=parse.attachments(msg),
        boilerplate_removed=removed,
        sent_at=_sent_at(str(msg.get("Date", ""))),
    )
    used: set[str] = set()
    for item in thread.attachments:
        item.filename = unique(safe_filename(item.filename), used)
    return thread


def plan(path: Path, parent: Path, name: str | None = None, include_source: bool = True) -> Plan:
    """Decide the folder and every file name for `path` without writing anything.

    A generated folder name is shortened (down to MIN_SLUG_CHARS) until the longest path fits MAX_PATH_CHARS.
    A name given with `name` is used exactly as given, so if it doesn't fit, that is an error.
    """
    # Read the input completely now: with force=True the input may live inside the folder being replaced
    # (rebuilding from its own source.eml).
    thread = build_thread(path)
    source_bytes = path.read_bytes()

    def candidate(folder: str) -> Plan:
        return Plan(path, source_bytes, thread, parent / folder, include_source)

    if name is not None:
        result = candidate(name)
    else:
        for max_chars in range(MAX_SLUG_CHARS, MIN_SLUG_CHARS - 1, -1):
            result = candidate(folder_name(thread.subject, thread.sent_at, max_chars))
            if result.longest_path() <= MAX_PATH_CHARS:
                break
    if result.longest_path() > MAX_PATH_CHARS:
        raise PathTooLongError(
            f"the longest output path would be {result.longest_path()} characters (limit {MAX_PATH_CHARS}); "
            "use a shorter --out folder or a shorter --name"
        )
    return result


def write(plan: Plan, force: bool = False) -> Result:
    """Create the thread folder described by `plan`."""
    folder = plan.folder
    if folder.exists():
        if not force:
            raise OutputExistsError(f"{folder} already exists (use --force to replace it)")
        shutil.rmtree(folder)
    folder.mkdir(parents=True)

    saved: list[Path] = []
    for item in plan.thread.attachments:
        (folder / ATTACHMENTS_DIR).mkdir(exist_ok=True)
        target = folder / ATTACHMENTS_DIR / item.filename
        target.write_bytes(item.data)
        saved.append(target)
    if plan.include_source:
        (folder / SOURCE_FILE).write_bytes(plan.source_bytes)

    markdown = render(
        plan.thread,
        source=SOURCE_FILE if plan.include_source else plan.source.name,
        attachment_paths=[f"{ATTACHMENTS_DIR}/{p.name}" for p in saved],
    )
    plan.markdown_path.write_text(markdown, encoding="utf-8")
    return Result(
        folder=folder, markdown_path=plan.markdown_path, message_count=len(plan.thread.messages), attachment_paths=saved
    )


def convert(
    path: Path,
    parent: Path,
    name: str | None = None,
    include_source: bool = True,
    force: bool = False,
) -> Result:
    """Plan and write the thread folder for `path` inside `parent`."""
    return write(plan(path, parent, name=name, include_source=include_source), force=force)


def _sent_at(date_header: str) -> datetime | None:
    try:
        return parsedate_to_datetime(date_header).astimezone()
    except (TypeError, ValueError):
        return None
