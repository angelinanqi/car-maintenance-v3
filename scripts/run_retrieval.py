from pathlib import Path
from app.database.client import get_supabase_client
from app.database.retriever import retrieve_documents

OUTPUT_DIR = Path("output/retrieval")


def main() -> None:
    supabase = get_supabase_client()

    retrieve_documents(
        supabase=supabase,
        output_dir=OUTPUT_DIR,
    )


if __name__ == "__main__":
    main()
