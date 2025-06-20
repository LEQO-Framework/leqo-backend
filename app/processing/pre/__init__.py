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

from openqasm3.ast import Program
from openqasm3.printer import dumps

from app.model.CompileRequest import ImplementationNode
from app.model.data_types import LeqoSupportedType
from app.processing.graph import IOInfo, ProcessedProgramNode, ProgramNode, QubitInfo
from app.processing.pre.converter import parse_to_openqasm3
from app.processing.pre.inlining import InliningTransformer
from app.processing.pre.io_parser import ParseAnnotationsVisitor
from app.processing.pre.renaming import RenameRegisterTransformer
from app.processing.pre.size_casting import size_cast
from app.processing.pre.utils import PreprocessingException
from app.processing.utils import cast_to_program
from app.utils import save_generate_implementation_node


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
        exc.node = save_generate_implementation_node(node.name, implementation)
        raise exc

    return processed_node
