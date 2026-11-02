"""Conservative text normalization shared by manual preprocessing stages."""


def normalize_unicode(text: str) -> str:
    # Avoid NFKC: technical symbols and superscripts are source information.
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
    return "".join(char for char in text if char in ("\n", "\t") or ord(char) >= 32)
