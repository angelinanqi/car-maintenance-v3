from dataclasses import dataclass

@dataclass
class Metadata:
    document_name: str = ""
    source_tag: str = ""
    source_depth: int = 0
    source_position: int = 0

    def to_dict(self) -> dict:
        return {
            "document_name": self.document_name,
            "source_tag": self.source_tag,
            "source_depth": self.source_depth,
            "source_position": self.source_position,
        }
