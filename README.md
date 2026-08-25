# car-maintenance-v3
Latest version of FYP, focus on RAG pipeline only

# RAG Pipeline: Stage 1 — Parsing

Stage 1 ingests finalized Markdown manual files, converts them to structured HTML, and parses them into hierarchical `HTMLNode` trees serialized as JSON.

> **Note:** OCR processing happens upstream and is out of scope for this stage.

---

## Directory Layout

```text
rag_project/
├── data/markdown/         # Input: Raw .md files (e.g., axia-2023.md)
└── output/parse/          # Output: Generated .html and _html_tree.json files

```

---

## Core Components

* **`app/models/html_node.py`**
Defines the `HTMLNode` schema. Captures document context, tag hierarchies, text content, parent-child relationships, depth, and source position.
* **`app/parsing/markdown_parser.py`**
Handles the core Markdown-to-HTML transformation.
* **`app/parsing/html_tree.py`**
Parses raw HTML into a structured `HTMLNode` object model while preserving heading hierarchy and metadata.
* **`scripts/run_parsing.py`**
Executes the HTML-to-`HTMLNode` JSON conversion stage.

---

## Running the Parsing Stage

Place your target Markdown files in `data/markdown/`, then execute the following from the project root:

**Step 1: Convert Markdown to HTML**

```bash
python -m app.parsing.markdown_parser

```

*Reads from `data/markdown/*.md` and writes intermediate `.html` files to `output/parse/`.*

**Step 2: Convert HTML to HTMLNode JSON**

```bash
python -m scripts.run_parsing

```

*Reads `.html` files from `output/parse/` and outputs `<document_name>_html_tree.json` (consumed by **Stage 2: Normalization**).*

> ⚠️ **Order Matters:** Step 1 must be run before Step 2. `run_parsing.py` expects the raw HTML files to already exist in `output/parse/`.

---

## Planned Architecture Refactor

Currently, Stage 1 requires running two separate commands. The target design is to have `scripts/run_parsing.py` orchestrate both steps internally:

```bash
python -m scripts.run_parsing
# Target execution flow: Markdown -> HTML -> HTMLNode JSON

```

*`markdown_parser.py` will remain a reusable module inside `app/parsing/`, but `run_parsing.py` will serve as the single CLI entry point for the stage.*

---

## Dependencies

Ensure the following are included in your `requirements.txt`:

* `mistletoe`
* `beautifulsoup4`