import json
from pathlib import Path


def add_ar_field(path: Path, key: str = "question_ar") -> bool:
    if not path.exists():
        print(f"WARN: not found: {path}")
        return False
    # Try common encodings
    data = None
    for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            data = json.loads(path.read_text(encoding=enc))
            break
        except Exception:
            data = None
    if data is None or not isinstance(data, list):
        print(f"WARN: not a list: {path}")
        return False
    changed = False
    for item in data:
        if isinstance(item, dict) and key not in item:
            item[key] = ""
            changed = True
    if changed:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=4), encoding="utf-8")
    return changed


def main():
    root = Path(__file__).resolve().parents[1]  # BIRD/
    targets = [
        root / "train" / "train.json",
        root / "dev_20240627" / "dev.json",
        root / "dev_20240627" / "dev_tied_append.json",
    ]
    any_changed = False
    for p in targets:
        changed = add_ar_field(p)
        print(f"{p}: {'updated' if changed else 'no change'}")
        any_changed = any_changed or changed
    if not any_changed:
        print("No files changed (field already present everywhere)")


if __name__ == "__main__":
    main()

