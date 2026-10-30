from pathlib import Path
from sqlalchemy import func, select
from backend.catalogue import catalogue_info, seed_words
from backend.constants import MAX_WORDS
from backend.models import User, Vocabulary, Word
from backend.seed import populate_user
from backend.services.words import make_word
from scripts.build_n2_seed import build


def make_user(db):
    user = User(email="seed@example.com", name="Seed test", password_hash="unused")
    db.add(user)
    db.flush()
    return user


def test_source_translations_are_unique_and_reproducible():
    words = seed_words()
    assert len(words) == len({(w.kanji, w.reading) for w in words}) == 1617
    assert Path("backend/seed.json").read_text(encoding="utf-8") == build()
    lookup = {(w.kanji, w.reading): w.meaning for w in words}
    assert lookup["工夫", "くふう"] == "Sự tìm tòi; nghĩ cách làm hiệu quả"
    assert lookup["統計", "とうけい"] == "Thống kê"
    assert lookup["努める", "つとめる"] == "Nỗ lực; cố gắng"
    assert ("ローマ字", "ろーまじ") in lookup


def test_population_is_idempotent_and_preserves_overrides(database):
    with database.begin() as db:
        user = make_user(db)
        original = make_word(user.id, seed_words()[0])
        original.meaning = "Nghĩa riêng"
        original.marked_for_review, original.seen, original.correct = True, 7, 2
        db.add(original)
        db.flush()
        assert populate_user(db, user).added == 1616
        assert db.scalar(select(func.count()).select_from(Word)) == 1
        assert populate_user(db, user, apply=True).after == 1617
        assert populate_user(db, user, apply=True).added == 0
        db.refresh(original)
        assert (original.meaning, original.marked_for_review, original.seen, original.correct) == (
            "Nghĩa riêng",
            True,
            7,
            2,
        )
        assert user.revision == 1
        assert db.scalar(select(func.count()).select_from(Vocabulary)) == 1617


def test_population_honors_capacity(database):
    with database.begin() as db:
        user = make_user(db)
        db.add_all(
            Word(
                user_id=user.id, kanji=f"個人語句{i}", reading="こじん", meaning="Từ riêng", note=""
            )
            for i in range(MAX_WORDS - 1)
        )
        db.flush()
        result = populate_user(db, user, apply=True)
        assert result.added == 1 and result.after == MAX_WORDS
        assert result.skipped_capacity == len(seed_words()) - 1
        assert populate_user(db, user, apply=True).added == 0


def test_catalogue_metadata_and_schema_contract(client):
    metadata = client.get("/api/catalogue").json()
    assert metadata == catalogue_info()
    assert metadata["limits"]["max_words"] == MAX_WORDS
    assert client.get(metadata["credits_url"]).status_code == 200
    schema = client.get("/openapi.json").json()
    assert (
        schema["paths"]["/api/study/actions"]["post"]["requestBody"]["content"]["application/json"][
            "schema"
        ]["discriminator"]["propertyName"]
        == "action"
    )
    assert schema["paths"]["/api/workspace"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]["$ref"].endswith("WorkspaceOut")
