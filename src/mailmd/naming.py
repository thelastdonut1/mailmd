"""Names for everything mailmd writes to disk: the thread folder, its Markdown file and attachments."""

import re
from datetime import datetime
from pathlib import Path

# "Re:", "RE:", "Fw:", "FW:", "Fwd:" and the full-width colon variant used by Japanese clients
REPLY_PREFIX = re.compile(r"^\s*((re|fw|fwd)\s*[:：]\s*)+", re.IGNORECASE)
# Characters Windows rejects in file and folder names, plus control characters
FORBIDDEN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
MAX_SLUG_CHARS = 60


def base_subject(subject: str) -> str:
    """The subject without any leading Re:/Fw: prefixes."""
    return REPLY_PREFIX.sub("", subject).strip()


def folder_name(subject: str, sent: datetime | None) -> str:
    """`YYYY-MM-DD_subject-slug`, dated by the newest message in the thread."""
    date = sent.strftime("%Y-%m-%d") if sent else "undated"
    return f"{date}_{slug(subject)}"


def slug(subject: str) -> str:
    """Lowercase, hyphen-separated and short, keeping non-ASCII letters so Japanese subjects stay readable."""
    words = "".join(ch.lower() if ch.isalnum() else "-" for ch in base_subject(subject))
    words = re.sub(r"-+", "-", words).strip("-")
    if len(words) > MAX_SLUG_CHARS:
        cut = words[:MAX_SLUG_CHARS]
        # End on a word boundary when one is reasonably close, so slugs don't end mid-word
        words = cut.rsplit("-", 1)[0] if "-" in cut[MAX_SLUG_CHARS // 2 :] else cut
    return words or "no-subject"


def safe_filename(name: str) -> str:
    """Keep only the final path component and drop characters Windows forbids in file names."""
    name = Path(name.replace("\\", "/")).name
    name = FORBIDDEN.sub("_", name).strip(" .")
    return name or "attachment"


def is_valid_folder_name(name: str) -> bool:
    """A user-supplied --name must already be a plain, safe folder name; it is never silently rewritten."""
    return bool(name) and name == safe_filename(name) and name not in {".", ".."}


def unique(name: str, used: set[str]) -> str:
    """Return `name`, or `name (2)`, `name (3)`... if it is already in `used` (case-insensitive, like Windows)."""
    stem, dot, suffix = name.rpartition(".")
    if not dot:
        stem, suffix = name, ""
    candidate, n = name, 2
    while candidate.lower() in used:
        candidate = f"{stem} ({n}).{suffix}" if suffix else f"{stem} ({n})"
        n += 1
    used.add(candidate.lower())
    return candidate
