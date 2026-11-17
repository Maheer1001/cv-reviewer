import re
from typing import List

from backend.deterministic_analyzer import BUZZWORDS_LIST


_NUMBER = re.compile(r"\d+(?:\.\d+)?")


def unsupported_numbers(source_text: str, suggested: str) -> List[str]:
    """Return quantities in suggested text that are not present in the source evidence.

    Text inside [square brackets] is a placeholder the user must replace, and export is blocked until they do,
    so numbers there are templates rather than claims.
    """
    claimed = re.sub(r"\[[^\[\]]*\]", " ", suggested or "")
    source_nums = set(_NUMBER.findall(source_text or ""))
    suggested_nums = _NUMBER.findall(claimed)
    extra = []
    for num in suggested_nums:
        if num not in source_nums and num not in extra:
            extra.append(num)
    return extra


def introduced_buzzwords(source_text: str, suggested: str) -> List[str]:
    source = (source_text or "").lower()
    suggested_l = (suggested or "").lower()
    return [word for word in BUZZWORDS_LIST if word in suggested_l and word not in source]


def rewrite_is_faithful(source_text: str, suggested: str) -> tuple[bool, str]:
    """Reject a rewrite that adds quantities or empty praise not present in the evidence."""
    if not suggested or not suggested.strip():
        return False, "The suggested rewrite was empty."
    numbers = unsupported_numbers(source_text, suggested)
    if numbers:
        return False, (
            "Discarded a rewrite that introduced "
            + ", ".join(numbers)
            + ", which is not in the original text or a confirmed answer."
        )
    buzz = introduced_buzzwords(source_text, suggested)
    if buzz:
        return False, "Discarded a rewrite that added unsupported praise: " + ", ".join(buzz[:4]) + "."
    return True, ""
