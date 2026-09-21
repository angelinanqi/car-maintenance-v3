import argparse
from pathlib import Path
from rag.app.youtube.retrieval import retrieve_youtube, group_by_video, timestamp_url


def main():
    parser = argparse.ArgumentParser(
        description="Inspect YouTube retrieval; lower distance means a closer match."
    )
    parser.add_argument("query")
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of candidate chunks before grouping",
    )
    parser.add_argument("--group-by-video", action="store_true")
    parser.add_argument(
        "--chroma-path", type=Path, default=Path("output/embeddings/chroma")
    )

    args = parser.parse_args()

    try:
        results = retrieve_youtube(args.query, args.top_k, args.chroma_path)
    except Exception as error:
        parser.exit(1, f"YouTube query failed: {error}\n")

    if args.group_by_video:
        results = group_by_video(results)

    if not results:
        print("No indexed YouTube chunks. Run YouTube ingestion first.")

    for rank, result in enumerate(results, 1):
        metadata = result["metadata"]
        print(
            f"\n{rank}. {metadata['video_title']} | distance={result['distance']:.4f}"
        )
        print(
            f"{metadata['language']} | {metadata['start_seconds']:.1f}-{metadata['end_seconds']:.1f}s"
        )
        print(result["text"][:500])
        print(timestamp_url(metadata["video_id"], metadata["start_seconds"]))


if __name__ == "__main__":
    main()
