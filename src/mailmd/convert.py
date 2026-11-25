"""Pipeline: .eml file -> Thread -> Markdown file plus an attachments folder."""

import re
from dataclasses import dataclass
from pathlib import Path

from mailmd import parse
from mailmd.clean import clean_messages
from mailmd.model import Attachment, Thread
from mailmd.render import render


@dataclass
class Result:
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
    )


def convert(path: Path, out_dir: Path | None = None) -> Result:
    out_dir = out_dir or path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    thread = build_thread(path)

    attachment_dir_name = f"{path.stem}_attachments"
    saved = _save_attachments(thread.attachments, out_dir / attachment_dir_name)

    markdown = render(thread, source=path.name, attachment_dir=attachment_dir_name if saved else None)
    markdown_path = out_dir / f"{path.stem}.md"
    markdown_path.write_text(markdown, encoding="utf-8")
    return Result(markdown_path=markdown_path, message_count=len(thread.messages), attachment_paths=saved)


def _save_attachments(items: list[Attachment], directory: Path) -> list[Path]:
    saved: list[Path] = []
    used: set[str] = set()
    for item in items:
        name = _unique(_safe_filename(item.filename), used)
        item.filename = name
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / name
        target.write_bytes(item.data)
        saved.append(target)
    return saved


def _safe_filename(name: str) -> str:
    """Keep only the final path component and drop characters Windows forbids in file names."""
    name = Path(name.replace("\\", "/")).name
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .")
    return name or "attachment"


def _unique(name: str, used: set[str]) -> str:
    stem, dot, suffix = name.rpartition(".")
    if not dot:
        stem, suffix = name, ""
    candidate, n = name, 2
    while candidate.lower() in used:
        candidate = f"{stem} ({n}).{suffix}" if suffix else f"{stem} ({n})"
        n += 1
    used.add(candidate.lower())
    return candidate
