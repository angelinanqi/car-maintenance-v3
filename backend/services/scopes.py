"""Resolve published knowledge through database associations on every request."""
from fastapi import HTTPException
from backend import db
from backend.services import content_sources


def resolve(scope_type, scope_id, *, require_available=True):
    if scope_type not in {"vehicle", "category"}:
        raise HTTPException(422, "Select a vehicle or category knowledge scope.")
    table = "knowledge_vehicles" if scope_type == "vehicle" else "guide_categories"
    scope = db.get(table, scope_id)
    published = scope.get("published" if scope_type == "vehicle" else "knowledge_published", False)
    if scope_type == 'category' and not scope.get('published', False):
        published = False
    if require_available and not published:
        raise HTTPException(409, "This knowledge scope is not published.")
    field = scope_type + "_id"
    links = db.all_rows("document_vehicles" if scope_type == "vehicle" else "document_categories",
                        **{field: str(scope_id)})
    ids = [link["document_id"] for link in links]
    documents = db.all_rows("documents", id=ids, status="processed") if ids else []
    documents = [d for d in documents if d.get("published", False) and d.get("chunk_count", 0) > 0 and d.get("indexed_revision")
                 and d["indexed_revision"] == d.get("source_revision")]
    content = content_sources.load(scope_type, scope_id)
    if require_available and not documents and not content:
        raise HTTPException(409, "This scope has no published reference content. Select another scope.")
    associations = db.all_rows("document_vehicles", document_id=[d["id"] for d in documents]) if documents else []
    vehicles = {v["id"]: v for v in db.all_rows("knowledge_vehicles")}
    metadata = {}
    for document in documents:
        applicable = [vehicles[link["vehicle_id"]] for link in associations
                      if link["document_id"] == document["id"] and link["vehicle_id"] in vehicles]
        metadata[document.get("index_document_name") or document["id"]] = {
            "document_id": document["id"], "document_title": document["name"],
            "document_type": document.get("document_type", "other_reference"),
            "vehicle_independent": document.get("vehicle_independent", False),
            "source_fidelity_verified": document.get("source_fidelity_verified", False),
            "year": document.get("year", ""), "engine": document.get("engine", ""),
            "variant": document.get("variant", ""), "applicable_vehicles": applicable,
            "index_revision": document["indexed_revision"],
            "indexed_chunk_count": document['chunk_count'],
        }
    videos = db.all_rows("knowledge_videos", **{field: str(scope_id)})
    return {"scope_type": scope_type, "scope_id": str(scope_id), "label": scope["name"],
            "vehicle": scope if scope_type == "vehicle" else None,
            "document_ids": list(metadata), "document_metadata": metadata,
            "content_sources": content,
            "video_ids": [v["video_id"] for v in videos], "published": published,
            "vehicle_codes": [v["code"] for v in vehicles.values()]}


def catalog(*, admin=False):
    result = []
    for kind, table in (("vehicle", "knowledge_vehicles"), ("category", "guide_categories")):
        for row in db.all_rows(table):
            scope = resolve(kind, row["id"], require_available=False)
            if admin or scope["published"]:
                result.append({"scope_type": kind, "scope_id": row["id"], "label": row["name"],
                               "code": row.get("code"), "published": scope["published"],
                               "available": scope["published"] and bool(scope["document_ids"] or scope['content_sources']),
                               "document_count": len(scope["document_ids"]),
                               "content_count": len(scope['content_sources'])})
    return result
