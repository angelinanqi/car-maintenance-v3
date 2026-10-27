"""Render physical PDF pages with the PDFium already installed beside MinerU."""
import argparse
from hashlib import sha256
import json
from pathlib import Path

import pypdfium2 as pdfium


def render(source, output, pages):
    output.mkdir(parents=True, exist_ok=True)
    digest = sha256(source.read_bytes()).hexdigest()
    records = []
    with pdfium.PdfDocument(str(source)) as document:
        for number in sorted(set(pages)):
            if number < 1 or number > len(document):
                raise ValueError('Physical page number is outside the original PDF')
            target = output / f'page-{number:05d}.png'
            # The caller uses a directory keyed by source bytes. Reuse complete
            # page renders; interrupted writes never replace the final file.
            if not target.is_file():
                page = document[number - 1]
                try:
                    width, height = page.get_size()
                    scale = 1800 / max(width, height)
                    bitmap = page.render(scale=scale)
                    try:
                        image = bitmap.to_pil()
                        image.save(target.with_suffix('.tmp'), format='PNG')
                        image.close()
                    finally:
                        bitmap.close()
                finally:
                    page.close()
                target.with_suffix('.tmp').replace(target)
            records.append({'page': number, 'path': target.name,
                            'sha256': sha256(target.read_bytes()).hexdigest()})
    report = {'source_sha256': digest, 'pages': records, 'long_edge_pixels': 1800}
    staged = output / 'pages.tmp'
    staged.write_text(json.dumps(report), encoding='utf-8')
    staged.replace(output / 'pages.json')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--pages', type=int, nargs='+', required=True)
    args = parser.parse_args()
    render(args.source, args.output, args.pages)
