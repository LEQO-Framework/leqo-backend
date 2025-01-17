from openqasm3.ast import Include, Statement
from openqasm3.parser import parse

from app.model.block import Block
from app.qasm_builder import QASMBuilder


def process_statement(statement: Statement) -> Statement:
    return statement


def process_block(block: Block, builder: QASMBuilder) -> None:
    """
    Passes a block of qasm code through the pipeline and appends it to the final program using `builder`.

    :param block: The qasm block to be processed
    :param builder: QasmBuilder used to build the final program
    """

    program = parse(block.qasm)

    builder.comment(block.label)
    for statement in program.statements:
        if isinstance(statement, Include):
            builder.include(statement.filename)
        else:
            builder.statement(process_statement(statement))
