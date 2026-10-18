"""Rebuild assistance from elements.json or a saved sources manifest; no OCR."""
import argparse
import json
from pathlib import Path
from rag.app.maintenance.assistance import prepare, extract_items, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--selection', type=Path, help='Explicit confirmed table/column selections')
    parser.add_argument('--catalogue', type=Path, help='Optional JSON list of standard maintenance items')
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
    path = prepare(manifest, args.output_dir)
    print(path)
    if args.selection:
        catalogue = json.loads(path.read_text(encoding='utf-8'))
        selection = json.loads(args.selection.read_text(encoding='utf-8'))
        items = json.loads(args.catalogue.read_text(encoding='utf-8')) if args.catalogue else []
        result = extract_items(catalogue, selection, items)
        # Generated suggestions are disposable. Never write admin review decisions here.
        suggestions_path = path.with_name(path.stem + '.suggestions.json')
        write_json(suggestions_path, result)
        print(suggestions_path)


if __name__ == '__main__':
    main()
