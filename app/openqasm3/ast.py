"""
Leqo-backend specific extensions of the abstract syntax tree.

* Added support for comments using :class:`~app.openqasm3.ast.CommentStatement`
"""

from dataclasses import dataclass

from openqasm3.ast import Statement


@dataclass
class CommentStatement(Statement):
    """
    Simple qasm statement representing a block comment.

    Output: `/* {comment} */`
    """

    comment: str
