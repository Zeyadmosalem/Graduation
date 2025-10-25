import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple, Set, Optional


def require_deps():
    try:
        import sqlglot  # noqa: F401
        import networkx  # noqa: F401
    except Exception as e:
        raise SystemExit(
            "Missing dependencies. Install: pip install sqlglot networkx\n"
            f"Import error: {e}"
        )


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=4), encoding="utf-8")


def build_schema_maps(schema_entry: dict):
    table_names = schema_entry.get("table_names") or schema_entry.get("table_names_original") or []
    col_names = schema_entry.get("column_names") or schema_entry.get("column_names_original") or []
    col_descs = schema_entry.get("column_descriptions") or []
    fk_pairs = schema_entry.get("foreign_keys") or []
    fk_descs = schema_entry.get("foreign_key_descriptions") or []

    idx_to_ref: Dict[int, Tuple[str, str]] = {}
    table_to_cols: Dict[str, List[Tuple[str, str]]] = defaultdict(list)

    for i, (t_idx, c_name) in enumerate(col_names):
        if t_idx == -1:
            idx_to_ref[i] = ("*", "*")
            continue
        tname = table_names[t_idx]
        idx_to_ref[i] = (tname, c_name)
        desc = col_descs[i] if i < len(col_descs) else ""
        table_to_cols[tname].append((c_name, desc))

    fk_desc_map: Dict[Tuple[str, str, str, str], str] = {}
    for d in fk_descs:
        key = (
            d.get("child_table", ""),
            d.get("child_column", ""),
            d.get("parent_table", ""),
            d.get("parent_column", ""),
        )
        fk_desc_map[key] = d.get("summary") or d.get("usage") or ""

    # Also index symmetric lookup (parent->child) because SQL conditions may not reflect FK direction
    fk_desc_map_rev: Dict[Tuple[str, str, str, str], str] = {}
    for (ct, cc, pt, pc), desc in fk_desc_map.items():
        fk_desc_map_rev[(pt, pc, ct, cc)] = desc

    return idx_to_ref, table_to_cols, fk_desc_map, fk_desc_map_rev


def parse_sql(sql: str):
    from sqlglot import parse_one, exp
    ast = None
    # Try a few likely dialects to improve robustness
    for dialect in ("sqlite", "mysql", "tsql", "postgres", None):
        try:
            ast = parse_one(sql, read=dialect, error_level="IGNORE")
            if ast is not None:
                break
        except Exception:
            ast = None
    if ast is None:
        return None

    # alias->table and set of explicit table tokens
    alias_to_table: Dict[str, str] = {}
    tables_in_from: List[str] = []
    def _alias_name(a):
        # sqlglot may return TableAlias node or a raw string for aliases
        if a is None:
            return None
        return getattr(a, "name", a)

    for t in ast.find_all(exp.Table):
        name = t.name
        alias = _alias_name(t.alias)
        if name:
            tables_in_from.append(name)
            alias_to_table[name] = name
        if alias:
            alias_to_table[alias] = name or alias

    # Collect column equality join conditions (WHERE or ON):
    # handle EQ comparisons where both sides are Columns
    join_pairs: List[Tuple[Optional[str], str, Optional[str], str]] = []
    for eq in ast.find_all(exp.EQ):
        left, right = eq.left, eq.right
        if isinstance(left, exp.Column) and isinstance(right, exp.Column):
            ltab = left.table
            rtab = right.table
            lname = left.name
            rname = right.name
            if lname and rname:
                join_pairs.append((ltab, lname, rtab, rname))

    # Handle USING/NATURAL joins
    using_edges: List[Tuple[str, str, str, List[str]]] = []
    last_left_alias: Optional[str] = None
    from_node = ast.find(exp.From)
    if from_node and isinstance(from_node.this, exp.Table):
        base = from_node.this
        last_left_alias = _alias_name(base.alias) or base.name
    for j in ast.find_all(exp.Join):
        right = j.this
        right_alias = None
        if isinstance(right, exp.Table):
            right_alias = _alias_name(right.alias) or right.name
        using = j.args.get("using")
        natural = j.args.get("natural")
        if right_alias and (using or natural):
            # Determine real table names for left and right via alias mapping
            # left refers to the last_left_alias seen
            if last_left_alias and right_alias:
                left_table = alias_to_table.get(last_left_alias, last_left_alias)
                right_table = alias_to_table.get(right_alias, right_alias)
                # If USING: list of column identifiers
                cols = []
                if using and hasattr(using, "expressions"):
                    cols = [c.name for c in using.expressions if getattr(c, "name", None)]
                elif natural:
                    # NATURAL: use intersection of column names
                    cols = None  # We'll resolve later when schema is available
                using_edges.append((left_table, right_table, right_alias, cols or []))
            # Update last_left_alias for chaining
        if right_alias:
            last_left_alias = right_alias

    # Collect all column references to help include single-table queries
    columns: List[Tuple[Optional[str], str]] = []
    for c in ast.find_all(exp.Column):
        columns.append((c.table, c.name))

    return alias_to_table, join_pairs, using_edges, tables_in_from, columns


