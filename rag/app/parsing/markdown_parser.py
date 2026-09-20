from pathlib import Path
from mistletoe.html_renderer import HtmlRenderer
from mistletoe.block_token import Document

INPUT_DIR = Path("output/cleaning")
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


def parse_markdown_files(input_dir: Path = INPUT_DIR, output_dir: Path = OUTPUT_DIR):
    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    markdown_files = sorted(input_dir.glob("*.md"))

    if not markdown_files:
        raise FileNotFoundError(
            f"No cleaned Markdown files found in: {input_dir}. Run rag.scripts.run_clean first."
        )

    for markdown_file in markdown_files:
        document_name = markdown_file.stem

        output_file = output_dir / f"{document_name}.html"

        convert_markdown_to_html(
            markdown_file=markdown_file,
            output_file=output_file,
        )

        print(f"Generated HTML: {output_file}")


if __name__ == "__main__":
    parse_markdown_files()
