"""One source of truth for application limits and learning rules."""

MAX_WORDS = 2000
PAGE_SIZE = 50
MAX_PAGE_SIZE = 100
IMPORT_BYTES = 1_000_000
REQUEST_BYTES = 4_000_000
KANJI_LENGTH = 80
READING_LENGTH = 120
MEANING_LENGTH = 300
NOTE_LENGTH = 600
PASSWORD_MIN = 10
PASSWORD_MAX = 128
MASTERED_STREAK = 2
REVIEW_DAYS = (1, 3, 7, 14, 30)


def public_limits():
    return {
        "max_words": MAX_WORDS,
        "page_size": PAGE_SIZE,
        "max_page_size": MAX_PAGE_SIZE,
        "import_bytes": IMPORT_BYTES,
        "kanji_length": KANJI_LENGTH,
        "reading_length": READING_LENGTH,
        "meaning_length": MEANING_LENGTH,
        "note_length": NOTE_LENGTH,
        "password_min": PASSWORD_MIN,
        "password_max": PASSWORD_MAX,
        "mastered_streak": MASTERED_STREAK,
    }