def build_gold_for_record(rec: dict, schema: dict):
    # Maps
    idx_to_ref, table_to_cols, fk_desc_map, fk_desc_map_rev = build_schema_maps(schema)
    parsed = parse_sql(rec.get("SQL", "")) or ({}, [], [], [], [])
    alias_to_table, join_pairs, using_edges, tables_in_from, columns = parsed

    # Resolve tables referenced by FROM/JOIN and joins/columns
    tables_needed: Set[str] = set()
    # Include explicit tables from FROM/JOIN
    for name in tables_in_from:
        if name in table_to_cols:
            tables_needed.add(name)
    edges: List[Dict] = []

    # EQ-based joins
    for ltab, lname, rtab, rname in join_pairs:
        lt = alias_to_table.get(ltab or "", ltab or "")
        rt = alias_to_table.get(rtab or "", rtab or "")
        if not lt or not rt:
            continue
        tables_needed.update([lt, rt])
        # Prefer FK description if matches either direction
        desc = fk_desc_map.get((lt, lname, rt, rname)) or fk_desc_map_rev.get((lt, lname, rt, rname)) or ""
        edges.append({
            "child_table": lt,
            "child_column": lname,
            "parent_table": rt,
            "parent_column": rname,
            "description": desc,
        })

    # USING/NATURAL joins: we only add after we know shared columns. We'll approximate by shared names in schema
    for left_table, right_table, _alias, cols in using_edges:
        if not left_table or not right_table:
            continue
        tables_needed.update([left_table, right_table])
        left_cols = {c for c, _ in table_to_cols.get(left_table, [])}
        right_cols = {c for c, _ in table_to_cols.get(right_table, [])}
        shared = cols or list(left_cols.intersection(right_cols))
        for cname in shared:
            desc = fk_desc_map.get((left_table, cname, right_table, cname)) or fk_desc_map_rev.get((left_table, cname, right_table, cname)) or ""
            edges.append({
                "child_table": left_table,
                "child_column": cname,
                "parent_table": right_table,
                "parent_column": cname,
                "description": desc,
            })

    # Include tables implied by referenced columns (helps single-table queries without joins)
    for t_alias, col in columns:
        if t_alias:
            real = alias_to_table.get(t_alias, t_alias)
            if real in table_to_cols:
                tables_needed.add(real)
        else:
            owners = [t for t, cols in table_to_cols.items() if any(cn == col for cn, _ in cols)]
            if len(owners) == 1:
                tables_needed.add(owners[0])

    # If nothing inferred yet, fallback: scan SQL for schema table names (whole words)
    if not tables_needed:
        sql_l = (rec.get("SQL", "") or "").lower()
        for t in table_to_cols.keys():
            try:
                if re.search(r"\b" + re.escape(t.lower()) + r"\b", sql_l):
                    tables_needed.add(t)
            except re.error:
                # Skip exotic names that break regex
                continue

    # Build nodes with all columns+descriptions
    nodes = []
    for t in sorted(tables_needed):
        cols = [{"name": cn, "description": desc} for (cn, desc) in table_to_cols.get(t, [])]
        nodes.append({"table_name": t, "columns": cols})

    # Deduplicate edges
    seen = set()
    deduped = []
    for e in edges:
        key = (e["child_table"], e["child_column"], e["parent_table"], e["parent_column"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(e)

    # Context text (English only for now)
    lines = []
    for n in nodes:
        cols_text = ", ".join([f"{c['name']}: {c['description']}" if c['description'] else c['name'] for c in n["columns"]])
        lines.append(f"Table {n['table_name']}: {cols_text}")
    if deduped:
        lines.append("Relationships:")
        for e in deduped:
            desc = f" ({e['description']})" if e.get('description') else ""
            lines.append(f"{e['child_table']}.{e['child_column']} → {e['parent_table']}.{e['parent_column']}{desc}")
    context_text = "\n".join(lines)

    return {
        "db_id": rec.get("db_id"),
        "question_en": rec.get("question_en") or rec.get("question") or "",
        "question_ar": rec.get("question_ar", ""),
        "SQL": rec.get("SQL", ""),
        "gold_graph": {"nodes": nodes, "edges": deduped},
        "context_text": context_text,
    }


def process_split(root: Path, split: str):
    if split == "train":
        tables_path = root / "train" / "train_tables_with_fk_desc.json"
        q_paths = [root / "train" / "train.json"]
        out_path = root / "train" / "train_gold_graphs.json"
    else:
        tables_path = root / "dev_20240627" / "dev_tables_with_fk_desc.json"
        q_paths = [root / "dev_20240627" / "dev.json", root / "dev_20240627" / "dev_tied_append.json"]
        out_path = root / "dev_20240627" / "dev_gold_graphs.json"

    schemas = load_json(tables_path)
    db_map = {d["db_id"]: d for d in schemas}

    results = []
    for q_path in q_paths:
        if not q_path.exists():
            continue
        questions = load_json(q_path)
        for rec in questions:
            db_id = rec.get("db_id")
            schema = db_map.get(db_id)
            if not schema:
                continue
            results.append(build_gold_for_record(rec, schema))

    save_json(out_path, results)
    print(f"Wrote: {out_path} ({len(results)} records)")


def main():
    ap = argparse.ArgumentParser(description="Build gold graphs per question using actual SQL joins only.")
    ap.add_argument("--split", choices=["train", "dev", "both"], required=True)
    args = ap.parse_args()

    require_deps()

    root = Path(__file__).resolve().parents[1]
    if args.split in ("train", "both"):
        process_split(root, "train")
    if args.split in ("dev", "both"):
        process_split(root, "dev")


if __name__ == "__main__":
    main()
