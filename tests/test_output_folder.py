"""Behavior of the thread folder that `mailmd convert` writes (issue #1)."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from mailmd.cli import app
from mailmd.convert import MAX_PATH_CHARS, OutputExistsError, PathTooLongError, convert, plan

FIXTURE = Path(__file__).parent / "fixtures" / "outlook_reply.eml"
# The fixture's Date header is 2026-11-25 14:08:16 UTC; folder dates use the machine's local time zone.
LOCAL_DATE = datetime(2026, 11, 25, 14, 8, 16, tzinfo=UTC).astimezone().strftime("%Y-%m-%d")
FOLDER = f"{LOCAL_DATE}_project-kickoff"


def run(*args: str):
    return CliRunner().invoke(app, ["convert", *args])


def test_everything_is_written_inside_one_thread_folder(tmp_path):
    # Promise: a conversion writes exactly one folder holding the Markdown (named like the folder), attachments/
    # and source.eml, and nothing else in the parent.
    result = convert(FIXTURE, tmp_path)
    assert [p.name for p in tmp_path.iterdir()] == [FOLDER]
    assert sorted(p.name for p in result.folder.iterdir()) == sorted([f"{FOLDER}.md", "attachments", "source.eml"])


def test_source_eml_is_a_byte_for_byte_copy_and_the_input_is_untouched(tmp_path):
    # Promise: source.eml is identical to the input, and the input file itself is left where it was.
    original = FIXTURE.read_bytes()
    result = convert(FIXTURE, tmp_path)
    assert (result.folder / "source.eml").read_bytes() == original
    assert FIXTURE.read_bytes() == original


def test_attachments_are_saved_with_exact_bytes_and_linked_from_front_matter(tmp_path):
    # Promise: real attachments land in attachments/ byte-for-byte, inline images are skipped, and the front matter
    # lists their paths relative to the Markdown file.
    result = convert(FIXTURE, tmp_path)
    assert [p.name for p in result.attachment_paths] == ["schedule_v2.txt"]
    assert result.attachment_paths[0].read_bytes() == b"Week 1: kickoff\n"
    assert '- "attachments/schedule_v2.txt"' in result.markdown_path.read_text(encoding="utf-8")


def test_no_source_leaves_the_original_out_and_names_it_in_front_matter(tmp_path):
    # Promise: with include_source=False there is no source.eml, and the front matter names the original file.
    result = convert(FIXTURE, tmp_path, include_source=False)
    assert not (result.folder / "source.eml").exists()
    assert 'source: "outlook_reply.eml"' in result.markdown_path.read_text(encoding="utf-8")


def test_existing_folder_is_never_overwritten_without_force(tmp_path):
    # Promise: converting into a folder that already exists fails and leaves the existing folder's files unchanged.
    first = convert(FIXTURE, tmp_path)
    (first.folder / "my-notes.txt").write_text("keep me")
    with pytest.raises(OutputExistsError):
        convert(FIXTURE, tmp_path)
    assert (first.folder / "my-notes.txt").read_text() == "keep me"


def test_force_rebuilds_the_folder_from_its_own_source_eml(tmp_path):
    # Promise: `--force` on the folder's own source.eml rebuilds the folder in place (the input is read before the
    # old folder is removed).
    first = convert(FIXTURE, tmp_path)
    rebuilt = convert(first.folder / "source.eml", tmp_path, force=True)
    assert rebuilt.folder == first.folder
    assert (rebuilt.folder / "source.eml").read_bytes() == FIXTURE.read_bytes()
    assert rebuilt.markdown_path.exists()


def test_cli_creates_the_folder_in_the_current_directory_by_default(tmp_path, monkeypatch):
    # Promise: without --out, the thread folder is created in the current working directory, not next to the input.
    monkeypatch.chdir(tmp_path)
    result = run(str(FIXTURE))
    assert result.exit_code == 0, result.output
    assert (tmp_path / FOLDER / f"{FOLDER}.md").exists()


def test_cli_out_and_name_choose_where_and_what(tmp_path):
    # Promise: --out picks the parent folder and --name replaces the whole folder name (no date added), which the
    # Markdown file also takes.
    result = run(str(FIXTURE), "--out", str(tmp_path / "notes"), "--name", "kickoff")
    assert result.exit_code == 0, result.output
    assert (tmp_path / "notes" / "kickoff" / "kickoff.md").exists()


def test_cli_rejects_name_with_several_files(tmp_path):
    # Promise: --name with more than one input is an error, because every thread would get the same folder.
    result = run(str(FIXTURE), str(FIXTURE), "--name", "kickoff", "--out", str(tmp_path))
    assert result.exit_code != 0
    assert not (tmp_path / "kickoff").exists()


def test_cli_never_lets_a_later_input_replace_an_earlier_one_in_the_same_run(tmp_path):
    # Promise: two inputs that map to the same folder name don't overwrite each other, even with --force;
    # the second is skipped and the command exits non-zero.
    copy = tmp_path / "copy.eml"
    copy.write_bytes(FIXTURE.read_bytes())
    result = run(str(FIXTURE), str(copy), "--out", str(tmp_path / "out"), "--force")
    assert result.exit_code == 1
    assert "already written in this run" in result.output


def _parent_of_length(base: Path, length: int) -> Path:
    """A (not yet created) folder under `base` whose absolute path is exactly `length` characters."""
    prefix = len(str(base.absolute())) + 1
    return base / ("p" * (length - prefix))


def test_generated_name_shrinks_until_the_longest_path_fits(tmp_path):
    # Promise: when the parent folder is deep, a generated folder name is shortened so that no written path
    # exceeds MAX_PATH_CHARS, and it keeps its date prefix.
    source = tmp_path / "long.eml"
    long_subject = b"Subject: RE: Quarterly planning discussion for the regional engineering teams"
    source.write_bytes(FIXTURE.read_bytes().replace(b"Subject: RE: Project kickoff", long_subject, 1))
    roomy = plan(source, tmp_path)
    # Deep enough that the roomy name's Markdown path (parent + 2 x folder + separators + ".md") overflows by 10
    parent = _parent_of_length(tmp_path, MAX_PATH_CHARS - (2 * len(roomy.folder.name) + 5) + 10)
    deep = plan(source, parent)
    with pytest.raises(PathTooLongError):  # the unshortened name really wouldn't fit here
        plan(source, parent, name=roomy.folder.name)
    assert deep.longest_path() <= MAX_PATH_CHARS
    assert len(deep.folder.name) < len(roomy.folder.name)
    assert deep.folder.name.startswith(f"{LOCAL_DATE}_")


def test_path_that_cannot_fit_is_an_error_before_anything_is_written(tmp_path):
    # Promise: if even the shortest generated name is too long, conversion fails without creating anything.
    parent = _parent_of_length(tmp_path, MAX_PATH_CHARS - 10)
    with pytest.raises(PathTooLongError):
        convert(FIXTURE, parent)
    assert not parent.exists()


def test_user_supplied_name_is_never_shortened(tmp_path):
    # Promise: a --name that would make a path too long is an error, not silently truncated.
    with pytest.raises(PathTooLongError):
        plan(FIXTURE, tmp_path, name="n" * MAX_PATH_CHARS)
