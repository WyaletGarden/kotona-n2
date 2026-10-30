"""Add missing catalogue words without overwriting vocabulary, progress or active sessions.

Preview: python -m backend.seed --all-users
Apply:   python -m backend.seed --all-users --apply
"""

import argparse
import json
from dataclasses import asdict, dataclass
from sqlalchemy import select
from sqlalchemy.orm import Session
from .catalogue import ensure_shared_catalogue, seed_words
from .constants import MAX_WORDS
from .db import SessionLocal
from .models import User, Vocabulary, Word


@dataclass(frozen=True)
class SeedResult:
    user_id: str
    before: int
    added: int
    already_present: int
    skipped_capacity: int
    after: int


def populate_user(
    db: Session, user: User, *, apply: bool = False, bump_revision: bool = True
) -> SeedResult:
    """Caller must lock the user row before applying and own the transaction."""
    existing = set(
        db.execute(select(Word.kanji, Word.reading).where(Word.user_id == user.id)).tuples()
    )
    catalogue = seed_words()
    missing = [word for word in catalogue if (word.kanji, word.reading) not in existing]
    available = max(0, MAX_WORDS - len(existing))
    adding = missing[:available]
    if apply and adding:
        from .services.words import make_word

        ensure_shared_catalogue(db)
        shared = {(v.kanji, v.reading): v for v in db.scalars(select(Vocabulary))}
        db.add_all(
            make_word(user.id, word, shared.get((word.kanji, word.reading))) for word in adding
        )
        if bump_revision:
            user.revision += 1
        db.flush()
    return SeedResult(
        user.id,
        len(existing),
        len(adding),
        len(catalogue) - len(missing),
        len(missing) - len(adding),
        len(existing) + len(adding),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--all-users", action="store_true")
    target.add_argument("--user-id", help="Only populate this account UUID.")
    parser.add_argument(
        "--apply", action="store_true", help="Commit additions; otherwise preview only."
    )
    args = parser.parse_args()
    results = []
    with SessionLocal.begin() as db:
        query = select(User).order_by(User.id)
        if args.user_id:
            query = query.where(User.id == args.user_id)
        if args.apply:
            # Same account lock as API writes: imports cannot race with learning/edits.
            query = query.with_for_update()
        users = list(db.scalars(query))
        if args.user_id and not users:
            raise SystemExit("Account not found; nothing changed.")
        for user in users:
            results.append(populate_user(db, user, apply=args.apply))
    print(
        json.dumps(
            {
                "mode": "applied" if args.apply else "preview",
                "catalogue_size": len(seed_words()),
                "accounts": len(results),
                "added_total": sum(r.added for r in results),
                "results": [asdict(r) for r in results],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
