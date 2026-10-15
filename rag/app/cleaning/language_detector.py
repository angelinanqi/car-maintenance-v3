from rag.config.settings import MALAY_CONFIDENCE_THRESHOLD
from lingua import Language, LanguageDetectorBuilder


class LanguageDetector:
    """
    Detects English and Malay text using Lingua.
    Only confident Malay text is considered removable.
    """

    def __init__(self, malay_threshold: float = MALAY_CONFIDENCE_THRESHOLD) -> None:
        self.malay_threshold = malay_threshold

        self.detector = LanguageDetectorBuilder.from_languages(
            Language.ENGLISH,
            Language.MALAY,
        ).build()

    def is_confident_malay(self, text: str) -> bool:
        text = text.strip()

        if not text:
            return False

        confidence = self.detector.compute_language_confidence(
            text,
            Language.MALAY,
        )

        return confidence >= self.malay_threshold
