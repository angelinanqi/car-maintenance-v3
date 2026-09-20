from pathlib import Path
from rag.app.normalization.builder import normalize_file

PROJECT_ROOT = Path(__file__).resolve().parents[2]
INPUT_DIR = PROJECT_ROOT / "output" / "parse"
OUTPUT_DIR = PROJECT_ROOT / "output" / "nodes"

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
