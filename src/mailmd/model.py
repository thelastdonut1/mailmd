"""Plain data types shared across the pipeline."""

from dataclasses import dataclass, field


@dataclass
class Message:
    """One message in a thread: either the exported message itself or a copy quoted inside it."""

    sender: str
    sent: str
    to: str = ""
    cc: str = ""
    subject: str = ""
    body: str = ""
    quoted: bool = False  # True when this message was recovered from quoted history


@dataclass
class Attachment:
    filename: str
    data: bytes


@dataclass
class Thread:
    subject: str
    messages: list[Message]  # oldest first
    attachments: list[Attachment] = field(default_factory=list)
    boilerplate_removed: int = 0
