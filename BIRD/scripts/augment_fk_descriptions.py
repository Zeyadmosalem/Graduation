import argparse
import csv
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class ColumnRef:
    table_idx: int
    name: str


def norm(s: str) -> str:
    if s is None:
        return ""
    # Normalize for robust matching across cases and separators
    return re.sub(r"[^a-z0-9]", "", s.strip().lower())


def tidy_text(s: str) -> str:
    if not s:
        return ""
    # Collapse whitespace, trim, and normalize trailing punctuation spacing
    s = re.sub(r"\s+", " ", s).strip()
    # Remove duplicate trailing periods
    s = re.sub(r"\.*$", ".", s).rstrip()
    return s


def build_table_desc_map(db_dir: Path) -> Dict[str, Dict[str, str]]:
    """
    Build mapping: normalized_table_name -> { normalized_column_name -> column_description }
    from database_description/*.csv files.
    """
    table_to_cols: Dict[str, Dict[str, str]] = {}
    desc_dir = db_dir / "database_description"
    if not desc_dir.exists():
        return table_to_cols

    for csv_path in sorted(desc_dir.glob("*.csv")):
        table_key = norm(csv_path.stem)
        try:
            def read_csv_with_fallback(path: Path) -> List[Dict[str, str]]:
                # Try utf-8-sig, then cp1252 as fallback for odd encodings
                encodings = ["utf-8-sig", "utf-8", "cp1252", "latin-1"]
                last_exc: Optional[Exception] = None
                for enc in encodings:
                    try:
                        with path.open(newline="", encoding=enc) as f:
                            reader = csv.DictReader(f)
                            return list(reader)
                    except Exception as e:
                        last_exc = e
                        continue
                raise last_exc or Exception("Unknown CSV read error")

            rows = read_csv_with_fallback(csv_path)
            col_map: Dict[str, str] = {}
            for row in rows:
                orig_name = (row.get("original_column_name") or row.get("original") or "").strip()
                col_name = (row.get("column_name") or "").strip()
                desc = (row.get("column_description") or row.get("description") or "").strip()
                # Prefer original_column_name for matching; fall back to column_name
                for cand in [orig_name, col_name]:
                    key = norm(cand)
                    if key:
                        # Do not overwrite a non-empty description with an empty one
                        if key not in col_map or (desc and not col_map[key]):
                            col_map[key] = desc
            if col_map:
                table_to_cols[table_key] = col_map
        except Exception as e:
            # Continue on per-file errors, but note them to stderr
            print(f"WARN: Failed reading {csv_path}: {e}", file=sys.stderr)
    return table_to_cols


def find_db_dir(base_dirs: List[Path], db_id: str) -> Optional[Path]:
    target = norm(db_id)
    for base in base_dirs:
        if not base.exists():
            continue
        # Typical layout: <base>/<db_id>
        direct = base / db_id
        if direct.exists():
            return direct
        # Fuzzy match inside base
        for p in base.iterdir():
            if p.is_dir() and norm(p.name) == target:
                return p
    return None


def load_json(path: Path):
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def augment_split(
    split: str,
    tables_json: Path,
    db_roots: List[Path],
    out_json: Optional[Path] = None,
    in_place: bool = False,
) -> Path:
    data = load_json(tables_json)
    out_path = tables_json if in_place else (
        out_json
        or tables_json.with_name(tables_json.stem + "_with_fk_desc" + tables_json.suffix)
    )

    updated = 0
    missing_fk_desc = 0
    missing_col_desc_total = 0

    for db in data:
        db_id = db.get("db_id")
        if not db_id:
            continue

        # Map indices to ColumnRef for convenience
        col_names_orig: List[List] = db.get("column_names_original", [])
        tables_orig: List[str] = db.get("table_names_original", [])

        def idx_to_ref(idx: int) -> ColumnRef:
            t_idx, col = col_names_orig[idx]
            return ColumnRef(t_idx, col)

        # Skip if no FKs
        fks: List[List[int]] = db.get("foreign_keys", [])
        if not fks:
            db.setdefault("foreign_key_descriptions", [])

        # Locate DB folder and build description map
        db_dir = find_db_dir(db_roots, db_id)
        table_desc_map: Dict[str, Dict[str, str]] = {}
        if db_dir:
            table_desc_map = build_table_desc_map(db_dir)

        # Foreign key descriptions
        fk_descs = []
        if fks:
            for pair in fks:
                try:
                    child_idx, parent_idx = pair
                except Exception:
                    # Some entries may be nested or malformed
                    continue
                child = idx_to_ref(child_idx)
                parent = idx_to_ref(parent_idx)
                child_table = tables_orig[child.table_idx]
                parent_table = tables_orig[parent.table_idx]

                child_desc = ""
                parent_desc = ""
                if table_desc_map:
                    c_tbl_map = table_desc_map.get(norm(child_table))
                    if c_tbl_map:
                        child_desc = c_tbl_map.get(norm(child.name), "")
                    p_tbl_map = table_desc_map.get(norm(parent_table))
                    if p_tbl_map:
                        parent_desc = p_tbl_map.get(norm(parent.name), "")

                if not child_desc and not parent_desc:
                    missing_fk_desc += 1

                # Build concise, non-redundant summary
                first = f"{child_table}.{child.name} references {parent_table}.{parent.name}."
                c = (child_desc or "").strip()
                p = (parent_desc or "").strip()
                # Avoid redundancy if one contains the other (case/space-insensitive)
                c_norm = norm(c)
                p_norm = norm(p)
                parts: List[str] = [first]
                if c and (not p_norm or c_norm != p_norm) and (p_norm not in c_norm):
                    parts.append(c)
                elif p:
                    parts.append(p)
                # Join and tidy
                summary = " ".join(p for p in parts if p)
                summary = tidy_text(summary)

                fk_descs.append(
                    {
                        "child_table": child_table,
                        "child_column": child.name,
                        "parent_table": parent_table,
                        "parent_column": parent.name,
                        "child_description": child_desc,
                        "parent_description": parent_desc,
                        "summary": summary,
                        "usage": f"Foreign key linking {child_table}.{child.name} to {parent_table}.{parent.name}",
                    }
                )

        db["foreign_key_descriptions"] = fk_descs

        # Column descriptions aligned with column_names_original
        col_descs: List[str] = []
        for t_idx, col_name in col_names_orig:
            if t_idx == -1:
                col_descs.append("")
                continue
            table_name = tables_orig[t_idx]
            desc = ""
            if table_desc_map:
                tbl_map = table_desc_map.get(norm(table_name))
                if tbl_map:
                    desc = tbl_map.get(norm(col_name), "")
            if not desc:
                missing_col_desc_total += 1
            col_descs.append(desc)

        db["column_descriptions"] = col_descs
        updated += 1

    save_json(out_path, data)
    print(
        f"[{split}] Augmented {updated} DBs. Missing FK descriptions: {missing_fk_desc}. Missing column descriptions: {missing_col_desc_total}.")
    return out_path


