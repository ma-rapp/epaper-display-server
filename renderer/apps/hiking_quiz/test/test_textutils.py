import os
import sys

print(sys.path)
print(os.getcwd())

from renderer.apps.hiking_quiz.textutils import splitline_evenly


def test_split_simple():
    text = "This is a test text"
    maxwidth = 10  # characters

    assert splitline_evenly(text, measure_fn=len, maxwidth=maxwidth) == [
        "This is a",
        "test text",
    ]


def test_split_barely_does_not_fit():
    """
    This test case uses a string that just barely does not fit.
    It should be split into two lines of equal length.
    """
    text = "This is a test text"
    maxwidth = len(text) - 1  # characters

    assert splitline_evenly(text, measure_fn=len, maxwidth=maxwidth) == [
        "This is a",
        "test text",
    ]


def test_long_hyphenated_word():
    text = "This-is-a-very-long-hyphenated-word and short text"
    maxwidth = 11  # characters

    assert splitline_evenly(text, measure_fn=len, maxwidth=maxwidth) == [
        "This-is-a-",
        "very-long-",
        "hyphenated-",
        "word and",
        "short text",
    ]
