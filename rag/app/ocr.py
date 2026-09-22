import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

# run MinerU once per document name and retain only markdown and images


def _complete(markdown: Path) -> bool:
    if not markdown.is_file() or not (markdown.parent / "images").is_dir():
        return False

    text = markdown.read_text(encoding="utf-8")
    references = re.findall(r'images/[^\s)"<>]+', text)

    return bool(text.strip()) and all(
        (markdown.parent / path).is_file() for path in references
    )


def run_ocr(
    pdf_path: str | Path,
    output_dir: str | Path = "output/ocr",
    *,
    mineru_executable: str | Path | None = None,
) -> Path:

    source = Path(pdf_path).resolve()

    if source.suffix.lower() != ".pdf":
        raise ValueError(f"Expected a PDF file: {source}")

    if not source.is_file():
        raise FileNotFoundError(f"PDF does not exist: {source}")

    root = Path(output_dir).resolve()
    destination = root / source.stem

    if destination.resolve().parent != root:
        raise ValueError(f"OCR destination must be a document directory inside {root}")

    markdown = destination / f"{source.stem}.md"

    if _complete(markdown):
        print(f"Reusing OCR: {source.stem}")
        return markdown

    executable = mineru_executable or os.environ.get("MINERU_EXECUTABLE")

    if not executable:
        local = Path(sys.executable).parent / (
            "mineru.exe" if os.name == "nt" else "mineru"
        )

        executable = str(local) if local.is_file() else "mineru"

    root.mkdir(parents=True, exist_ok=True)
    # prevents old output from being mistaken for this run's result, and removes all intermediate files even after failure
    with tempfile.TemporaryDirectory(prefix=".mineru-", dir=root) as temporary:
        work = Path(temporary)
        raw = work / "raw"
        print(f"Running MinerU: {source}")

        subprocess.run(
            [str(executable), "-p", str(source), "-o", str(raw), "-b", "pipeline"],
            check=True,
        )

        candidates = sorted(raw.rglob("*.md"))
        matching = [path for path in candidates if path.stem == source.stem]
        candidates = matching or candidates

        if len(candidates) != 1:
            raise ValueError(
                f"Expected one MinerU Markdown output for {source.name}; found {len(candidates)}"
            )

        generated = candidates[0]

        if not generated.read_text(encoding="utf-8").strip():
            raise ValueError(f"MinerU produced empty Markdown for {source.name}")

        clean = work / "clean"
        clean.mkdir()
        images = generated.parent / "images"

        if images.is_dir():
            shutil.copytree(images, clean / "images")
        else:
            if "images/" in generated.read_text(encoding="utf-8"):
                raise ValueError(
                    f"MinerU output references a missing images directory: {generated}"
                )
            (clean / "images").mkdir()

        shutil.copy2(generated, clean / markdown.name)

        if not _complete(clean / markdown.name):
            raise ValueError(f"MinerU output has missing image files for {source.name}")

        # only replace this document's incomplete cache after successful OCR

        if destination.exists():
            shutil.rmtree(destination)
        clean.rename(destination)
    return markdown