def guess_defaults(root: Path, split: str) -> Tuple[Path, List[Path]]:
    if split == "train":
        tables_json = root / "BIRD" / "train" / "train_tables.json"
        db_roots = [root / "BIRD" / "train" / "train_databases" / "train_databases"]
    else:
        # dev path varies; default to dev_*/dev_tables.json and dev_databases*
        # Try a common location and auto-extract zip if needed
        dev_dir = root / "BIRD" / "dev_20240627"
        tables_json = dev_dir / "dev_tables.json"
        db_root = dev_dir / "dev_databases"
        if not db_root.exists():
            zip_path = dev_dir / "dev_databases.zip"
            if zip_path.exists():
                try:
                    import zipfile
                    with zipfile.ZipFile(zip_path) as zf:
                        zf.extractall(dev_dir)
                except Exception as e:
                    print(f"WARN: Failed to extract {zip_path}: {e}", file=sys.stderr)
        db_roots = [db_root, dev_dir]
    return tables_json, db_roots


def main():
    ap = argparse.ArgumentParser(description="Augment BIRD tables JSON with FK descriptions from CSVs.")
    ap.add_argument("--root", type=Path, default=Path.cwd(), help="Project root containing BIRD/")
    ap.add_argument("--split", choices=["train", "dev", "both"], required=True)
    ap.add_argument("--tables-json", type=Path, default=None, help="Path to train/dev _tables.json")
    ap.add_argument("--db-root", type=Path, action="append", default=None, help="Database root(s) to search for <db_id>/database_description")
    ap.add_argument("--out-json", type=Path, default=None, help="Output JSON path (default: *_with_fk_desc.json)")
    ap.add_argument("--in-place", action="store_true", help="Overwrite the input JSON in place")
    args = ap.parse_args()

    def run_one(split_name: str, tables_override: Optional[Path], out_override: Optional[Path], db_root_override: Optional[List[Path]]):
        tables_json, db_roots = guess_defaults(args.root, split_name)
        if tables_override:
            tables_json = tables_override
        if db_root_override:
            db_roots = db_root_override

        if not tables_json.exists():
            print(f"ERROR: Tables JSON not found: {tables_json}", file=sys.stderr)
            sys.exit(1)

        db_roots = [p for p in db_roots if p.exists()]
        if not db_roots:
            print("WARN: No existing database roots found. Will produce summaries without CSV descriptions.", file=sys.stderr)

        out_path = augment_split(
            split=split_name,
            tables_json=tables_json,
            db_roots=db_roots,
            out_json=out_override,
            in_place=args.in_place,
        )
        print(f"Wrote: {out_path}")

    if args.split == "both":
        # Run for train then dev; allow independent overrides only if provided explicitly per run
        run_one("train", args.tables_json if args.tables_json and "train" in str(args.tables_json).lower() else None,
                args.out_json if args.out_json and "train" in str(args.out_json).lower() else None,
                args.db_root)
        run_one("dev", args.tables_json if args.tables_json and "dev" in str(args.tables_json).lower() else None,
                args.out_json if args.out_json and "dev" in str(args.out_json).lower() else None,
                args.db_root)
    else:
        run_one(args.split, args.tables_json, args.out_json, args.db_root)


if __name__ == "__main__":
    main()
