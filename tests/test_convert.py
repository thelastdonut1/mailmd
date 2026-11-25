"""Tests run against tests/fixtures/outlook_reply.eml, a synthetic Outlook export:
Alice's reply (with a real attachment and an inline logo) quoting Bob's message, which quotes Alice's first message."""

from pathlib import Path

import pytest

from mailmd.convert import build_thread, convert

FIXTURE = Path(__file__).parent / "fixtures" / "outlook_reply.eml"
NOTICE = "CONFIDENTIALITY NOTICE"


@pytest.fixture
def thread():
    return build_thread(FIXTURE)


def test_quoted_header_blocks_become_messages_oldest_first(thread):
    # Promise: each Outlook "From:/Sent:/To:/Subject:" block becomes its own message, ordered oldest to newest.
    assert [m.body.splitlines()[0] for m in thread.messages] == ["Bob,", "Alice,", "Hi Bob,"]
    assert [m.quoted for m in thread.messages] == [True, True, False]


def test_exported_message_metadata_comes_from_real_headers(thread):
    # Promise: the newest message's sender, recipients and date come from the .eml headers, not its body.
    newest = thread.messages[-1]
    assert newest.sender == '"Smith, Alice" <alice@example.com>'
    assert newest.cc == '"Lee, Carol" <carol@example.com>'
    assert "November 25, 2026" in newest.sent


def test_notice_repeated_across_messages_is_removed_everywhere(thread):
    # Promise: a long paragraph repeated in two or more messages (a confidentiality notice) appears in none of them.
    assert all(NOTICE not in m.body for m in thread.messages)
    assert thread.boilerplate_removed == 3


def test_short_repeated_lines_are_kept(thread):
    # Promise: short lines that legitimately repeat ("Thanks,") are never treated as boilerplate.
    assert all("Thanks," in m.body for m in thread.messages)


def test_outlook_link_and_image_noise_is_removed(thread):
    # Promise: mailto duplicates, link-scanner wrappers, inline-image placeholders and banner lines are stripped,
    # while the link text itself is kept.
    text = "\n".join(m.body + m.sender + m.to + m.cc for m in thread.messages)
    for noise in ("<mailto:", "mimecastprotect", "[cid:", "CGBANNERINDICATOR", "image-processing-service"):
        assert noise not in text
    assert "https://intranet.example.com/plan" in text


def test_squashed_preview_paragraph_is_dropped(thread):
    # Promise: a leading one-line copy of the message (Outlook's hidden preview text) is removed.
    assert thread.messages[-1].body.startswith("Hi Bob,\n\nHere is the updated schedule.")


def test_markdown_lists_each_participant_once(tmp_path):
    # Promise: one person written several ways ('"Smith, Alice" <a@x>' and 'Smith, Alice <a@x>') is listed once.
    markdown = convert(FIXTURE, tmp_path).markdown_path.read_text(encoding="utf-8")
    front_matter = markdown.split("---")[1]
    assert front_matter.count("Smith, Alice") == 1
    assert "## 3. Smith, Alice ·" in markdown
