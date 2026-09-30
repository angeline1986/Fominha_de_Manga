"""Shared natural ordering for chapter and manga labels."""
import re


def natural_sort_key(value: str) -> list[object]:
    """Sort labels by embedded numbers (for example, Ch. 2 before Ch. 10)."""
    return [
        (1, int(part)) if part.isdigit() else (0, part.casefold())
        for part in re.split(r"(\d+)", value)
    ]
