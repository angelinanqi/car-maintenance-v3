import json


def print_diagnostics(result):
    details = result["diagnostics"]
    print("Routing:")
    print(json.dumps(details["routing"], indent=2))
    
    if result["route"] not in {"rag", "rag_with_external_warning"}:
        print("Manual and YouTube retrieval skipped for this route.")
        return

    manual = details["manual"]
    generation = details["generation"]
    
    print("\nManual retrieval:")
    print(f"Retrieved chunk count: {len(manual['chunks'])}")
    print(f"Distance metric: {manual['metric']} (lower is better)")
    print("Manual relevance threshold: none; supporting evidence is selected from all chunks.")
    
    for chunk in manual["chunks"]:
        print(f"  [{chunk['rank']}] {chunk['id']} | distance={chunk['distance']}")
        
    print(f"Final manual relevance: {result['manual_relevant']}")
    print(f"Reason: {generation['decision_reason']}")
    print(f"Supporting excerpt: {generation['supporting_excerpt'] or '(none)'}")
    print("\nActual manual context passed to the answer LLM:")
    print(result["context"] or "(empty; manual generation skipped)")
    print("\nRaw answer LLM output:")
    print(generation["raw_generation"] or "(not called)")

    youtube = details["youtube"]
    
    print("\nYouTube retrieval:")
    print(f"Indexed chunks: {youtube['indexed_chunks']}")
    print(f"Distance metric: {youtube['metric']} (lower is better)")
    print(f"Similarity threshold: {youtube['threshold']} (higher is better)")
    print(f"Raw candidate count: {len(youtube['raw_chunks'])}")
    
    for chunk in youtube["raw_chunks"]:
        metadata = chunk["metadata"]
        print(f"\n{metadata.get('video_title', metadata['video_id'])} | id={chunk['id']}")
        print(f"distance={chunk['distance']} | similarity={chunk['score']}")
        print(f"Timestamp: {metadata.get('start_seconds', 'unavailable (metadata-only)')}")
        print(f"Content type: {metadata.get('retrieval_content', 'unknown')}")
        print(chunk["text"])
        
    print("\nGrouped videos (best chunk per video, before threshold/best-score filtering):")
    for video in youtube["grouped_videos"]:
        print(f"{video['metadata']['video_id']} | distance={video['distance']} | similarity={video['score']}")
        
    print(f"Final YouTube relevance: {youtube['relevant']} - {youtube['reason']}")
    print("\nActual YouTube results passed to recommendation logic (not to the answer LLM):")
    print(json.dumps(details["recommendation_context"], indent=2, ensure_ascii=False))
