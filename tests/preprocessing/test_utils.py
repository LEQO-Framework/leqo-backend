import pytest
from openqasm3.ast import Annotation

from app.preprocessing.utils import parse_io_annotation


def test_parse_io_annotation() -> None:
    def assert_parse(command: str | None, expected: list[int]) -> None:
        assert parse_io_annotation(Annotation("leqo.input", command)) == expected, (
            f"'{command}' != {expected}"
        )
        assert parse_io_annotation(Annotation("leqo.output", command)) == expected, (
            f"'{command}' != {expected}"
        )

    def assert_parse_failure(command: str | None, match: str) -> None:
        with pytest.raises(ValueError, match=match):
            parse_io_annotation(Annotation("leqo.input", command))

        with pytest.raises(ValueError, match=match):
            parse_io_annotation(Annotation("leqo.output", command))

    assert_parse(None, [])
    assert_parse("", [])
    assert_parse("   ", [])  # Allow blank
    assert_parse("1,2,3", [1, 2, 3])
    assert_parse("3,2,1", [3, 2, 1])  # Order is preserved
    assert_parse(" 1 , 2 , 3 ", [1, 2, 3])
    assert_parse("1-2", [1, 2])  # Range is inclusive
    assert_parse("1-1", [1])
    assert_parse(" 1 - 2 ", [1, 2])
    assert_parse("1-2,2-3", [1, 2, 2, 3])  # Overlaps are preserved
    assert_parse(" 1 - 2 , 2 - 3 ", [1, 2, 2, 3])
    assert_parse("1,2,3-5,7", [1, 2, 3, 4, 5, 7])
    assert_parse(" 1 , 2 , 3 - 5 , 7 ", [1, 2, 3, 4, 5, 7])

    assert_parse_failure("abc", r"^invalid literal for int\(\) with base 10: 'abc'")
    assert_parse_failure("abc", r"^invalid literal for int\(\) with base 10: 'abc'")
    assert_parse_failure("1,,2", r"^invalid literal for int\(\) with base 10: ''")
    assert_parse_failure("1-2-3", r"^A range may only contain 2 integers")
    assert_parse_failure("2-1", r"^Start of range must be <= end of range")
