"""
Each qasm snippet attached to a node in the editor will first be passed through the preprocessing pipeline.
The pipeline consists of multiple :class:`~openqasm3.visitor.QASMTransformer` that will transform the abstract syntax tree (AST) of the qasm snippet.
"""
from io import UnsupportedOperation

from app.openqasm3.parser import leqo_parse
from app.processing.graph import IOInfo, ProcessedProgramNode, ProgramNode, QubitInfo
from app.processing.pre.inlining import InliningTransformer
from app.processing.pre.io_parser import ParseAnnotationsVisitor, IOParserUnsupportedOperation
from app.processing.pre.renaming import RenameRegisterTransformer
from app.processing.utils import cast_to_program

class PreprocessingException(Exception):
    """
    Class for exceptions raised during preprocessing.
    """

    def __init__(self, msg, error_code: int = None, error_type: str = None, node: ProgramNode = None, traceback = None):
        super().__init__(msg)
        self.error_code = error_code
        self.error_type = error_type
        self.node = node
        self.traceback = traceback

def preprocess(node: ProgramNode, implementation: str) -> ProcessedProgramNode:
    """Run an openqasm3 snippet through the preprocessing pipeline.

    :param program: A valid openqasm3 program (as AST) to preprocess.
    :param section_info: MetaData of the section to preprocess.
    :return: The preprocessed program.
    """
    try:
        ast = leqo_parse(implementation)
        ast = RenameRegisterTransformer().visit(ast, node.id)
        ast = cast_to_program(InliningTransformer().visit(ast))

        io = IOInfo()
        qubit = QubitInfo()
        _ = ParseAnnotationsVisitor(io, qubit).visit(ast)

    except PreprocessingException as e:
        e.node = node
        if e.error_code is None: e.error_code = 400
        e.error_type = type(e).__name__
        raise e
    except IOParserUnsupportedOperation as e:
        raise PreprocessingException(e.args[0], 422, type(e).__name__, node) from e
    except Exception as e:
        raise PreprocessingException(e.args[0], 400, type(e).__name__, node) from e

    return ProcessedProgramNode(node, ast, io, qubit)
