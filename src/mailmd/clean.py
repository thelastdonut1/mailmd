"""Remove noise from message bodies: image placeholders, link wrappers and repeated boilerplate."""

import re
from collections import Counter

from mailmd.model import Message

# Lines that are only an inline-image placeholder, e.g. "[cid:image001.png@01DD7CE4.98B63A90]<https://...>"
IMAGE_PLACEHOLDER = re.compile(r"^\s*\[(cid:|https?://)[^\]]*\](<[^>]*>)?\s*$")
# Duplicate address rendering, e.g. "jane@x.com<mailto:jane@x.com>"
MAILTO = re.compile(r"<mailto:[^>]*>")
# Link-scanner rewrites, e.g. "<https://url.us.m.mimecastprotect.com/s/...>"
SCANNER_LINK = re.compile(r"<https?://[^>]*(mimecast|safelinks\.protection)[^>]*>")
NOISE_LINES = re.compile(r"^\s*CGBANNERINDICATOR\s*$")
# Paragraphs shorter than this are never treated as boilerplate ("Thanks," repeats legitimately)
MIN_BOILERPLATE_CHARS = 40
# How many leading characters must match before a first paragraph counts as a squashed preview copy
PREVIEW_PROBE_CHARS = 30


def clean_messages(messages: list[Message]) -> int:
    """Clean every message body in place; return how many boilerplate paragraphs were removed."""
    for message in messages:
        message.sender = MAILTO.sub("", message.sender)
        message.to = MAILTO.sub("", message.to)
        message.cc = MAILTO.sub("", message.cc)
        message.body = _drop_preview_paragraph(_clean_lines(message.body))

    # A paragraph that appears in two or more messages is boilerplate (confidentiality notices, signatures).
    counts = Counter(key for message in messages for key in {_key(p) for p in _paragraphs(message.body)})
    repeated = {key for key, count in counts.items() if count > 1 and len(key) >= MIN_BOILERPLATE_CHARS}

    removed = 0
    for message in messages:
        kept = []
        for paragraph in _paragraphs(message.body):
            if _key(paragraph) in repeated:
                removed += 1
            else:
                kept.append(paragraph)
        message.body = "\n\n".join(kept)
    return removed


def _clean_lines(body: str) -> str:
    lines = []
    for line in body.split("\n"):
        if IMAGE_PLACEHOLDER.match(line) or NOISE_LINES.match(line):
            lines.append("")  # keep a paragraph break where the noise was, so neighbours don't merge
            continue
        line = MAILTO.sub("", line)
        line = SCANNER_LINK.sub("", line)
        lines.append(line.rstrip())
    return "\n".join(lines)


def _drop_preview_paragraph(body: str) -> str:
    """Drop a leading paragraph that is just the message's own text squashed onto one line.

    Outlook HTML often carries hidden "preview text", which shows up in the plain-text part as the start
    of the message repeated without line breaks.
    """
    paragraphs = _paragraphs(body)
    if len(paragraphs) < 2:
        return body
    first = re.sub(r"\s+", "", paragraphs[0])
    rest = re.sub(r"\s+", "", "".join(paragraphs[1:]))
    probe = first[:PREVIEW_PROBE_CHARS]
    if len(probe) == PREVIEW_PROBE_CHARS and rest.startswith(probe):
        return "\n\n".join(paragraphs[1:])
    return body


def _paragraphs(body: str) -> list[str]:
    """Split on blank lines; this also collapses Outlook's runs of empty lines."""
    return [p.strip("\n") for p in re.split(r"\n\s*\n", body) if p.strip()]


def _key(paragraph: str) -> str:
    return re.sub(r"\s+", " ", paragraph).strip().lower()
