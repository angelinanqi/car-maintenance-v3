from rag.config.settings import MALAY_CONFIDENCE_THRESHOLD
from lingua import Language, LanguageDetectorBuilder


class LanguageDetector:
    """
    Detects English and Malay text using Lingua.
    Only confident, single-language Malay text is considered removable.
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

        if confidence < self.malay_threshold:
            return False

        # A dominant-language score can hide a short English instruction.
        # Keep the whole block when the detector finds mixed or unknown spans;
        # span boundaries are not reliable enough to use for deleting text.
        spans = self.detector.detect_multiple_languages_of(text)
        return bool(spans) and all(span.language == Language.MALAY for span in spans)
