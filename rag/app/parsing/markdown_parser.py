from pathlib import Path
from mistletoe import Document, HtmlRenderer

INPUT_DIR = Path("data/markdown")
OUTPUT_DIR = Path("output/parse")


def convert_markdown_to_html(
    markdown_file: Path,
    output_file: Path,
):
    with HtmlRenderer() as renderer:
        with markdown_file.open(
            "r",
            encoding="utf-8",
        ) as file:
            document = Document(file)
            html_output = renderer.render(document)

    output_file.write_text(
        html_output,
        encoding="utf-8",
    )


def parse_markdown_files():
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    markdown_files = sorted(INPUT_DIR.glob("*.md"))

    if not markdown_files:
        print(f"No Markdown files found in: {INPUT_DIR}")
        return

    for markdown_file in markdown_files:
        document_name = markdown_file.stem

        output_file = OUTPUT_DIR / f"{document_name}.html"

        convert_markdown_to_html(
            markdown_file=markdown_file,
            output_file=output_file,
        )

        print(f"Generated HTML: {output_file}")


if __name__ == "__main__":
    parse_markdown_files()
