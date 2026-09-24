"""Small, deterministic transformations that preserve policy wording."""
import re


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\u00a0", " ")).strip()


def clean_blocks(blocks: list[str]) -> str:
    # Do not case-fold policy text, remove numbers, or deduplicate repeated rules.
    return "\n\n".join(value for block in blocks if (value := normalize_whitespace(block)))
