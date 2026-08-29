import re
import unicodedata

JUNK_INVISIBLE_CHARS = [
    "\u200b",
    "\ufeff",
    "\u200e",
    "\u200f",
]


_JUNK_PATTERN = re.compile("|".join(JUNK_INVISIBLE_CHARS))
_WHITESPACE_PATTERN = re.compile(r"\s+")


def normalize_unicode(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def strip_junk_invisible_chars(text: str) -> str:
    return _JUNK_PATTERN.sub("", text)


def collapse_whitespace(text: str) -> str:
    return _WHITESPACE_PATTERN.sub(" ", text).strip()


def normalize_text(text: str) -> str:
    text = normalize_unicode(text)
    text = strip_junk_invisible_chars(text)
    text = collapse_whitespace(text)
    return text