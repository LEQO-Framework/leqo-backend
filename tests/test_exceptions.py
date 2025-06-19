from io import StringIO
from textwrap import dedent

from app.model.exceptions import DiagnosticError, print_exception


def test_single_diagnostic() -> None:
    stream = StringIO()
    print_exception(stream, DiagnosticError("Test 42"))
    assert stream.getvalue() == "Test 42\n"


def test_single_exception() -> None:
    stream = StringIO()
    print_exception(stream, Exception("Test 42"))
    assert stream.getvalue() == "<Redacted>\n"


def test_multiple_exceptions() -> None:
    try:
        try:
            try:
                raise Exception("Redacted 2") from DiagnosticError("Test 2")
            except Exception as e:
                raise DiagnosticError("Test 1") from e
        except Exception as e:
            raise Exception("Redacted 1") from e
    except Exception as ex:
        exception = ex

    stream = StringIO()
    print_exception(stream, exception)
    print(stream.getvalue())
    assert stream.getvalue() == dedent("""\
    <Redacted>
    ╰ Test 1
      ╰ <Redacted>
        ╰ Test 2
    """)


def test_exception_group() -> None:
    try:
        raise DiagnosticError("Item 1") from Exception("Redacted 1")
    except Exception as ex:
        item1 = ex

    try:
        raise Exception("Redacted 2") from DiagnosticError("Item 2")
    except Exception as ex:
        item2 = ex

    try:
        raise ExceptionGroup(
            "Redacted inner group", [item1, item2]
        ) from DiagnosticError("Cause of inner group")
    except Exception as ex:
        inner_group = ex

    try:
        raise ExceptionGroup(
            "Redacted outer group", [inner_group]
        ) from DiagnosticError("Cause of outer group")
    except Exception as ex:
        exception = ex

    stream = StringIO()
    print_exception(stream, exception)
    print(stream.getvalue())
    assert stream.getvalue() == dedent("""\
    <Redacted>
    │ <Redacted>
    │ │ Item 1
    │ │ ╰ <Redacted>
    │ │ <Redacted>
    │ │ ╰ Item 2
    │ ╰ Cause of inner group
    ╰ Cause of outer group
    """)


class MyTestException(Exception):
    pass


def test_no_exception_msg():
    stream = StringIO()
    print_exception(stream, MyTestException(), is_debug=True)
    assert stream.getvalue() == "MyTestException\n"
