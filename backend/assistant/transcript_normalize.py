import re


SPELLING_REPLACEMENTS = {
    "VIZAG": "Vizag",
    "JARVIS": "Jarvis",
    "VISAKHAPATNAM": "Visakhapatnam",
    "VIZIANAGARAM": "Vizianagaram",
}

SPELLED_SEQUENCE = re.compile(
    r"\b(?:"
    r"[A-Za-z]\b[\s.\-]+"
    r"){2,}"
    r"[A-Za-z]\b"
    r"\.?"
)


def _join_spelled_letters(match: re.Match) -> str:

    letters = re.findall(
        r"[A-Za-z]",
        match.group(0),
    )

    if len(letters) < 3:
        return match.group(0)

    joined = "".join(letters)
    upper = joined.upper()

    return SPELLING_REPLACEMENTS.get(
        upper,
        joined,
    )


def normalize_transcript(text: str) -> str:

    if not text or not text.strip():
        return text

    normalized = SPELLING_REPLACEMENTS.get(
        text.strip().upper(),
        text,
    )

    normalized = SPELLED_SEQUENCE.sub(
        _join_spelled_letters,
        normalized,
    )

    return normalized
