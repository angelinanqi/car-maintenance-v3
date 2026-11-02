from backend.settings import MINERU_BACKEND, MINERU_TIMEOUT, MINERU_API_URL, EXTRACTION_MAX_BYTES
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from backend.settings import MINERU_EXECUTABLE, OUTPUT_DIR

# Run MinerU once per document name; retain Markdown, images and provenance JSON.


def _complete(markdown: Path) -> bool:
    if not markdown.is_file() or not (markdown.parent / "images").is_dir():
        return False

    text = markdown.read_text(encoding="utf-8")
    references = re.findall(r'images/[^\s)"<>]+', text)

    version = markdown.parent / 'extraction-version.txt'
    return version.is_file() and version.read_text(encoding='utf-8').strip() == '2' and bool(text.strip()) and all(
        (markdown.parent / path).is_file() for path in references
    )


def run_ocr(
    pdf_path: str | Path,
    output_dir: str | Path = OUTPUT_DIR / "ocr",
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

    executable = mineru_executable or MINERU_EXECUTABLE

    if not executable:
        local = Path(sys.executable).parent / (
            "mineru.exe" if os.name == "nt" else "mineru"
        )

        executable = str(local) if local.is_file() else "mineru"

    root.mkdir(parents=True, exist_ok=True)
    log_path = root / f"{source.stem}.mineru.log"
    # prevents old output from being mistaken for this run's result, and removes all intermediate files even after failure
    with tempfile.TemporaryDirectory(prefix=".mineru-", dir=root) as temporary:
        work = Path(temporary)
        raw = work / "raw"
        print(f"Running MinerU: {source}")

        # Keep diagnostics outside the temporary directory so failures remain inspectable.
        if MINERU_API_URL and mineru_executable is None:
            from backend.services.ocr_client import extract_remote
            extract_remote(source, raw, root / f'{source.stem}.mineru-job.json',
                           url=MINERU_API_URL, backend=MINERU_BACKEND,
                           timeout=MINERU_TIMEOUT, max_bytes=EXTRACTION_MAX_BYTES)
        else:
            _run_local(executable, source, raw, log_path)

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
        metadata = clean / 'metadata'
        metadata.mkdir()
        for index, path in enumerate(sorted(raw.rglob('*.json'))):
            shutil.copy2(path, metadata / f'{index:03d}-{path.name}')
        (clean / 'extraction-version.txt').write_text('2', encoding='utf-8')

        if not _complete(clean / markdown.name):
            raise ValueError(f"MinerU output has missing image files for {source.name}")

        # only replace this document's incomplete cache after successful OCR
        if destination.exists():
            shutil.rmtree(destination)
        clean.rename(destination)
    return markdown


def _run_local(executable, source, raw, log_path):
    with log_path.open("wb") as log:
        try:
            subprocess.run(
                [str(executable), "-p", str(source), "-o", str(raw), "-b", MINERU_BACKEND],
                check=True,
                timeout=MINERU_TIMEOUT,
                # MinerU's API client defaults to a separate one-hour wait.
                # The backend's configured deadline owns this whole job.
                env={**os.environ, "MINERU_TASK_RESULT_TIMEOUT_SECONDS": str(MINERU_TIMEOUT)},
                stdout=log,
                stderr=subprocess.STDOUT,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
            log.flush()
            with log_path.open("rb") as saved_log:
                saved_log.seek(max(0, log_path.stat().st_size - 1600))
                details = saved_log.read().decode("utf-8", errors="replace").strip()
            if isinstance(error, subprocess.TimeoutExpired):
                reason = f"timed out after {MINERU_TIMEOUT:g} seconds"
            else:
                reason = f"failed with exit code {error.returncode}"
            raise RuntimeError(
                f"MinerU {reason}. Log: {log_path}\n{details}"
            ) from error
