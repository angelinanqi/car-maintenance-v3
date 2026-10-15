from pathlib import Path
from mistletoe.html_renderer import HtmlRenderer
from mistletoe.block_token import Document



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
