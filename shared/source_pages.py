"""Physical source-page assets; no inferred caption or neighbouring-page links."""
from hashlib import sha256
import math
import re
import shutil

from shared.source_elements import image_path


def element_page(element):
    pages = element.get('pages', [])
    if (element.get('provenance_available') and len(pages) == 1
            and type(pages[0]) is int and pages[0] > 0):
        return pages[0]
    return None


def element_region(element):
    """Return one known-unit source rectangle, never infer it from its size.

    MinerU content-list v1 exports [left, top, right, bottom] on a 0..1000
    top-left scale. Older manifests call those boxes mineru-native; accept
    that marker only with an exact matching v1 source record.
    """
    page = element_page(element)
    if page is None:
        return None
    regions = set()
    for item in element.get('bounding_boxes', []):
        box = item.get('bbox')
        if (item.get('page') != page or not isinstance(box, list) or len(box) != 4
                or any(type(value) not in (int, float) or not math.isfinite(value) for value in box)
                or not (0 <= box[0] < box[2] <= 1000 and 0 <= box[1] < box[3] <= 1000)):
            return None
        units = item.get('coordinate_system')
        if units == 'mineru-native':
            matched = any(record.get('schema') == 'mineru_content_list_v1'
                          and type(record.get('page_idx')) is int and record['page_idx'] == page - 1
                          and record.get('bbox') == box for record in element.get('source_records', []))
            if not matched:
                return None
        elif units != 'normalized_1000':
            return None
        regions.add(tuple(box))
    return list(next(iter(regions))) if len(regions) == 1 else None


def page_assets(manifest):
    """Validate the page catalogue before using paths or content-addressed keys."""
    assets = manifest.get('page_assets', [])
    if assets and not re.fullmatch(r'[0-9a-f]{64}', manifest.get('source_sha256', '')):
        raise ValueError('Source-page assets require the original PDF hash')
    result = {}
    for asset in assets:
        page = asset['page']
        if (type(page) is not int or page < 1 or page in result
                or not re.fullmatch(r'[0-9a-f]{64}', asset['asset_sha256'])):
            raise ValueError('Invalid or duplicate source-page asset')
        image_path(asset['asset_path'])
        result[page] = asset
    return result


def copy_page_assets(manifest, extraction, destination):
    """Reuse the same checked copying for normal indexing and isolated replays."""
    for asset in page_assets(manifest).values():
        source = extraction / image_path(asset['asset_path'])
        if sha256(source.read_bytes()).hexdigest() != asset['asset_sha256']:
            raise ValueError('Source page does not match its recorded hash')
        destination.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination / asset['asset_sha256'])
