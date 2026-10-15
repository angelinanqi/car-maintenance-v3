from rag.config.settings import MALAY_CONFIDENCE_THRESHOLD
import re
from pathlib import Path
from rag.app.cleaning.language_detector import LanguageDetector


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
        malay_threshold: float = MALAY_CONFIDENCE_THRESHOLD,
    ) -> None:
        self.language_detector = LanguageDetector(malay_threshold=malay_threshold)

    def clean_file(self, input_path: Path, output_path: Path):
        """Clean extracted Markdown for indexing."""
        cleaned = self.clean(input_path.read_text(encoding="utf-8"))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(cleaned, encoding="utf-8")

    def clean(
        self,
        markdown: str,
    ) -> str:

        # Keep fenced/indented code byte-for-byte at the line level. Also avoids
        # deleting repeated code lines or treating code pipes as table syntax.
        original = markdown.splitlines()
        protected = self._code_lines(original)
        result = []
        pending = []
        for index, line in enumerate(original):
            if index in protected:
                if pending:
                    result.append(self._clean_prose("\n".join(pending)))
                    pending = []
                result.append(line + "\n")
            else:
                pending.append(line)
        if pending:
            result.append(self._clean_prose("\n".join(pending)))
        return "".join(result)

    def _clean_prose(self, markdown: str) -> str:
        text = self._normalize_unicode(markdown)
        text = self._normalize_whitespace(text)

        lines = text.splitlines()

        lines = self._remove_malay(
            lines,
        )

        lines = self._remove_consecutive_duplicates(
            lines,
        )

        lines = self._remove_obvious_garbage(
            lines,
        )

        cleaned = self._final_whitespace_cleanup(lines)

        return cleaned

    @staticmethod
    def _code_lines(lines: list[str]) -> set[int]:
        protected = set()
        fence = None
        for index, line in enumerate(lines):
            match = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
            if fence:
                protected.add(index)
                if (
                    match
                    and match[1][0] == fence[0]
                    and len(match[1]) >= len(fence)
                    and not line[match.end() :].strip()
                ):
                    fence = None
            elif match:
                fence = match[1]
                protected.add(index)
            elif line.startswith(("    ", "\t")) and not re.match(
                r"^\s*(?:[-*+]\s+|\d+[.)]\s+)", line
            ):
                protected.add(index)
        return protected

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
            # Leading indentation and inline spacing can be Markdown syntax.
            # Two trailing spaces are a meaningful Markdown hard line break.
            hard_break = line.endswith("  ") and bool(line.strip())
            line = line.rstrip() + ("  " if hard_break else "")

            cleaned_lines.append(line)

        return "\n".join(cleaned_lines)

    def _remove_malay(
        self,
        lines: list[str],
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

            if not self._should_remove_malay(block):
                result.extend(paragraph)

            paragraph.clear()

        table_lines = self._table_lines(lines)
        for index, line in enumerate(lines):
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
            if index in table_lines:
                flush_paragraph()

                cleaned_line = self._clean_table_line(
                    line,
                )

                result.append(cleaned_line)
                continue

            # Markdown structural elements are kept conservative.
            if self._is_markdown_structure(line):
                flush_paragraph()
                natural = re.sub(r"^\s*(?:>\s*)+", "", line)
                natural = re.sub(r"^\s*(?:#{1,6}\s+|[-*+]\s+|\d+[.)]\s+)", "", natural)
                if not self._should_remove_malay(natural):
                    result.append(line)
                continue

            paragraph.append(line)

        flush_paragraph()

        return result

    def _clean_table_line(
        self,
        line: str,
    ) -> str:
        """
        Remove confidently Malay prose from individual table cells.
        """

        if self._is_table_separator(line):
            return line

        # Escaped pipes and code spans are not safe to rewrite cell-by-cell.
        if "\\|" in line or "`" in line:
            return line
        parts = line.split("|")
        cleaned_parts: list[str] = []

        for part in parts:
            cell = part.strip()

            if self._should_remove_malay(cell):
                cleaned_parts.append("")
            else:
                cleaned_parts.append(part)

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

    def _table_lines(self, lines: list[str]) -> set[int]:
        """Require a header followed by a matching Markdown delimiter row."""
        rows = set()
        for index in range(1, len(lines)):
            if not self._is_table_separator(lines[index]):
                continue
            header = lines[index - 1].strip().strip("|").split("|")
            separator = lines[index].strip().strip("|").split("|")
            if "|" not in lines[index - 1] or len(header) != len(separator):
                continue
            rows.update((index - 1, index))
            following = index + 1
            while (
                following < len(lines)
                and lines[following].strip()
                and "|" in lines[following]
            ):
                if len(lines[following].strip().strip("|").split("|")) != len(
                    separator
                ):
                    break
                rows.add(following)
                following += 1
        return rows

    def _is_table_separator(self, line: str) -> bool:
        """
        Detect rows such as:

            | --- | --- |
        """
        stripped = line.strip()

        if not stripped or "|" not in stripped:
            return False

        parts = stripped.split("|")

        meaningful_parts = [part.strip() for part in parts if part.strip()]

        if not meaningful_parts:
            return False

        return all(re.fullmatch(r":?-{3,}:?", part) for part in meaningful_parts)

    def _is_markdown_structure(self, line: str) -> bool:
        stripped = line.lstrip()

        if stripped.startswith("#"):
            return True

        if stripped.startswith(("- ", "* ", "+ ")):
            return True

        if re.match(r"^\d+[.)]\s", stripped):
            return True

        if stripped.startswith(">"):
            return True

        return False

    def _remove_consecutive_duplicates(
        self,
        lines: list[str],
    ) -> list[str]:
        result: list[str] = []

        previous: str | None = None

        table_lines = self._table_lines(lines)
        for index, line in enumerate(lines):
            stripped = line.strip()

            if (
                stripped
                and line == previous
                and index not in table_lines
                and not self._is_markdown_structure(line)
            ):
                continue

            result.append(line)

            if stripped:
                previous = line
            else:
                previous = None

        return result

    def _remove_obvious_garbage(
        self,
        lines: list[str],
    ) -> list[str]:
        result: list[str] = []

        for line in lines:
            stripped = line.strip()

            if self._is_obvious_garbage(stripped):
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
            hard_break = line.endswith("  ") and bool(line.strip())
            line = line.rstrip() + ("  " if hard_break else "")

            if not line.strip():
                if previous_blank:
                    continue

                previous_blank = True
                result.append("")
                continue

            previous_blank = False
            result.append(line)

        return "\n".join(result) + "\n"
