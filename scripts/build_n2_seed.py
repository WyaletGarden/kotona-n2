"""Build the offline, attributed vocabulary catalogue from its pinned source and translations."""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.schemas import WordInput
from backend.constants import MAX_WORDS

DATA = ROOT / "backend" / "data"
OUTPUT = ROOT / "backend" / "seed.json"


def build():
    metadata = json.loads((DATA / "catalogue.json").read_text(encoding="utf-8"))
    starter = json.loads((DATA / "starter.json").read_text(encoding="utf-8"))
    sources = json.loads((DATA / "n2-source.json").read_text(encoding="utf-8"))
    translations = {}
    for line in (DATA / "n2-vi.tsv").read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        source_id, meaning = line.split("\t", 1)
        if source_id in translations or not meaning.strip():
            raise ValueError(f"Duplicate or empty translation: {source_id}")
        translations[source_id] = meaning
    if set(translations) != {row["id"] for row in sources}:
        raise ValueError("Source and translation IDs do not match exactly.")
    rows = starter + [
        dict(kanji=row["kanji"], reading=row["reading"], meaning=translations[row["id"]], note="")
        for row in sources
    ]
    validated = [WordInput.model_validate(row).model_dump() for row in rows]
    keys = {(row["kanji"], row["reading"]) for row in validated}
    if len(keys) != len(validated) or len(validated) > MAX_WORDS:
        raise ValueError("Duplicate vocabulary or library capacity exceeded.")
    if not all(re.search("[\u3400-\u4dbf\u4e00-\u9fff々]", row["kanji"]) for row in validated):
        raise ValueError("A vocabulary item has no kanji.")
    if (
        len(starter) != metadata["starter_entries"]
        or len(sources) != metadata["added_entries"]
        or len(rows) != metadata["total_entries"]
    ):
        raise ValueError("Catalogue counts do not match the provenance manifest.")
    return json.dumps(validated, ensure_ascii=False, indent=2) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="Verify generated seed without writing files."
    )
    args = parser.parse_args()
    content = build()
    if args.check:
        if OUTPUT.read_text(encoding="utf-8") != content:
            raise SystemExit(
                "seed.json differs from the validated source/translations. Rebuild it."
            )
    else:
        OUTPUT.write_text(content, encoding="utf-8")
    print(
        f"Validated {len(json.loads(content))} vocabulary items; SHA-256 {hashlib.sha256(content.encode()).hexdigest()}"
    )


if __name__ == "__main__":
    main()
