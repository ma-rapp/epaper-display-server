from collections.abc import Callable
from typing import List


def _generate_all_splits(
    elements: List,
    nb_splits: int,
    valid_fn: Callable[[List[str]], bool] | None = None,
):
    """
    generate all splits of the elements.

    Example 1:
        elements = [1, 2, 3]
        nb_splits = 1
    Splits
        [1, 2, 3]

    Example 2:
        elements = [1, 2, 3]
        nb_splits = 2
    Splits
        [1], [2, 3]
        [1, 2], [3]

    Example 3:
        elements = [1, 2, 3]
        nb_splits = 3
    Splits
        [1], [2], [3]
    """
    if nb_splits > len(elements):
        return
    if nb_splits == 1:
        if valid_fn is not None and not valid_fn(elements):
            return
        yield [elements]
    else:
        for nb_elements_first_split in range(1, len(elements) + 1):
            first_element = elements[:nb_elements_first_split]
            if valid_fn is not None and not valid_fn(first_element):
                continue
            remaining_elements = elements[nb_elements_first_split:]
            for remaining_splits in _generate_all_splits(
                remaining_elements,
                nb_splits - 1,
                valid_fn=valid_fn,
            ):
                split = [first_element] + remaining_splits
                yield split


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
):
    nb_splits = 1
    words = split_into_words(line)
    while True:
        if nb_splits >= len(words):
            return words

        shortest_width = None
        best_split_lines = None
        for split in _generate_all_splits(
            words,
            nb_splits,
            valid_fn=lambda words: measure_fn("".join(words).strip())
            <= min(maxwidth, shortest_width or maxwidth),
        ):
            split_lines = ["".join(words).strip() for words in split]
            width = max(measure_fn(line) for line in split_lines)
            if shortest_width is None or width < shortest_width:
                shortest_width = width
                best_split_lines = split_lines

        if shortest_width is not None:
            assert (
                shortest_width <= maxwidth
            )  # only valid split should be found when using a valid_fn
            return best_split_lines

        nb_splits += 1
