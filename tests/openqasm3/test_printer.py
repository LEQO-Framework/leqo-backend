from app.openqasm3.ast import CommentStatement
from app.openqasm3.printer import leqo_dumps


def test_printer_comment() -> None:
    assert leqo_dumps(CommentStatement("Hi!")) == "/* Hi! */\n"


def test_printer_comment_empty() -> None:
    assert leqo_dumps(CommentStatement("")) == "/*  */\n"


def test_printer_comment_multiline() -> None:
    assert leqo_dumps(CommentStatement("a \n b \n c")) == "/* a \n b \n c */\n"


def test_printer_comment_escape() -> None:
    assert leqo_dumps(CommentStatement("a*/ */")) == r"/* a*\/ *\/ */" + "\n"
