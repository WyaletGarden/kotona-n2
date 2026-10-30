"""Validated vocabulary shared by registration and the idempotent seed command."""

import json
from functools import lru_cache
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5
from .schemas import WordInput
from .constants import MAX_WORDS, public_limits


@lru_cache
def seed_words() -> tuple[WordInput, ...]:
    raw = json.loads(Path(__file__).with_name("seed.json").read_text(encoding="utf-8"))
    words = tuple(WordInput.model_validate(row) for row in raw)
    keys = {(word.kanji, word.reading) for word in words}
    if not words or len(words) > MAX_WORDS or len(keys) != len(words):
        raise ValueError(f"The seed catalogue must contain 1–{MAX_WORDS} unique vocabulary items.")
    return words


@lru_cache
def catalogue_info() -> dict:
    metadata = json.loads(
        (Path(__file__).parent / "data" / "catalogue.json").read_text(encoding="utf-8")
    )
    return {
        "count": len(seed_words()),
        "added": metadata["added_entries"],
        "source": metadata["repository"],
        "commit": metadata["commit"],
        "license": metadata["license"],
        "license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
        "credits_url": "/vocabulary-credits.html",
        "scope": "Built-in vocabulary adapted from OpenJLPT; personal additions may have separate attribution.",
        "upstream_attribution": [
            "OpenJLPT contributors — https://github.com/evanclan/OpenJLPT",
            "Jonathan Waller — https://www.tanos.co.uk/jlpt/",
            "JMdict / EDRDG — https://www.edrdg.org/jmdict/j_jmdict.html",
        ],
        "adaptations": metadata["adaptations"],
        "limits": public_limits(),
    }


@lru_cache
def vocabulary_records() -> tuple[dict, ...]:
    rows = json.loads(
        (Path(__file__).parent / "data" / "n2-source.json").read_text(encoding="utf-8")
    )
    source_keys = {(r["kanji"], r["reading"]): f"openjlpt:{r['id']}" for r in rows}
    return tuple(
        {
            "id": str(uuid5(NAMESPACE_URL, f"kotoba:vocabulary:{w.kanji}|{w.reading}")),
            **w.model_dump(),
            "source_key": source_keys.get((w.kanji, w.reading), "kotoba:starter"),
        }
        for w in seed_words()
    )


def ensure_shared_catalogue(db):
    """Concurrent registrations reuse stable catalogue IDs, without updating user data."""
    from sqlalchemy import select
    from .models import Vocabulary

    existing = set(db.scalars(select(Vocabulary.id)))
    missing = [r for r in vocabulary_records() if r["id"] not in existing]
    if missing:
        if db.get_bind().dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import insert
        else:
            from sqlalchemy.dialects.sqlite import insert
        db.execute(insert(Vocabulary).values(missing).on_conflict_do_nothing(index_elements=["id"]))
