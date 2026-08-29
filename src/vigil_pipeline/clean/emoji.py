import json
import emoji as emoji_lib

THREAT_SIGNAL_EMOJI = {"🔪", "🔫", "💀", "⚰️", "🩸"}


def extract_emoji(text: str) -> list[str]:
    return [match["emoji"] for match in emoji_lib.emoji_list(text)]


def strip_emoji(text: str) -> str:
    stripped = emoji_lib.replace_emoji(text, replace="")
    return " ".join(stripped.split())


def emoji_flags_json(emojis: list[str]) -> str | None:
    return json.dumps(emojis, ensure_ascii=False) if emojis else None


def has_threat_signal_emoji(emojis: list[str]) -> bool:
    return any(e in THREAT_SIGNAL_EMOJI for e in emojis)


def process_emoji(text: str) -> tuple[str, list[str], bool]:
    emojis = extract_emoji(text)
    clean = strip_emoji(text)
    threat_flag = has_threat_signal_emoji(emojis)
    return clean, emojis, threat_flag