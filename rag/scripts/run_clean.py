from pathlib import Path
from rag.app.cleaning.cleaner import MarkdownCleaner

INPUT_DIR = Path("data/markdown")
OUTPUT_DIR = Path("output/cleaning")
REPORT_DIR = OUTPUT_DIR / "reports"


def main() -> None:
    if not INPUT_DIR.exists():
        raise FileNotFoundError(f"Input directory does not exist: {INPUT_DIR}")

    markdown_files = sorted(INPUT_DIR.glob("*.md"))

    if not markdown_files:
        print(f"No Markdown files found in {INPUT_DIR}")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    cleaner = MarkdownCleaner(malay_threshold=0.97)

    for input_path in markdown_files:
        document_name = input_path.stem

        output_path = OUTPUT_DIR / input_path.name
        report_path = REPORT_DIR / f"{document_name}.json"

        print(f"\nCleaning: {input_path.name}")

        report = cleaner.clean_file(input_path, output_path, report_path)

        print(f"  Output: {output_path}")
        print(f"  Report: {report_path}")
        print(f"  Malay blocks removed: " f"{len(report.malay_blocks_removed)}")
        print(f"  Duplicate lines removed: " f"{len(report.duplicate_lines_removed)}")
        print(f"  OCR garbage removed: " f"{len(report.garbage_removed)}")

    print("\nCleaning complete.")


if __name__ == "__main__":
    main()
