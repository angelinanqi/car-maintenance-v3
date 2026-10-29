"""Collect bounded review evidence from the same records used by normal chat."""
import json
from shared.table_evidence import table_literal_text


def collect_trace(records, eligible, excluded, sources, diagnostics, client, elapsed_ms):
    labels = {record.chunk_id: f"S{index}" for index, record in enumerate(eligible, 1)}
    cited = {source.get("chunk_id") for source in sources if source.get("chunk_id")}
    cited_elements = {source.get("element_id") for source in sources if source.get("element_id")}
    reasons = {item.get("chunk_id"): item["reason"] for item in excluded if item.get("chunk_id")}
    unique = {record.chunk_id: record for record in records}
    ordered = sorted(unique.values(), key=lambda record: (record.chunk_id not in cited, record.chunk_id not in labels, record.rank))
    evidence = []
    for record in ordered[:20]:
        metadata = record.metadata
        kind = metadata.get("content_type", "paragraph")
        if kind not in {"paragraph", "table", "image"}:
            continue
        text = metadata.get("source_content") or record.text
        if kind == "table" and metadata.get("evidence_type") in {"table_cells_v1", "table_cells_v2"}:
            text = table_literal_text(json.loads(text))
        if not isinstance(text, str):
            text = json.dumps(text, ensure_ascii=False)
        section_path = metadata.get("section_path") or []
        if isinstance(section_path, str):
            section_path = json.loads(section_path)
        evidence.append({"document_id": metadata["document_id"], "source_revision": metadata["index_revision"],
            "chunk_id": record.chunk_id, "element_id": metadata.get("element_id"), "kind": kind,
            "label": labels.get(record.chunk_id), "section_path": section_path,
            "excerpt": text[:4000], "eligible": record.chunk_id in labels,
            "cited": record.chunk_id in cited or metadata.get("element_id") in cited_elements,
            "exclusion": reasons.get(record.chunk_id, "")[:300]})
    return {"evidence": evidence, "diagnostics": {
        "provider": client.provider, "model": client.model, "elapsed_ms": elapsed_ms,
        "reason": diagnostics.get("decision_reason", ""), "retrieved_count": len(records),
        "eligible_count": len(eligible), "evidence_truncated": len(ordered) > 20,
        "fallback_used": bool(client.fallback_reason)}}
