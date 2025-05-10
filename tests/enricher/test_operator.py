import asyncio
from typing import override

import pytest

from app.enricher import (
    Constraints,
    Enricher,
    EnricherStrategy,
    EnrichmentResult,
    ImplementationMetaData,
    NodeUnsupportedException,
)
from app.model.CompileRequest import (
    BitLiteralNode,
    BoolLiteralNode,
    FloatLiteralNode,
    ImplementationNode,
    IntLiteralNode,
)
from app.model.CompileRequest import (
    Node as FrontendNode,
)

class AsyncEnricherStrategy(EnricherStrategy):
    @override
    async def _enrich_impl(
        self, node: FrontendNode, constraints: Constraints | None
    ) -> EnrichmentResult:
        if not isinstance(node, BitLiteralNode):
            raise NodeUnsupportedException(node)

        await asyncio.create_task(asyncio.sleep(1))
        return EnrichmentResult(
            ImplementationNode(id=node.id, implementation="C"),
            ImplementationMetaData(width=None, depth=None),
        )


@pytest.mark.asyncio
async def initialise_database() -> None:
    # add an EncodeValuenNode with different encodings and bounds
    # to the database

@pytest.mark.asyncio
async def reset_database() -> None:
    # reset the database

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
async def test_enrich_search_operator() -> None:
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
