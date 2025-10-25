Project: BIRD Schema Context Augmentation

Overview
- Goal: Enrich BIRD train/dev table schemas with per-column meanings and clear foreign key (FK) usage to improve Text-to-SQL training (especially for ambiguous names like id or abbreviation).
- Output: New JSONs alongside the originals that add two fields per DB:
  - foreign_key_descriptions: For each FK pair, includes child/parent sides and a concise summary of how the FK links tables.
  - column_descriptions: One string per column (aligned with column_names_original) populated from per-table CSV descriptions.

Why this idea
- Ambiguous column names (e.g., id, code, abbreviation) frequently confuse Text-to-SQL models.
- The BIRD dataset already ships rich per-table, per-column descriptions in database_description/*.csv files.
- By programmatically joining these descriptions into the train/dev tables JSONs, we provide the model with explicit semantics and FK usage context at training time.

How it works
- For each DB in train/dev tables JSON:
  - Locate database_description/*.csv files by table name.
  - Build a map: table -> { column -> column_description } using robust normalization (case-insensitive, ignore separators) and encoding fallbacks (UTF-8, UTF-8-SIG, CP1252, Latin-1).
  - For foreign_keys (index pairs), resolve child/parent columns and attach a description object:
    - child_table, child_column, parent_table, parent_column
    - child_description, parent_description
    - summary: a concise sentence like "child.col references parent.col. {description}." with redundancy trimmed
    - usage: explicit linkage sentence
  - For all columns, populate column_descriptions aligned to column_names_original (empty string for the special [ -1, "*" ] row).

Reproducibility (How to run)
- Prerequisites: Python 3.8+ (no external packages required).
- Script path: scripts/augment_fk_descriptions.py
- Default locations assumed:
  - Train: BIRD/train/train_tables.json; DB roots under BIRD/train/train_databases/train_databases
  - Dev: BIRD/dev_20240627/dev_tables.json; DB roots under BIRD/dev_20240627/dev_databases (auto-extracts dev_databases.zip if present)

Commands
- Train only (writes train/train_tables_with_fk_desc.json):
  - python scripts/augment_fk_descriptions.py --split train
- Dev only (writes dev_20240627/dev_tables_with_fk_desc.json):
  - python scripts/augment_fk_descriptions.py --split dev
- Both splits (writes both outputs):
  - python scripts/augment_fk_descriptions.py --split both

Advanced options
- --in-place: overwrite the original _tables.json instead of creating a new file.
- --tables-json <path>: manually provide a tables JSON path (for non-standard layouts).
- --db-root <path>: add or override database roots (repeatable).
- --out-json <path>: set a custom output path.

Whatâ€™s inside this repo
- train/
  - train_tables.json (original BIRD train tables)
  - train_tables_with_fk_desc.json (augmented with FK + column descriptions)
  - train.json (original BIRD train questions)
- dev/
  - dev_tables.json (original BIRD dev tables)
  - dev_tables_with_fk_desc.json (augmented with FK + column descriptions)
  - dev.json (original BIRD dev questions)
  - dev_tied_append.json (BIRD dev additional questions)
- scripts/
  - augment_fk_descriptions.py (the automation script)

Notes and limitations
- If a description is missing in CSVs for a particular column, the corresponding entry in column_descriptions is left empty, and FK summaries use whichever side has a description available.
- The script normalizes names (case/space/underscore/hyphen) to match CSVs to JSON; exotic naming mismatches can still cause misses.
- No network is required. The dev databases zip is extracted locally if needed.

Extending / Arabic translation
- To support multilingual context, add a translation pass to produce summary_ar and/or column_description_ar using your preferred translation pipeline or glossary.
- The augmentation logic is deterministic given the same inputs and encodings, so post-translation fields can be layered on without changing the schema join logic.

License
- This repo includes derived metadata from the BIRD dataset. Please follow BIRDâ€™s terms for redistribution and use.

