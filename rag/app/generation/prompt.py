from rag.app.retrieval.search import RetrievalResult


def build_context(
    results: list[RetrievalResult],
) -> str:
    if not results:
        return "No relevant manual content was retrieved."

    context_parts = []

    for result in results:
        metadata = result.metadata

        document_name = metadata.get(
            "document_name",
            "Unknown document",
        )

        section_path = metadata.get(
            "section_path",
            "",
        )

        node_type = metadata.get(
            "node_type",
            "",
        )

        header = f"Document: {document_name}"

        if section_path:
            header += f"\nSection: {section_path}"

        if node_type:
            header += f"\nContent type: {node_type}"

        # current chunks already carry document/section/content labels. Keep a fallback for imported or older chunks without those prefixes.
        text = result.text
        if not text.startswith("Document: "):
            text = f"{header}\n\nContent:\n{text}"
        context_parts.append(f"[{result.rank}]\n{text}")

    return "\n\n---\n\n".join(context_parts)