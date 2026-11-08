import pytest

from app.companion.mood import MOODS, parse_mood


def test_moods_match_schema():
    assert MOODS == ("calm", "warm", "happy", "concerned", "encouraging", "serious")


@pytest.mark.parametrize(
    ("raw", "previous", "expected_text", "expected_mood"),
    [
        ("[mood: warm] Vanakkam!", "calm", "Vanakkam!", "warm"),
        ("[mood: happy]Glad to hear it", "calm", "Glad to hear it", "happy"),
    ],
)
def test_tag_present_sets_mood_and_strips_tag(raw, previous, expected_text, expected_mood):
    assert parse_mood(raw, previous) == (expected_text, expected_mood)


def test_missing_tag_keeps_previous_mood_and_text():
    assert parse_mood("Plain reply, no tag.", "serious") == ("Plain reply, no tag.", "serious")


def test_tag_not_at_start_is_not_a_tag():
    raw = "Hello [mood: warm] there"
    assert parse_mood(raw, "calm") == (raw, "calm")


def test_unknown_mood_keeps_previous_and_text_unchanged():
    raw = "[mood: angry] Hi"
    assert parse_mood(raw, "concerned") == (raw, "concerned")


@pytest.mark.parametrize(
    "raw",
    [
        "[MOOD: HAPPY] Hello",
        "[Mood:Happy]   Hello",
        "   [ mood :  happy ]  Hello",
        "\n[mood: happy]\nHello",
    ],
)
def test_case_and_whitespace_are_tolerated(raw):
    assert parse_mood(raw, "calm") == ("Hello", "happy")


def test_empty_text_is_handled():
    assert parse_mood("", "calm") == ("", "calm")
