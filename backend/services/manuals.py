"""Manual downloads use the same applicability assignments as knowledge scopes."""
from backend import db


def available(row):
    return (row.get('mobile_visible') and row.get('published') and row.get('status') == 'processed'
            and row.get('document_type') == 'owners_manual' and row.get('indexed_revision')
            and row['indexed_revision'] == row.get('source_revision') and row.get('chunk_count', 0) > 0)


def published_manuals():
    rows = db.all_rows('documents', mobile_visible=True, published=True,
                       status='processed', document_type='owners_manual')
    return [row for row in rows if available(row)]


def applicable(row, vehicle_id, associations):
    return row.get('vehicle_independent', False) or any(
        link['document_id'] == row['id'] and link['vehicle_id'] == vehicle_id
        for link in associations
    )
