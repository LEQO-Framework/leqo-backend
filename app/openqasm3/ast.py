"""
Leqo-backend specific extensions of the abstract syntax tree.
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
