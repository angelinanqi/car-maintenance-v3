from dataclasses import dataclass, field
import json
from pathlib import Path


@dataclass
class CleaningReport:
    document_name: str

    malay_blocks_removed: list[str] = field(default_factory=list)
    duplicate_lines_removed: list[str] = field(default_factory=list)
    garbage_removed: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "document_name": self.document_name,
            "malay_blocks_removed": self.malay_blocks_removed,
            "duplicate_lines_removed": self.duplicate_lines_removed,
            "garbage_removed": self.garbage_removed,
        }

    def save(self, output_path: Path) -> None:
        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with output_path.open("w", encoding="utf-8") as file:
            json.dump(
                self.to_dict(),
                file,
                ensure_ascii=False,
                indent=2,
            )
