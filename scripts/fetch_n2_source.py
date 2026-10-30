"""Download a reproducible OpenJLPT N2 snapshot (data only, never executed)."""

import hashlib
import argparse
import json
import subprocess
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / ".runtime" / "vocabulary-sources"
REPOSITORY = "evanclan/OpenJLPT"


def fetch(url):
    with urlopen(
        Request(url, headers={"User-Agent": "Kotoba-vocabulary-import/1.0"}), timeout=30
    ) as response:
        return response.read()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--latest",
        action="store_true",
        help="Resolve current upstream main instead of the recorded snapshot.",
    )
    args = parser.parse_args()
    DEST.mkdir(parents=True, exist_ok=True)
    metadata = ROOT / "backend" / "data" / "catalogue.json"
    if metadata.exists() and not args.latest:
        commit = json.loads(metadata.read_text(encoding="utf-8"))["commit"]
    else:
        # Avoid GitHub REST rate limits; resolve only this public branch, no checkout.
        commit = subprocess.check_output(
            ["git", "ls-remote", f"https://github.com/{REPOSITORY}.git", "refs/heads/main"],
            text=True,
        ).split()[0]
    manifest = {"repository": f"https://github.com/{REPOSITORY}", "commit": commit, "files": {}}
    for path in ("data/json/vocab/n2.json", "LICENSE", "NOTICE.md", "README.md"):
        data = fetch(f"https://raw.githubusercontent.com/{REPOSITORY}/{commit}/{path}")
        (DEST / Path(path).name).write_bytes(data)
        manifest["files"][path] = hashlib.sha256(data).hexdigest()
        print(path, len(data), "bytes")
    (DEST / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print("Pinned source commit:", commit)


if __name__ == "__main__":
    main()
