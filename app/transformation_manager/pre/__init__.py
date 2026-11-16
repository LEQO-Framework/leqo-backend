"""
Each single qasm snippet attached to a node will first pass through the preprocessing pipeline.

This happens without the global graph view.
The steps are:

- parse implementation if it is a string
- convert to OpenQASM 3 if in OpenQASM 2
- rename the identifiers by prefixing with node id
- inline constants
- parse annotation info
- upcast inputs if they are too small for the required spec
"""

from copy import copy
from openqasm3.ast import AliasStatement, Concatenation, Identifier, Statement, Program

from app.model.data_types import LeqoSupportedType
from app.transformation_manager.graph import (
    IOInfo,
    ProcessedProgramNode,
    ProgramNode,
    QubitInfo,
)
from app.transformation_manager.pre.converter import parse_to_openqasm3
from app.transformation_manager.pre.inlining import InliningTransformer
from app.transformation_manager.pre.io_parser import ParseAnnotationsVisitor
from app.transformation_manager.pre.renaming import RenameRegisterTransformer
from app.transformation_manager.pre.size_casting import size_cast
from app.transformation_manager.pre.utils import PreprocessingException
from app.transformation_manager.utils import cast_to_program
from app.utils import safe_generate_implementation_node


# flatten concatenation expressions to get the individual identifiers, e.g. a ++ b -> [a, b]
def flatten_concat(expr):
    if isinstance(expr, Identifier):
        return [expr]
    if isinstance(expr, Concatenation):
        return flatten_concat(expr.lhs) + flatten_concat(expr.rhs)
    return []


# expand
def expand_unary_concat_broadcast(program: Program) -> Program:
    # handle the case of unary gates applied to concatenations, e.g. h q; where let q = a ++ b;
    cmap = {}
    for st in program.statements:  # find statements with concatenations on the rhs of an alias, e.g. let q = a ++ b;
        if (
            isinstance(st, AliasStatement)
            and isinstance(st.target, Identifier)
            and isinstance(st.value, Concatenation)
        ):
            elems = flatten_concat(
                st.value
            )  # flatten the concatenation to get the individual identifiers, e.g. a ++ b -> [a, b]
            if len(elems) >= 2:
                cmap[st.target.name] = elems

    if not cmap:
        return program

    new_statements: list[Statement] = []
    # replace statements with unary gates applied to concatenations with multiple statements, e.g. h q; -> h a; h b;
    for st in program.statements:
        qubits = getattr(st, "qubits", None)

        # unary gate like: h q;
        if qubits and len(qubits) == 1 and isinstance(qubits[0], Identifier):
            name = qubits[0].name

            if name in cmap:
                for elem in cmap[name]:
                    st2 = copy(st)
                    st2.qubits = [elem]
                    new_statements.append(st2)
                continue

        new_statements.append(st)

    # copy the program and replace the statements with the new statements containing the expanded unary gates applied to concatenations
    p2 = copy(program)
    p2.statements = new_statements
    return p2


def preprocess(
    node: ProgramNode,
    implementation: str | Program,
    requested_inputs: dict[int, LeqoSupportedType] | None = None,
) -> ProcessedProgramNode:
    """
    Run an openqasm3 snippet through the preprocessing pipeline.

    :param node: The node to preprocess.
    :param implementation: A valid OpenQASM 2/3 implementation for that node.
    :param requested_inputs: Optional inputs specification for size_casting
    :return: The preprocessed program.
    """
    try:
        if isinstance(implementation, Program):
            ast = implementation
        else:
            ast = parse_to_openqasm3(implementation)

        # handle the case of unary gates applied to concatenations, e.g. h q; where let q = a ++ b;
        ast = expand_unary_concat_broadcast(ast)  #

        ast = RenameRegisterTransformer().visit(ast, node.id)
        ast = cast_to_program(InliningTransformer().visit(ast))

        io = IOInfo()
        qubit = QubitInfo()
        _ = ParseAnnotationsVisitor(io, qubit).visit(ast)

        processed_node = ProcessedProgramNode(node, ast, io, qubit)
        if requested_inputs is not None:
            size_cast(
                processed_node,
                {index: type.size for index, type in requested_inputs.items()},
            )

    except PreprocessingException as exc:
        exc.node = safe_generate_implementation_node(node.name, implementation)
        raise exc

    return processed_node
