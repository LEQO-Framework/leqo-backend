from openqasm3.ast import BranchingStatement, Expression

from app.openqasm3.parser import leqo_parse


def parse_condition(value: str) -> Expression:
    wrapper = f"if({value}) {{}}"
    if_else_ast = leqo_parse(wrapper).statements[0]
    if not isinstance(if_else_ast, BranchingStatement):
        raise RuntimeError()
    return if_else_ast.condition
