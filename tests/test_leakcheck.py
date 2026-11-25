"""tools/leakcheck.py: the guard that keeps real email details out of this public repository (issue #8)."""

from pathlib import Path

import pytest
from leakcheck import check_text, load_deny_terms, main

REPO = Path(__file__).parent.parent


@pytest.fixture
def repo(tmp_path):
    """A throwaway repository root with a deny-list of made-up 'real' terms."""
    (tmp_path / ".leakcheck.local").write_text("# comment lines are ignored\nacmecorp.com\nJane Doe\n\n")
    (tmp_path / "tests" / "fixtures").mkdir(parents=True)
    return tmp_path


def run(repo: Path, *args: str) -> int:
    return main(list(args), root=repo)


def test_deny_listed_term_in_any_staged_file_blocks_the_commit(repo, capsys):
    # Promise: a deny-listed term anywhere in a staged file, in any letter case, fails the check and reports
    # the file and line.
    source = repo / "tests" / "test_x.py"
    source.write_text('subject = "ok"\nsender = "JANE DOE <jd@example.com>"\n')
    assert run(repo, str(source)) == 1
    assert "tests/test_x.py:2: contains deny-listed term 'jane doe'" in capsys.readouterr().err


def test_deny_list_ignores_comments_and_blank_lines(repo):
    # Promise: only real terms are loaded from .leakcheck.local; "#" comment lines and blank lines are skipped.
    assert load_deny_terms(repo) == ["acmecorp.com", "jane doe"]


def test_without_a_deny_list_only_the_fixture_rule_applies(tmp_path):
    # Promise: with no .leakcheck.local the deny-list check is skipped instead of failing, so a fresh clone
    # can still commit.
    source = tmp_path / "notes.md"
    source.write_text("Jane Doe at acmecorp.com\n")
    assert run(tmp_path, str(source)) == 0


def test_commit_message_is_checked_but_git_comment_lines_are_not(repo, capsys):
    # Promise: deny-listed terms in a commit message fail the commit-msg hook; git's "#" instruction lines,
    # which never reach the commit, are ignored.
    message = repo / "COMMIT_EDITMSG"
    message.write_text("Fix naming\n# Changes to be committed: acmecorp.com\n")
    assert run(repo, "--commit-msg", str(message)) == 0
    message.write_text("Fix naming for the Acmecorp.com thread\n")
    assert run(repo, "--commit-msg", str(message)) == 1
    assert "commit message:1" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("address", "allowed"),
    [
        ("alice@example.com", True),
        ("bob@mail.example.org", True),
        ("carol@example.co.jp", True),
        ("dave@corp.example", True),
        ("erin@partner.test", True),
        ("frank@realcompany.com", False),
        ("grace@gmail.com", False),
    ],
)
def test_fixture_addresses_must_use_reserved_example_domains(address, allowed):
    # Promise: in tests/fixtures/, an address on any domain other than a reserved example domain is reported,
    # even with no deny-list, because only a real export would contain one.
    findings = check_text(f"From: {address}\n", "tests/fixtures/x.eml", deny_terms=[], is_fixture=True)
    assert (findings == []) is allowed


def test_content_ids_are_not_mistaken_for_addresses():
    # Promise: inline-image content IDs (image001.png@01DD7CE4.98B63A90) don't trip the fixture address rule.
    line = "[cid:image001.png@01DD7CE4.98B63A90]<https://example.com/x>\n"
    assert check_text(line, "tests/fixtures/x.eml", deny_terms=[], is_fixture=True) == []


def test_exchange_transport_headers_mark_a_fixture_as_a_real_export():
    # Promise: X-MS-Exchange-* headers, which only real Exchange exports carry, are reported in fixtures.
    findings = check_text("X-MS-Exchange-Organization-AuthAs: Anonymous\n", "tests/fixtures/x.eml", [], True)
    assert len(findings) == 1


def test_address_rule_applies_only_to_fixtures(repo):
    # Promise: ordinary files may mention non-example domains (e.g. a README linking gmail.com); only fixtures
    # are held to the example-domain rule.
    readme = repo / "README.md"
    readme.write_text("Works with exports from user@gmail.com accounts.\n")
    assert run(repo, str(readme)) == 0


def test_binary_files_are_skipped(repo):
    # Promise: binary files (images, .msg) are not scanned as text, so their bytes can't cause false alarms.
    image = repo / "logo.png"
    image.write_bytes(b"\x89PNG\x00\x00acmecorp.com")
    assert run(repo, str(image)) == 0


def test_the_committed_fixtures_pass_the_check():
    # Promise: every fixture in this repository satisfies the fixture rule, so the hook never blocks them.
    fixtures = sorted((REPO / "tests" / "fixtures").rglob("*"))
    assert fixtures, "expected at least one fixture"
    assert run(REPO, *[str(p) for p in fixtures if p.is_file()]) == 0
