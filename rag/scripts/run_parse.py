from pathlib import Path
from rag.app.parsing.html_tree import HTMLParser, save_tree

INPUT_DIR = Path("output/parse")


def parse_html_files():
    parser = HTMLParser()

    html_files = sorted(INPUT_DIR.glob("*.html"))

    if not html_files:
        print(f"No HTML files found in: {INPUT_DIR}")
        return

    for html_file in html_files:
        tree = parser.parse(html_file)

        output_file = INPUT_DIR / f"{html_file.stem}_html_tree.json"

        save_tree(
            tree=tree,
            output_file=output_file,
        )

        print(f"Generated JSON: {output_file}")


if __name__ == "__main__":
    parse_html_files()
