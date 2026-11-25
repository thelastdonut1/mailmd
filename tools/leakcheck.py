"""Block real email details from being committed to this public repository (issue #8).

Two checks:

1. Deny-list: terms listed one per line in `.leakcheck.local` (git-ignored, never committed) are matched
   case-insensitively against staged files and the commit message. Put work email domains, people's names and
   company names there. If the file doesn't exist, this check is skipped.
2. Fixture rule: files under `tests/fixtures/` must be synthetic. Every email address must use a reserved example
   domain, and Exchange transport headers (which only real exports carry) are not allowed.

Usage (run by prek, see .pre-commit-config.yaml):

    python tools/leakcheck.py FILE...           # pre-commit: check staged files
    python tools/leakcheck.py --commit-msg FILE # commit-msg: check the message being committed
"""

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

DENY_FILE = ".leakcheck.local"
FIXTURES_DIR = "tests/fixtures"

# Reserved for documentation by RFC 2606 / RFC 6761, plus example.co.jp for Japanese-format examples
ALLOWED_DOMAINS = ("example.com", "example.org", "example.net", "example.co.jp")
ALLOWED_TLDS = (".example", ".test", ".invalid", ".localhost")
# A top-level domain of letters only, so content IDs like image001.png@01DD7CE4.98B63A90 don't count as addresses
EMAIL = re.compile(r"[\w.+-]+@(?P<domain>[\w-]+(?:\.[\w-]+)*\.[a-z]{2,})\b", re.IGNORECASE)
REAL_EXPORT_HEADER = re.compile(r"^X-MS-Exchange-", re.IGNORECASE | re.MULTILINE)


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    reason: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.reason}"


def load_deny_terms(root: Path) -> list[str]:
    deny_file = root / DENY_FILE
    if not deny_file.exists():
        return []
    terms = []
    for line in deny_file.read_text(encoding="utf-8").splitlines():
        term = line.strip()
        if term and not term.startswith("#"):
            terms.append(term.lower())
    return terms


def check_text(text: str, path: str, deny_terms: list[str], is_fixture: bool) -> list[Finding]:
    findings = []
    for number, line in enumerate(text.splitlines(), start=1):
        lowered = line.lower()
        for term in deny_terms:
            if term in lowered:
                findings.append(Finding(path, number, f"contains deny-listed term {term!r}"))
        if is_fixture:
            for match in EMAIL.finditer(line):
                domain = match.group("domain").lower()
                if not _allowed_domain(domain):
                    findings.append(Finding(path, number, f"fixture address uses a non-example domain ({domain})"))
            if REAL_EXPORT_HEADER.match(line):
                findings.append(Finding(path, number, "fixture contains an Exchange transport header (real export?)"))
    return findings


def check_file(path: Path, root: Path, deny_terms: list[str]) -> list[Finding]:
    data = path.read_bytes()
    if b"\x00" in data:
        return []  # binary file
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("latin-1")
    relative = _relative(path, root)
    return check_text(text, relative, deny_terms, is_fixture=relative.startswith(f"{FIXTURES_DIR}/"))


def check_commit_message(path: Path, deny_terms: list[str]) -> list[Finding]:
    # Lines starting with "#" are git's own instructions and never end up in the commit
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if not line.startswith("#")]
    return check_text("\n".join(lines), "commit message", deny_terms, is_fixture=False)


def main(argv: list[str] | None = None, root: Path | None = None) -> int:
    parser = argparse.ArgumentParser(description="Block real email details from being committed.")
    parser.add_argument("--commit-msg", action="store_true", help="the single FILE is a commit message to check")
    parser.add_argument("files", nargs="*", type=Path)
    args = parser.parse_args(argv)
    root = root or Path.cwd()
    deny_terms = load_deny_terms(root)

    findings: list[Finding] = []
    if args.commit_msg:
        for path in args.files:
            findings += check_commit_message(path, deny_terms)
    else:
        for path in args.files:
            if path.name != DENY_FILE and path.is_file():
                findings += check_file(path, root, deny_terms)

    for finding in findings:
        print(finding, file=sys.stderr)
    if findings:
        print(f"\nleakcheck: {len(findings)} problem(s). Replace real details with made-up ones.", file=sys.stderr)
    return 1 if findings else 0


def _allowed_domain(domain: str) -> bool:
    return any(domain == d or domain.endswith(f".{d}") for d in ALLOWED_DOMAINS) or domain.endswith(ALLOWED_TLDS)


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


if __name__ == "__main__":
    sys.exit(main())
