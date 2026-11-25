from datetime import datetime

import pytest

from mailmd.naming import folder_name, is_valid_folder_name, safe_filename, slug, topic


def test_folder_name_is_date_then_subject_slug():
    # Promise: thread folders are named `YYYY-MM-DD_subject-slug` so a folder of threads sorts by date.
    assert folder_name("RE: Project kickoff", datetime(2026, 11, 5, 9, 30)) == "2026-11-05_project-kickoff"


def test_folder_name_without_a_date_says_undated():
    # Promise: a message with no usable Date header still gets a folder name instead of failing.
    assert folder_name("Project kickoff", None) == "undated_project-kickoff"


@pytest.mark.parametrize(
    ("subject", "expected"),
    [
        ("RE: FW: Re: Budget", "budget"),
        ("AW: SV: WG: Budget", "budget"),
        ("Fw：会議 2026", "会議-2026"),
        ("Q3 review / plan: draft?", "q3-review-plan-draft"),
        ("   ", "no-subject"),
    ],
)
def test_slug_strips_reply_prefixes_and_punctuation_but_keeps_non_ascii_letters(subject, expected):
    # Promise: slugs drop Re:/Fw:/AW:/SV:/WG: prefixes (including the full-width colon) and punctuation, use hyphens
    # between words, and keep letters from any script so Japanese subjects stay readable.
    assert slug(subject) == expected


@pytest.mark.parametrize(
    ("subject", "expected"),
    [
        ("[EXTERNAL] RE: Quote for retrofits (rev 2)", "Quote for retrofits"),
        ("Fw: 【ご案内】Annual Partner Summit 2027（3/2〜6・大阪開催）", "Annual Partner Summit 2027"),
        ("[EXT] RE: [Ticket 42] FW: Budget「草案」", "Budget"),
    ],
)
def test_topic_drops_bracketed_labels_and_prefixes_in_any_order(subject, expected):
    # Promise: bracketed segments ([], 【】, (), （）, 「」) are treated as labels and removed, along with reply
    # prefixes, even when labels and prefixes alternate.
    assert topic(subject) == expected


def test_subject_made_only_of_a_bracketed_label_keeps_the_label_text():
    # Promise: if removing bracketed segments would leave nothing, the bracket contents are used instead.
    assert slug("RE: 【ご案内】") == "ご案内"


def test_long_slug_is_capped_on_a_word_boundary():
    # Promise: slugs are at most 40 characters by default and don't end mid-word or on a hyphen.
    result = slug("Quarterly planning discussion for the regional engineering teams and partners")
    assert len(result) <= 40
    assert result == "quarterly-planning-discussion-for-the"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("report:final?.pdf", "report_final_.pdf"), ("..\\..\\evil.exe", "evil.exe"), ("  .  ", "attachment")],
)
def test_attachment_names_are_safe_on_windows(raw, expected):
    # Promise: attachment names can never escape the output folder or contain characters Windows rejects.
    assert safe_filename(raw) == expected


@pytest.mark.parametrize(("name", "valid"), [("acme-quote", True), ("a/b", False), ("..", False), ("x:y", False)])
def test_user_supplied_folder_names_are_accepted_only_if_already_safe(name, valid):
    # Promise: a --name that isn't a plain, safe folder name is rejected rather than silently rewritten.
    assert is_valid_folder_name(name) is valid
