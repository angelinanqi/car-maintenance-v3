import json
from pathlib import Path
from rag.app.normalization.builder import SemanticBuilder

PROJECT_ROOT = Path(__file__).resolve().parents[2]

INPUT_DIR = PROJECT_ROOT / "output" / "parse"
OUTPUT_DIR = PROJECT_ROOT / "output" / "nodes"


def normalize_file(
    input_file: Path,
    output_file: Path,
) -> None:

    with input_file.open(
        "r",
        encoding="utf-8",
    ) as file:
        html_tree = json.load(file)

    document_name = input_file.stem.removesuffix("_html_tree")

    builder = SemanticBuilder()

    document = builder.build(
        html_tree,
        document_name,
    )

    with output_file.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            document.to_dict(),
            file,
            indent=4,
            ensure_ascii=False,
        )


def main() -> None:
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    input_files = sorted(INPUT_DIR.glob("*.json"))

    for input_file in input_files:
        output_file = OUTPUT_DIR / input_file.name

        normalize_file(
            input_file,
            output_file,
        )

        print(f"Normalized: {input_file.name}")


if __name__ == "__main__":
    main()
