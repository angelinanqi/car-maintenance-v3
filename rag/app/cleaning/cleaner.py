import re
from app.cleaning.cleaning_report import CleaningReport
from app.cleaning.language_detector import LanguageDetector


class MarkdownCleaner:
    """
    Cleans Markdown while preserving Markdown structure.
    Cleaning order:
        Unicode normalization
        -> whitespace normalization
        -> Malay detection/removal
        -> Malay removal inside tables
        -> exact consecutive duplicate removal
        -> obvious OCR garbage removal
        -> final whitespace cleanup
    """

    def __init__(
        self,
        malay_threshold: float = 0.97,
    ) -> None:
        self.language_detector = LanguageDetector(malay_threshold=malay_threshold)

    def clean(
        self,
        markdown: str,
        document_name: str,
    ) -> tuple[str, CleaningReport]:
        report = CleaningReport(document_name=document_name)

        text = self._normalize_unicode(markdown)
        text = self._normalize_whitespace(text)

        lines = text.splitlines()

        lines = self._remove_malay(
            lines,
            report,
        )

        lines = self._remove_consecutive_duplicates(
            lines,
            report,
        )

        lines = self._remove_obvious_garbage(
            lines,
            report,
        )

        cleaned = self._final_whitespace_cleanup(lines)

        return cleaned, report

    def _normalize_unicode(self, text: str) -> str:
        """
        Unicode normalization.
        Avoids NFKC because technical manuals contain meaningful symbols, superscripts, model numbers, etc.
        """
        replacements = {
            "\u2018": "'",
            "\u2019": "'",
            "\u201c": '"',
            "\u201d": '"',
            "\u2013": "-",
            "\u2014": "-",
            "\u00a0": " ",
        }

        for old, new in replacements.items():
            text = text.replace(old, new)

        # Remove control characters except newline and tab.
        text = "".join(char for char in text if char in ("\n", "\t") or ord(char) >= 32)

        return text

    def _normalize_whitespace(self, text: str) -> str:
        lines = text.splitlines()

        cleaned_lines = []

        for line in lines:
            line = line.rstrip()
            line = re.sub(r"[ \t]+", " ", line)

            # Remove spaces before common punctuation.
            line = re.sub(
                r"\s+([,.;:!?])",
                r"\1",
                line,
            )

            cleaned_lines.append(line)

        return "\n".join(cleaned_lines)

    def _remove_malay(
        self,
        lines: list[str],
        report: CleaningReport,
    ) -> list[str]:
        """
        Remove confidently Malay paragraphs.
        - Markdown tables are processed cell-by-cell so that long Malay prose inside a table can be removed without destroying the table.
        - Short fragments are preserved.
        """

        result: list[str] = []

        paragraph: list[str] = []
        inside_code_fence = False

        def flush_paragraph() -> None:
            if not paragraph:
                return

            block = "\n".join(paragraph).strip()

            if self._should_remove_malay(block):
                report.malay_blocks_removed.append(block)
            else:
                result.extend(paragraph)

            paragraph.clear()

        for line in lines:
            stripped = line.strip()

            # Code fences are completely untouched.
            if stripped.startswith("```"):
                flush_paragraph()

                result.append(line)
                inside_code_fence = not inside_code_fence
                continue

            if inside_code_fence:
                result.append(line)
                continue

            # Blank line ends a paragraph.
            if not stripped:
                flush_paragraph()
                result.append(line)
                continue

            # Markdown table.
            if self._is_table_line(line):
                flush_paragraph()

                cleaned_line = self._clean_table_line(
                    line,
                    report,
                )

                result.append(cleaned_line)
                continue

            # Markdown structural elements are kept conservative.
            if self._is_markdown_structure(line):
                flush_paragraph()
                result.append(line)
                continue

            paragraph.append(line)

        flush_paragraph()

        return result

    def _clean_table_line(
        self,
        line: str,
        report: CleaningReport,
    ) -> str:
        """
        Remove confidently Malay prose from individual table cells.
        """

        if self._is_table_separator(line):
            return line

        parts = line.split("|")
        cleaned_parts: list[str] = []

        for part in parts:
            cell = part.strip()

            if self._should_remove_malay(cell):
                report.malay_blocks_removed.append(cell)
                cleaned_parts.append("")
            else:
                cleaned_parts.append(cell)

        return "|".join(cleaned_parts)

    def _should_remove_malay(self, text: str) -> bool:
        """
        Only classify sufficiently long natural-language blocks.
        Short technical fragments such as:
            dan
            ABS
            ECU
            12V
            5W-30
        are preserved.
        """

        text = text.strip()

        if not text:
            return False

        meaningful_text = re.sub(
            r"[^A-Za-zÀ-ÿ\s]",
            " ",
            text,
        )

        words = meaningful_text.split()

        # Too few words to make a reliable language decision.
        if len(words) < 8:
            return False

        # Very short text is also unreliable.
        if len(meaningful_text.strip()) < 50:
            return False

        return self.language_detector.is_confident_malay(text)

    def _is_table_line(self, line: str) -> bool:
        """
        Basic Markdown table detection.
        """
        return "|" in line

    def _is_table_separator(self, line: str) -> bool:
        """
        Detect rows such as:

            | --- | --- |
        """
        stripped = line.strip()

        if not stripped:
            return False

        parts = stripped.split("|")

        meaningful_parts = [part.strip() for part in parts if part.strip()]

        if not meaningful_parts:
            return False

        return all(re.fullmatch(r":?-+:?", part) for part in meaningful_parts)

    def _is_markdown_structure(self, line: str) -> bool:
        stripped = line.lstrip()

        if stripped.startswith("#"):
            return True

        if stripped.startswith(("- ", "* ", "+ ")):
            return True

        if re.match(r"^\d+\.\s", stripped):
            return True

        if stripped.startswith(">"):
            return True

        return False

    def _remove_consecutive_duplicates(
        self,
        lines: list[str],
        report: CleaningReport,
    ) -> list[str]:
        result: list[str] = []

        previous: str | None = None

        for line in lines:
            stripped = line.strip()

            if stripped and stripped == previous:
                report.duplicate_lines_removed.append(stripped)
                continue

            result.append(line)

            if stripped:
                previous = stripped
            else:
                previous = None

        return result

    def _remove_obvious_garbage(
        self,
        lines: list[str],
        report: CleaningReport,
    ) -> list[str]:
        result: list[str] = []

        for line in lines:
            stripped = line.strip()

            if self._is_obvious_garbage(stripped):
                report.garbage_removed.append(stripped)
                continue

            result.append(line)

        return result

    def _is_obvious_garbage(self, line: str) -> bool:
        """
        Remove only isolated OCR garbage.
        """
        if not line:
            return False

        return bool(re.fullmatch(r"[~^]{1,10}", line))

    def _final_whitespace_cleanup(
        self,
        lines: list[str],
    ) -> str:
        result: list[str] = []

        previous_blank = False

        for line in lines:
            line = line.rstrip()

            if not line.strip():
                if previous_blank:
                    continue

                previous_blank = True
                result.append("")
                continue

            previous_blank = False
            result.append(line)

        return "\n".join(result).strip() + "\n"
