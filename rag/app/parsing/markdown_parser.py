from pathlib import Path
from mistletoe.html_renderer import HtmlRenderer
from mistletoe.block_token import Document
from bs4 import BeautifulSoup
from shared.text_normalization import normalize_unicode


def render_section_path(section_path: list[str]) -> list[str]:
    """Render raw extraction headings with the same renderer as prose headings."""
    titles = []
    with HtmlRenderer() as renderer:
        for title in section_path:
            html = renderer.render(Document("# " + normalize_unicode(title) + "\n"))
            titles.append(BeautifulSoup(html, "html.parser").get_text().strip())
    return titles


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
