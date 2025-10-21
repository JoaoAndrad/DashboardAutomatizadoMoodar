"""Example module docstring to remove when requested.

Contains functions with comments and docstrings.
"""

import math


def foo(x):
    """Function docstring should be removed when --remove-docstrings is used.

    It also contains inline comments and a string literal below.
    """
    # This is a comment and should be removed
    s = "This is a string # not a comment"
    # Another comment
    return math.sqrt(x)  # inline comment to remove


class Bar:
    """Class docstring to remove if requested."""

    def method(self):
        print("Hello")  # say hi


if __name__ == '__main__':
    # run example
    print(foo(9))
