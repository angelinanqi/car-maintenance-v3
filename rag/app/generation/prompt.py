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


def build_prompt(
    query: str,
    context: str,
) -> str:
    if not query.strip():
        raise ValueError("Query cannot be empty.")

    if not context.strip():
        raise ValueError("Context cannot be empty.")

    return f"""You are answering questions about a vehicle owner's manual.

Use the provided manual context to answer the user's question.

Rules:
- Use the manual context as the source of truth.
- Do not invent information that is not supported by the context.
- If the context does not contain enough information to answer the question, say so clearly.
- Answer directly and clearly.
- Do not mention the retrieval process unless necessary.

User question:
{query}

Manual context:
{context}
"""
