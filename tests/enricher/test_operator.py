import pytest
from sqlalchemy.orm import Session

from app.enricher import (
    Constraints,
    Enricher,
    EnricherStrategy,
    EnrichmentResult,
    ImplementationMetaData,
    NodeUnsupportedException,
)
from app.enricher.models import InputType, NodeType, OperatorNode
from app.model.CompileRequest import (
    BitLiteralNode,
    BoolLiteralNode,
    FloatLiteralNode,
    ImplementationNode,
    IntLiteralNode,
)
from app.model.CompileRequest import PrepareStateNode as FrontendPrepareStateNode
from app.model.CompileRequest import OperatorNode as FrontendOperatorNode



@pytest.fixture(autouse=True)
def setup_database_data(session: Session) -> None:
    """
    Set up the database with test data for the EncodeValueNode.
    """
    node1 = OperatorNode(
        type=NodeType.ENCODE,
        depth=1,
        width=1,
        implementation="amplitude_impl",
        inputs=[{"index": 0, "type": InputType.FloatType.value, "size": 32}],
        encoding=EncodingType.AMPLITUDE,
        bounds=2,
    )
    node2 = EncodeValueNode(
        type=NodeType.ENCODE,
        depth=2,
        width=2,
        implementation="angle_impl",
        inputs=[{"index": 0, "type": InputType.IntType.value, "size": 32}],
        encoding=EncodingType.ANGLE,
        bounds=1,
    )
    node3 = EncodeValueNode(
        type=NodeType.ENCODE,
        depth=3,
        width=3,
        implementation="matrix_impl",
        inputs=[{"index": 0, "type": InputType.BitType.value, "size": 32}],
        encoding=EncodingType.MATRIX,
        bounds=6,
    )
    node4 = EncodeValueNode(
        type=NodeType.ENCODE,
        depth=4,
        width=4,
        implementation="schimdt_impl",
        inputs=[{"index": 0, "type": InputType.BoolType.value, "size": None}],
        encoding=EncodingType.SCHMIDT,
        bounds=8,
    )

    session.add_all([node1, node2, node3, node4])
    session.commit()
    session.close()


@pytest.mark.asyncio
async def test_enrich_plus_operator() -> None:
    # Enrich node implementation
    # assert the implementation

@pytest.mark.asyncio
async def test_enrich_multiplication_operator() -> None:
    # Enrich node implementation
    # assert the implementation

@pytest.mark.asyncio
async def test_enrich_OR_operator() -> None:
    # Enrich node implementation
    # assert the implementation

@pytest.mark.asyncio
async def test_enrich_greater_operator() -> None:
    # Enrich node implementation
    # assert the implementation

@pytest.mark.asyncio
async def test_enrich_min_operator() -> None:
    # Enrich node implementation
    # assert the implementation

@pytest.mark.asyncio
async def test_enrich_unknown_node() -> None:
    # Try enrich non OperatorNode implementation
    # assert exception NodeUnsupportedException

@pytest.mark.asyncio
async def test_enrich_operator_one_inputs() -> None:
    # Enrich node implementation
    # assert exception ConstraintValidationException

@pytest.mark.asyncio
async def test_enrich_operator_three_inputs() -> None:
    # Enrich node implementation
    # assert exception ConstraintValidationException

@pytest.mark.asyncio
async def test_enrich_operator_classical_input() -> None:
    # Enrich node with classical input
    # assert exception ConstraintValidationException

@pytest.mark.asyncio
async def test_enrich_operator_node_not_in_db() -> None:
    # Enrich node without implemetation in db
    # assert exception NodeUnsupportedException
