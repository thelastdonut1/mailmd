"""Names for everything mailmd writes to disk: the thread folder, its Markdown file and attachments."""

import re
from datetime import datetime
from pathlib import Path

# Defaults for naming rules. Issue #10 moves these into a config file.

# Reply/forward prefixes, case-insensitive, followed by a colon (AW/SV/WG: German, Swedish, Dutch clients)
REPLY_PREFIXES = ("re", "fw", "fwd", "aw", "sv", "wg")
# Bracket pairs whose contents are labels or details ([EXTERNAL], 【重要】, (rev 2), dates), not the topic
STRIP_BRACKETS = ("[]", "【】", "()", "（）", "「」")
MAX_SLUG_CHARS = 40
MIN_SLUG_CHARS = 20  # the shortest a slug may be shrunk to when fitting the path-length budget

REPLY_PREFIX = re.compile(rf"^\s*(({'|'.join(REPLY_PREFIXES)})\s*[:：]\s*)+", re.IGNORECASE)
BRACKETED = re.compile("|".join(f"{re.escape(o)}[^{re.escape(c)}]*{re.escape(c)}" for o, c in STRIP_BRACKETS))
# Characters Windows rejects in file and folder names, plus control characters
FORBIDDEN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def base_subject(subject: str) -> str:
    """The subject without any leading Re:/Fw: prefixes."""
    return REPLY_PREFIX.sub("", subject).strip()


def topic(subject: str) -> str:
    """The subject's topic: reply prefixes and bracketed labels removed.

    `[EXTERNAL] RE: Quote for retrofits (rev 2)` becomes `Quote for retrofits`. If removing bracketed segments
    would leave nothing (a subject that is only `【ご案内】`), the bracket contents are kept instead.
    """
    previous = None
    text = subject
    while text != previous:  # labels and prefixes can alternate: "[EXT] RE: [Ticket] FW: ..."
        previous = text
        text = BRACKETED.sub(" ", base_subject(text)).strip()
    return text or base_subject(subject)


def folder_name(subject: str, sent: datetime | None, max_chars: int = MAX_SLUG_CHARS) -> str:
    """`YYYY-MM-DD_subject-slug`, dated by the newest message in the thread."""
    date = sent.strftime("%Y-%m-%d") if sent else "undated"
    return f"{date}_{slug(subject, max_chars)}"


def slug(subject: str, max_chars: int = MAX_SLUG_CHARS) -> str:
    """Lowercase, hyphen-separated and short, keeping non-ASCII letters so Japanese subjects stay readable."""
    words = "".join(ch.lower() if ch.isalnum() else "-" for ch in topic(subject))
    words = re.sub(r"-+", "-", words).strip("-")
    if len(words) > max_chars:
        cut = words[:max_chars]
        # End on a word boundary when one is reasonably close, so slugs don't end mid-word
        words = cut.rsplit("-", 1)[0] if "-" in cut[max_chars // 2 :] else cut
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
