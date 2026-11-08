import re
from typing import get_args

from app.companion.schemas import Mood

MOODS: tuple[str, ...] = get_args(Mood)

# Leading "[mood: X]" tag. Case-insensitive, whitespace-tolerant.
_MOOD_TAG = re.compile(r"^\[\s*mood\s*:\s*([^\]\r\n]*)\]", re.IGNORECASE)


def parse_mood(raw: str, previous: str) -> tuple[str, str]:
    """Return (clean_text, mood).

    A known leading tag is removed and sets the mood. A missing or unknown tag keeps the
    previous mood and returns the text unchanged.
    """
    if not raw:
        return raw, previous
    stripped = raw.lstrip()
    match = _MOOD_TAG.match(stripped)
    if match is None:
        return raw, previous
    value = match.group(1).strip().lower()
    if value not in MOODS:
        return raw, previous
    return stripped[match.end():].strip(), value
