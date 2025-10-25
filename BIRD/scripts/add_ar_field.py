import json
from pathlib import Path


def transform_item(item: dict) -> dict:
    # Prepare English/Arabic fields with defaults
    q_en = item.pop("question", item.get("question_en", ""))
    q_ar = item.get("question_ar", "")
    ev_en = item.pop("evidence", item.get("evidence_en", ""))
    ev_ar = item.get("evidence_ar", "")

    # Build new ordered dict: keep important fields first, then the rest
    ordered = {}
    # Common primary identifiers when present
    for k in ["question_id", "db_id"]:
        if k in item:
            ordered[k] = item[k]

    # Insert EN/AR pairs
    ordered["question_en"] = q_en
    ordered["question_ar"] = q_ar
    ordered["evidence_en"] = ev_en
    ordered["evidence_ar"] = ev_ar

    # Add SQL next if present
    if "SQL" in item:
        ordered["SQL"] = item["SQL"]

    # Preserve other known metadata in a stable order if present
    for k in ["difficulty"]:
        if k in item:
            ordered[k] = item[k]

    # Append any remaining keys not yet included
    for k, v in item.items():
        if k not in ordered:
            ordered[k] = v

    return ordered


def update_json(path: Path) -> bool:
    if not path.exists():
        print(f"WARN: not found: {path}")
        return False
    # Load with fallback encodings
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
    new_items = []
    for it in data:
        if not isinstance(it, dict):
            new_items.append(it)
            continue
        new_it = transform_item(dict(it))
        if new_it != it:
            changed = True
        new_items.append(new_it)

    if changed:
        path.write_text(json.dumps(new_items, ensure_ascii=False, indent=4), encoding="utf-8")
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
        changed = update_json(p)
        print(f"{p}: {'updated' if changed else 'no change'}")
        any_changed = any_changed or changed
    if not any_changed:
        print("No files changed (field already present everywhere)")


if __name__ == "__main__":
    main()
