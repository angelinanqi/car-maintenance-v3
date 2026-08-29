from pathlib import Path
from rag.app.database.client import get_supabase_client
from rag.app.database.importer import import_directory

INPUT_DIR = Path("output/nodes")
OUTPUT_DIR = Path("output/database")


def main() -> None:
    supabase = get_supabase_client()

    import_directory(
        supabase=supabase,
        input_dir=INPUT_DIR,
        output_dir=OUTPUT_DIR,
    )


if __name__ == "__main__":
    main()
