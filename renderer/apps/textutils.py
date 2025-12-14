from collections.abc import Callable
from typing import List


def _split_keep_delimiter(text: str, delimiter: str) -> List[str]:
    """
    Split a string by a delimiter, keeping the delimiter.
    """
    parts = text.split(delimiter)
    return [
        part + delimiter if i < len(parts) - 1 else part for i, part in enumerate(parts)
    ]


def split_into_words(line: str):
    """
    Split a line into words, taking into account hyphenated words.
    """
    words = [line]
    for delimiter in [" ", "-"]:
        words = [w for word in words for w in _split_keep_delimiter(word, delimiter)]
    return words


def splitline_evenly(
    line: str, measure_fn: Callable[[str], float], maxwidth: int | float
) -> List[str]:
    """
    Split a line into multiple lines, each with a maximum width.
    Minimize the length of the longest line.

    Args:
        line: The line to split.
        measure_fn: A function that takes a string and returns its width.
        maxwidth: The maximum width of each line.
    Returns:
        A list of lines.
    """
    words = split_into_words(line)

    lines: List[str] = []
    current_line = ""
    current_width = 0.0

    for word in words:
        word_width = measure_fn(word)
        if current_width + word_width <= maxwidth:
            current_line += word
            current_width += word_width
        else:
            if current_line:
                lines.append(current_line.rstrip())
            current_line = word
            current_width = word_width

    if current_line:
        lines.append(current_line.rstrip())

    if maxwidth > 1:
        shorter_lines = splitline_evenly(line, measure_fn, maxwidth - 1)
        if len(shorter_lines) <= len(lines):
            return shorter_lines

    return lines
