from openqasm3.ast import Expression, IntegerLiteral


def get_int(expression: Expression | None) -> int | None:
    """
    Tries to get an integer from an expression.
    This method does no analysis of the overall ast.
    If it cannot extract an integer from an expression, it throws.

    :param expression: Expression to be analyses
    :return: Integer or None if input was None
    """

    match expression:
        case None:
            return 0
        case IntegerLiteral():
            return expression.value
        case _:
            raise Exception("Invalid size")


def parse_io_range(value: str | None) -> int | None:
    if value is None:
        return None

    return int(value)