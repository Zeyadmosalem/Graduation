# Arabic-BIRD: Schema-Enriched Arabic Extension of the BIRD Text-to-SQL Benchmark

## Overview
This repository introduces **Arabic-BIRD**, a schema-enriched Arabic extension of the BIRD Text-to-SQL benchmark. The aim is to advance research in **cross-lingual semantic parsing** and provide a high-quality Arabic dataset for Text-to-SQL tasks.

This release targets research in **multilingual Text-to-SQL**, **semantic parsing**, **schema linking**, and **cross-lingual generalization**.

---

## Contributions
This work provides the community with:

### ✅ 1. Arabic-BIRD Dataset (New Resource)
A high-quality Arabic version of the BIRD Text-to-SQL dataset (train/dev), including aligned English–Arabic question and evidence pairs.

### 🧠 2. Schema-Enriched Cross-Lingual Annotation Pipeline
A reproducible methodology for enriching database schemas with column semantics and foreign-key context to enhance cross-lingual understanding.

### 🌍 3. Extension of BIRD with Schema Context for Arabic
An augmented version of BIRD incorporating column-level descriptions and FK usage summaries for improved schema linking and reasoning.

---

## Contributors

### 👨‍💻 Core Development
- **[@AbdelrahmanAboegela](https://github.com/AbdelrahmanAboegela)** - Lead Developer
  - ✅ **Phase 1**: Schema Enrichment (Completed)
  - ✅ **Phase 2**: Gold Graph Generation (Completed)
  - 🛠️ Pipeline Architecture & Implementation

### 🌍 Translation Team
The following contributors are working on **Phase 3: Arabic Translation**:

- **[@ibrahim-abd-elmotteleb](https://github.com/ibrahim-abd-elmotteleb)** — Ibrahim Abdelmotteleb (Translator)
- **[@SHEhabDevPro](https://github.com/SHEhabDevPro)** — Shehab Ahmed Mohamed Farrag (Translator)
- **[@Zeyadmosalem](https://github.com/Zeyadmosalem)** — Zeyad Salem (Translator)
- **[@gina925](https://github.com/gina925)** — Gina (Translator)

*Status: Translation work is currently in progress with distributed human translation across balanced dataset chunks.*

---

## Project Phases
| Phase | Status | Description | Contributors |
|--------|---------|----------------|--------------|
| **Phase 1: Schema Enrichment** | ✅ Completed | Added column semantics and FK context to BIRD schemas | [@AbdelrahmanAboegela](https://github.com/AbdelrahmanAboegela) |
| **Phase 2: Gold Graph Generation** | ✅ Completed | Built structural join graphs for each SQL instance | [@AbdelrahmanAboegela](https://github.com/AbdelrahmanAboegela) |
| **Phase 3: Arabic Translation** | 🚧 In Progress | Human translation of `question_ar` and `evidence_ar` fields |  [Translation Team](#-translation-team) |

---

## Methodology
The pipeline systematically enriches and translates the BIRD dataset through the following stages:

### **Schema Enrichment (Phase 1)**
For each database in BIRD train/dev:
- Extract table descriptions from CSV files using multi-encoding fallback
- Map: `table → column → description`
- Resolve FK pairs into child/parent relations and attach:
  - semantic summaries
  - usage context
- Generate `*_tables_with_fk_desc.json`

### **Gold Graph Generation (Phase 2)**
- Construct table–column graphs per example to surface join paths and schema traversal
- Provide an interactive visualization for researchers and annotators

### **Arabic Translation (Phase 3)**
- Normalize question structure to include `question_en`, `question_ar`, `evidence_en`, `evidence_ar`
- Split dataset into four balanced subsets for distributed human translation

---

## Reproducibility
All scripts are provided for full reproducibility.

### Phase 1 — Schema Enrichment
```bash
python BIRD/scripts/augment_fk_descriptions.py --split train
python BIRD/scripts/augment_fk_descriptions.py --split dev
python BIRD/scripts/augment_fk_descriptions.py --split both
```

### Phase 2 — Gold Graph Generation
Requires: `pip install sqlglot networkx`
```bash
python BIRD/scripts/build_gold_graphs.py --split both
```
Outputs:
- `BIRD/train/train_gold_graphs.json`
- `BIRD/dev_20240627/dev_gold_graphs.json`

### Optional Viewer
```bash
pip install pyvis
python BIRD/graph_viewer/server.py
```
Navigate to: http://127.0.0.1:8081

### Phase 3 — Translation Utilities
Normalize bilingual fields:
```bash
python BIRD/scripts/add_ar_field.py
```
Split into 4 translator chunks:
```bash
python BIRD/scripts/split_questions.py BIRD/train/train.json \
  BIRD/dev_20240627/dev.json BIRD/dev_20240627/dev_tied_append.json --parts 4
```

---

## Repository Structure
```
BIRD/
 ├─ train/
 │   ├─ train_tables.json
 │   ├─ train_tables_with_fk_desc.json
 │   ├─ train.json
 │   └─ train_part{1..4}of4.json
 │
 ├─ dev_20240627/
 │   ├─ dev_tables.json
 │   ├─ dev_tables_with_fk_desc.json
 │   ├─ dev.json
 │   ├─ dev_tied_append.json
 │   ├─ dev_part{1..4}of4.json
 │   └─ dev_tied_append_part{1..4}of4.json
 │
 ├─ scripts/
 │   ├─ augment_fk_descriptions.py
 │   ├─ add_ar_field.py
 │   ├─ split_questions.py
 │   └─ build_gold_graphs.py
 │
 └─ graph_viewer/
     ├─ server.py
     └─ static/
```

---

## Notes
- Missing column descriptions remain empty, but FK summaries preserve relational meaning
- Column matching is robust and encoding-agnostic
- Fully offline processing — no external downloads required

---

## Future Work
- Complete Arabic translation for all fields
- Provide Arabic schema summaries (`summary_ar`, `column_description_ar`)
- Release evaluation benchmarks for Arabic Text-to-SQL
- Prepare a research paper submission with evaluation results

---

## Diagrams

### 1) Project Pipeline Overview
```mermaid
flowchart LR
    A["Start"] --> B["Step 1: Schema Enrichment (Completed)"]
    B --> C["Step 2: Gold Graph Generation (Completed)"]
    C --> D["Step 3: Translation (In Progress)"]
    style B fill:#d7ffd9,stroke:#0a0,color:#000
    style C fill:#d7ffd9,stroke:#0a0,color:#000
    style D fill:#fff7cc,stroke:#cc9a06,color:#000
```

### 2) Schema Enrichment Process
```mermaid
flowchart TD
    S1[Load *_tables.json] --> S2[Locate database_description/*.csv]
    S2 --> S3{Read CSV with fallback<br/>utf-8 → utf-8-sig → cp1252 → latin-1}
    S3 --> S4[Map table → columns → descriptions]
    S4 --> S5[Resolve FK pairs to child/parent columns]
    S5 --> S6[Attach FK summaries + usage]
    S4 --> S7[Populate column_descriptions aligned to column_names_original]
    S6 --> S8[Write *_with_fk_desc.json]
    S7 --> S8

    style S1 fill:#cfe8ff,stroke:#0077cc,color:#000
    style S2 fill:#fff7cc,stroke:#cc9a06,color:#000
    style S3 fill:#fff7cc,stroke:#cc9a06,color:#000
    style S4 fill:#fff7cc,stroke:#cc9a06,color:#000
    style S5 fill:#fff7cc,stroke:#cc9a06,color:#000
    style S6 fill:#fff7cc,stroke:#cc9a06,color:#000
    style S7 fill:#fff7cc,stroke:#cc9a06,color:#000
    style S8 fill:#d7ffd9,stroke:#0a0,color:#000

```

### 3) Parallel Translation Workflow
```mermaid
flowchart TD
    T1[Questions JSON] --> T2[Split into 4 balanced chunks]
    T2 --> T3A[Team A Translations]
    T2 --> T3B[Team B Translations]
    T2 --> T3C[Team C Translations]
    T2 --> T3D[Team D Translations]
    T3A --> T4[Merge Arabic fields]
    T3B --> T4
    T3C --> T4
    T3D --> T4

    style T1 fill:#cfe8ff,stroke:#0077cc,color:#000
    style T2 fill:#fff7cc,stroke:#cc9a06,color:#000
    style T3A fill:#fff7cc,stroke:#cc9a06,color:#000
    style T3B fill:#fff7cc,stroke:#cc9a06,color:#000
    style T3C fill:#fff7cc,stroke:#cc9a06,color:#000
    style T3D fill:#fff7cc,stroke:#cc9a06,color:#000
    style T4 fill:#d7ffd9,stroke:#0a0,color:#000

```

### 4) Data Structure Transformation
```mermaid
flowchart LR
    D1[Original BIRD<br/>train/dev tables + questions]
        --> D2[Augmented Schemas<br/>*_tables_with_fk_desc.json]
        --> D3[Normalized Questions<br/>question_en/ar, evidence_en/ar]
        --> D4[Gold Graphs<br/>train/dev_gold_graphs.json]

    style D1 fill:#cfe8ff,stroke:#0077cc,color:#000
    style D2 fill:#fff7cc,stroke:#cc9a06,color:#000
    style D3 fill:#fff7cc,stroke:#cc9a06,color:#000
    style D4 fill:#d7ffd9,stroke:#0a0,color:#000

```

### 5) System Architecture
```mermaid
graph TD
    subgraph Inputs
      I1[BIRD train/dev tables]
      I2[BIRD train/dev questions]
    end

    subgraph Processing Scripts
      P1[augment_fk_descriptions.py]
      P2[add_ar_field.py]
      P3[split_questions.py]
      P4[build_gold_graphs.py]
    end

    subgraph Outputs
      O1[*_tables_with_fk_desc.json]
      O2[train/dev normalized questions]
      O3[train/dev question chunks]
      O4[train/dev_gold_graphs.json]
    end

    I1 --> P1 --> O1
    I2 --> P2 --> O2
    O2 --> P3 --> O3
    O1 --> P4
    O2 --> P4 --> O4

    style I1 fill:#cfe8ff,stroke:#0077cc,color:#000
    style I2 fill:#cfe8ff,stroke:#0077cc,color:#000
    style P1 fill:#fff7cc,stroke:#cc9a06,color:#000
    style P2 fill:#fff7cc,stroke:#cc9a06,color:#000
    style P3 fill:#fff7cc,stroke:#cc9a06,color:#000
    style P4 fill:#fff7cc,stroke:#cc9a06,color:#000
    style O1 fill:#d7ffd9,stroke:#0a0,color:#000
    style O2 fill:#d7ffd9,stroke:#0a0,color:#000
    style O3 fill:#d7ffd9,stroke:#0a0,color:#000
    style O4 fill:#d7ffd9,stroke:#0a0,color:#000

```

## License
This repository includes derived metadata from the BIRD dataset. Please adhere to the original BIRD licensing terms for redistribution and usage.
