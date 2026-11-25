"""Read an .eml file and split its body into the messages of the thread."""

import re
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path

from mailmd.model import Attachment, Message

# Outlook writes each quoted message as a header block:
#   From: Name <address>
#   Sent: Monday, November 16, 2026 2:18 PM
#   To: ...
#   Cc: ...        (optional)
#   Subject: ...
HEADER_START = re.compile(r"^\s*From:\s*(?P<value>.+?)\s*$")
HEADER_FIELD = re.compile(r"^\s*(?P<name>Sent|Date|To|Cc|Subject):\s*(?P<value>.*?)\s*$")
SEPARATOR = re.compile(r"^\s*_{10,}\s*$")
MAX_HEADER_LINES = 8


def load(path: Path) -> EmailMessage:
    with path.open("rb") as f:
        return BytesParser(policy=policy.default).parse(f)  # type: ignore[return-value]


def body_text(msg: EmailMessage) -> str:
    """Return the message body as plain text, preferring the text/plain part."""
    part = msg.get_body(preferencelist=("plain", "html"))
    if part is None:
        return ""
    content = part.get_content()
    if part.get_content_type() == "text/html":
        content = _html_to_text(content)
    return content.replace("\r\n", "\n").replace("\xa0", " ")


def attachments(msg: EmailMessage) -> list[Attachment]:
    """Return real attachments, skipping inline images such as signature logos."""
    found = []
    for part in msg.iter_attachments():
        if part.get_content_disposition() != "attachment":
            continue
        data = part.get_payload(decode=True)
        if isinstance(data, bytes):
            found.append(Attachment(filename=part.get_filename() or "attachment", data=data))
    return found


def split_thread(msg: EmailMessage) -> list[Message]:
    """Split the exported message into its own text plus each quoted message, newest first."""
    lines = body_text(msg).split("\n")
    starts = [i for i in range(len(lines)) if _is_header_start(lines, i)]

    top = Message(
        sender=str(msg.get("From", "")),
        sent=_format_date(str(msg.get("Date", ""))),
        to=str(msg.get("To", "")),
        cc=str(msg.get("Cc", "") or ""),
        subject=str(msg.get("Subject", "")),
        body=_join(lines[: starts[0]] if starts else lines),
    )
    messages = [top]
    for n, start in enumerate(starts):
        end = starts[n + 1] if n + 1 < len(starts) else len(lines)
        fields, body_start = _read_header_block(lines, start)
        messages.append(
            Message(
                sender=fields.get("From", ""),
                sent=fields.get("Sent", fields.get("Date", "")),
                to=fields.get("To", ""),
                cc=fields.get("Cc", ""),
                subject=fields.get("Subject", ""),
                body=_join(lines[body_start:end]),
                quoted=True,
            )
        )
    return messages


def _is_header_start(lines: list[str], i: int) -> bool:
    if not HEADER_START.match(lines[i]):
        return False
    following = lines[i + 1 : i + 3]
    return any(re.match(r"^\s*(Sent|Date):", line) for line in following)


def _read_header_block(lines: list[str], start: int) -> tuple[dict[str, str], int]:
    """Read From/Sent/To/Cc/Subject lines; return the fields and the index where the body begins."""
    match = HEADER_START.match(lines[start])
    fields = {"From": match.group("value") if match else ""}
    i = start + 1
    while i < len(lines) and i <= start + MAX_HEADER_LINES:
        field = HEADER_FIELD.match(lines[i])
        if not field:
            break
        fields[field.group("name")] = field.group("value")
        i += 1
        if field.group("name") == "Subject":
            break
    return fields, i


def _join(lines: list[str]) -> str:
    """Join body lines, dropping trailing separator lines that belong to the next header block."""
    while lines and (not lines[-1].strip() or SEPARATOR.match(lines[-1])):
        lines = lines[:-1]
    return "\n".join(lines).strip("\n")


def _format_date(value: str) -> str:
    try:
        dt = parsedate_to_datetime(value).astimezone()
    except (TypeError, ValueError):
        return value
    hour = dt.hour % 12 or 12
    offset = dt.strftime("%z")
    return f"{dt:%A, %B} {dt.day}, {dt.year} {hour}:{dt:%M %p} (UTC{offset[:3]}:{offset[3:]})"


class _TextExtractor(HTMLParser):
    BLOCK_TAGS = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"}

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in {"style", "script", "head"}:
            self._skip += 1
        elif tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"style", "script", "head"}:
            self._skip = max(0, self._skip - 1)
        elif tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self.parts.append(data)


def _html_to_text(html: str) -> str:
    extractor = _TextExtractor()
    extractor.feed(html)
    return "".join(extractor.parts)
