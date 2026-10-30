import unicodedata


def normalize_text(value: str) -> str:
    """Accent-insensitive search; dictionary identities still use NFC exact keys."""
    value = value.lower().replace("đ", "d")
    return "".join(c for c in unicodedata.normalize("NFD", value) if not unicodedata.combining(c))


def search_text(kanji: str, reading: str, meaning: str) -> str:
    return normalize_text(f"{kanji} {reading} {meaning}")
