"""Render a Thread as Markdown with YAML front matter."""

import json
import re

from mailmd.model import Thread
from mailmd.naming import base_subject

# "Name <address>" as Outlook writes it in quoted headers. Names are not RFC-quoted
# ("Smith, Alice <alice@example.com>"), so email.utils.parseaddr misreads the comma as an address separator.
NAME_ADDRESS = re.compile(r"^\s*(?P<name>.*?)\s*<(?P<address>[^<>]+)>\s*$")


def render(thread: Thread, source: str, attachment_paths: list[str]) -> str:
    participants = _participants([m.sender for m in thread.messages])
    front = {
        "subject": thread.subject,
        "source": source,
        "messages": len(thread.messages),
        "first_sent": thread.messages[0].sent if thread.messages else "",
        "last_sent": thread.messages[-1].sent if thread.messages else "",
        "participants": participants,
        "attachments": attachment_paths,
        "boilerplate_paragraphs_removed": thread.boilerplate_removed,
    }
    lines = ["---"]
    for key, value in front.items():
        lines.append(f"{key}: {_yaml(value)}")
    lines += ["---", "", f"# {thread.subject}", ""]

    for n, message in enumerate(thread.messages, start=1):
        lines.append(f"## {n}. {_name(message.sender)} · {message.sent}")
        lines.append("")
        lines.append(f"**To:** {message.to}  ")
        if message.cc:
            lines.append(f"**Cc:** {message.cc}  ")
        if message.subject and base_subject(message.subject).lower() != base_subject(thread.subject).lower():
            lines.append(f"**Subject:** {message.subject}  ")
        lines.append("")
        lines.append(message.body or "_(no text)_")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _name(sender: str) -> str:
    """Display name only: '"Smith, Alice" <alice@example.com>' and 'Smith, Alice' both become 'Smith, Alice'."""
    name, address = _split_address(sender)
    return name or address


def _participants(senders: list[str]) -> list[str]:
    """One entry per person, keeping the most complete 'Name <address>' form seen for them."""
    best: dict[str, str] = {}
    for sender in senders:
        name, address = _split_address(sender)
        key = (name or address).lower()
        if not key:
            continue
        form = f"{name} <{address}>" if name and address else (name or address)
        if key not in best or len(form) > len(best[key]):
            best[key] = form
    return sorted(best.values())


def _split_address(sender: str) -> tuple[str, str]:
    match = NAME_ADDRESS.match(sender)
    if match:
        return match.group("name").strip('" '), match.group("address").strip()
    return sender.strip('" '), ""


def _yaml(value: object) -> str:
    """JSON scalars and lists are valid YAML, and JSON escaping handles colons, quotes and non-ASCII safely."""
    if isinstance(value, list):
        if not value:
            return "[]"
        return "".join(f"\n  - {json.dumps(item, ensure_ascii=False)}" for item in value)
    if isinstance(value, int):
        return str(value)
    return json.dumps(value, ensure_ascii=False)
