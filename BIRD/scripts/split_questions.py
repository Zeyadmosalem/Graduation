import argparse
import json
from math import ceil
from pathlib import Path


def split_list(items, parts):
    n = len(items)
    if parts <= 1 or n == 0:
        return [items]
    # Contiguous near-equal chunks
    base = n // parts
    extra = n % parts
    chunks = []
    start = 0
    for i in range(parts):
        size = base + (1 if i < extra else 0)
        end = start + size
        chunks.append(items[start:end])
        start = end
    return chunks


def split_file(path: Path, parts: int = 4):
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"Expected list at {path}")
    chunks = split_list(data, parts)
    stem = path.stem
    for i, chunk in enumerate(chunks, start=1):
        out = path.with_name(f"{stem}_part{i}of{parts}.json")
        out.write_text(json.dumps(chunk, ensure_ascii=False, indent=4), encoding="utf-8")
        print(f"Wrote {out} ({len(chunk)} items)")


def main():
    ap = argparse.ArgumentParser(description="Split question JSON into N chunks for team translation")
    ap.add_argument("paths", type=Path, nargs="+", help="JSON files to split")
    ap.add_argument("--parts", type=int, default=4, help="Number of chunks (default: 4)")
    args = ap.parse_args()
    for p in args.paths:
        split_file(p, args.parts)


if __name__ == "__main__":
    main()

