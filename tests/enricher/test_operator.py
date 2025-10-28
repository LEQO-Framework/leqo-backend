import pytest
import pytest_asyncio
from openqasm3.ast import (
    AliasStatement,
    Identifier,
    IndexedIdentifier,
    IntegerLiteral,
    Program,
    QuantumGate,
    QubitDeclaration,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.enricher import Constraints
from app.enricher.models import (
    Input,
    InputType,
    NodeType,
    OperatorNode,
    OperatorType,
)
from app.enricher.operator import OperatorEnricherStrategy
from app.model.CompileRequest import OperatorNode as FrontendOperatorNode
from app.model.CompileRequest import PrepareStateNode as FrontendPrepareStateNode
from app.model.CompileRequest import SingleInsertMetaData
from app.model.data_types import FloatType, QubitType
from app.model.exceptions import InputCountMismatch, InputTypeMismatch
from tests.enricher.utils import assert_enrichments


@pytest_asyncio.fixture(autouse=True)
async def setup_database_data(session: AsyncSession) -> None:
    """
    Set up the database with test data for the OperatorNode.
    """

    node1 = OperatorNode(
        type=NodeType.OPERATOR,
        depth=1,
        width=2,
        implementation="addition_impl",
        inputs=[
            Input(index=0, type=InputType.QubitType, size=2),
            Input(index=1, type=InputType.QubitType, size=3),
        ],
        operator=OperatorType.ADD,
    )
    node2 = OperatorNode(
        type=NodeType.OPERATOR,
        depth=2,
        width=2,
        implementation="multiplication_impl",
        inputs=[
            Input(index=0, type=InputType.QubitType, size=1),
            Input(index=1, type=InputType.QubitType, size=4),
        ],
        operator=OperatorType.MUL,
    )
    node3 = OperatorNode(
        type=NodeType.OPERATOR,
        depth=3,
        width=3,
        implementation="or_impl",
        inputs=[
            Input(index=0, type=InputType.QubitType, size=4),
            Input(index=1, type=InputType.QubitType, size=3),
        ],
        operator=OperatorType.OR,
    )
    node4 = OperatorNode(
        type=NodeType.OPERATOR,
        depth=3,
        width=4,
        implementation="greater_than_impl",
        inputs=[
            Input(index=0, type=InputType.QubitType, size=5),
            Input(index=1, type=InputType.QubitType, size=4),
        ],
        operator=OperatorType.GT,
    )
    node5 = OperatorNode(
        type=NodeType.OPERATOR,
        depth=4,
        width=5,
        implementation="minimum_impl",
        inputs=[
            Input(index=0, type=InputType.QubitType, size=5),
            Input(index=1, type=InputType.QubitType, size=6),
        ],
        operator=OperatorType.MIN,
    )

    session.add_all([node1, node2, node3, node4, node5])
    await session.commit()


@pytest.mark.asyncio
async def test_insert_enrichtment(engine: AsyncEngine) -> None:
    node = FrontendOperatorNode(id="1", label=None, type="operator", operator="/")

    result = await OperatorEnricherStrategy(engine).insert_enrichment(
        node=node,
        implementation="operator_impl",
        requested_inputs={0: QubitType(size=2), 1: QubitType(size=3)},
        meta_data=SingleInsertMetaData(width=1, depth=1),
    )

    assert result is True
    async with AsyncSession(engine) as session:
        db_result = await session.execute(
            select(OperatorNode).where(
                OperatorNode.implementation == "operator_impl",
                OperatorNode.type == NodeType.OPERATOR,
                OperatorNode.operator == OperatorType.DIV,
                OperatorNode.depth == 1,
                OperatorNode.width == 1,
            )
        )
        node_in_db = db_result.scalar_one_or_none()
        assert node_in_db is not None


@pytest.mark.asyncio
async def test_enrich_plus_operator(engine: AsyncEngine) -> None:
    node = FrontendOperatorNode(id="1", label=None, type="operator", operator="+")
    constraints = Constraints(
        requested_inputs={0: QubitType(size=3), 1: QubitType(size=4)},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    enrichment_results = await OperatorEnricherStrategy(engine).enrich(
        node, constraints
    )
    enrichment_results = list(enrichment_results)
    assert len(enrichment_results) == 1

    result = enrichment_results[0]
    lhs_size = constraints.requested_inputs[0].size or 1
    rhs_size = constraints.requested_inputs[1].size or 1
    max_bits = max(lhs_size, rhs_size)
    expected_result_size = max_bits + 1
    expected_carry = max(max_bits - 1, 0)
    expected_width = lhs_size + rhs_size + expected_result_size + expected_carry

    assert result.meta_data.width == expected_width
    assert result.meta_data.depth is not None
    assert result.meta_data.depth > 0

    program = result.enriched_node.implementation
    assert isinstance(program, Program)
    alias_statement = program.statements[-1]
    assert isinstance(alias_statement, AliasStatement)
    assert all(
        annotation.keyword != "leqo.twos_complement"
        for annotation in alias_statement.annotations
    )
    output_value = alias_statement.value
    assert isinstance(output_value, Identifier)
    assert output_value.name == "sum"


@pytest.mark.asyncio
async def test_enrich_plus_operator_with_signed_extension(
    engine: AsyncEngine,
) -> None:
    node = FrontendOperatorNode(id="1", label=None, type="operator", operator="+")
    constraints = Constraints(
        requested_inputs={
            0: QubitType(size=2, signed=True),
            1: QubitType(size=4, signed=True),
        },
        optimizeDepth=True,
        optimizeWidth=True,
    )

    enrichment_results = await OperatorEnricherStrategy(engine).enrich(
        node, constraints
    )
    enrichment_results = list(enrichment_results)

    assert len(enrichment_results) == 1
    enriched_node = enrichment_results[0].enriched_node
    assert isinstance(enriched_node.implementation, Program)
    program = enriched_node.implementation

    sign_bit = IndexedIdentifier(Identifier("addend0"), [[IntegerLiteral(1)]])
    extended_sum_bit = IndexedIdentifier(Identifier("sum"), [[IntegerLiteral(2)]])
    gates = [
        statement
        for statement in program.statements
        if isinstance(statement, QuantumGate) and statement.name.name == "cx"
    ]

    assert any(gate.qubits == [sign_bit, extended_sum_bit] for gate in gates), (
        "Expected sign bit to drive extended sum bit for signed addition"
    )

    alias_statement = program.statements[-1]
    assert isinstance(alias_statement, AliasStatement)
    assert any(
        annotation.keyword == "leqo.twos_complement"
        for annotation in alias_statement.annotations
    )

    addend0_decl = next(
        stmt
        for stmt in program.statements
        if isinstance(stmt, QubitDeclaration) and stmt.qubit.name == "addend0"
    )
    addend1_decl = next(
        stmt
        for stmt in program.statements
        if isinstance(stmt, QubitDeclaration) and stmt.qubit.name == "addend1"
    )
    assert any(
        annotation.keyword == "leqo.twos_complement"
        for annotation in addend0_decl.annotations
    )
    assert any(
        annotation.keyword == "leqo.twos_complement"
        for annotation in addend1_decl.annotations
    )


@pytest.mark.asyncio
async def test_addition_enrichment_handles_larger_lhs(engine: AsyncEngine) -> None:
    node = FrontendOperatorNode(id="1", label=None, type="operator", operator="+")
    constraints = Constraints(
        requested_inputs={0: QubitType(size=5), 1: QubitType(size=3)},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    enrichment = OperatorEnricherStrategy(engine)._generate_addition_enrichment(
        node, constraints
    )

    lhs_size = constraints.requested_inputs[0].size or 1
    rhs_size = constraints.requested_inputs[1].size or 1
    max_bits = max(lhs_size, rhs_size)
    expected_result_size = max_bits + 1
    expected_carry = max(max_bits - 1, 0)
    expected_width = lhs_size + rhs_size + expected_result_size + expected_carry
    assert enrichment.meta_data.width == expected_width
    assert enrichment.meta_data.depth is not None
    assert enrichment.meta_data.depth > 0

    program = enrichment.enriched_node.implementation
    assert isinstance(program, Program)
    alias_statement = program.statements[-1]
    assert isinstance(alias_statement, AliasStatement)
    output_value = alias_statement.value
    assert isinstance(output_value, Identifier)
    assert output_value.name == "sum"


@pytest.mark.asyncio
async def test_enrich_plus_operator_without_constraints_uses_db(
    engine: AsyncEngine,
) -> None:
    node = FrontendOperatorNode(id="1", label=None, type="operator", operator="+")

    results = await OperatorEnricherStrategy(engine).enrich(node, None)
    assert_enrichments(results, "addition_impl", 2, 1)


@pytest.mark.asyncio
async def test_enrich_multiplication_operator(engine: AsyncEngine) -> None:
    node = FrontendOperatorNode(id="1", label=None, type="operator", operator="*")
    constraints = Constraints(
        requested_inputs={0: QubitType(size=1), 1: QubitType(size=4)},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    result = await OperatorEnricherStrategy(engine).enrich(node, constraints)
    assert_enrichments(result, "multiplication_impl", 2, 2)


@pytest.mark.asyncio
async def test_enrich_OR_operator(engine: AsyncEngine) -> None:
    node = FrontendOperatorNode(id="1", label=None, type="operator", operator="|")
    constraints = Constraints(
        requested_inputs={0: QubitType(size=4), 1: QubitType(size=3)},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    result = await OperatorEnricherStrategy(engine).enrich(node, constraints)
    assert_enrichments(result, "or_impl", 3, 3)


@pytest.mark.asyncio
async def test_enrich_greater_operator(engine: AsyncEngine) -> None:
    node = FrontendOperatorNode(id="1", label=None, type="operator", operator=">")
    constraints = Constraints(
        requested_inputs={0: QubitType(size=5), 1: QubitType(size=4)},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    result = await OperatorEnricherStrategy(engine).enrich(node, constraints)
    assert_enrichments(result, "greater_than_impl", 4, 3)


@pytest.mark.asyncio
async def test_enrich_min_operator(engine: AsyncEngine) -> None:
    node = FrontendOperatorNode(id="1", label=None, type="operator", operator="min")
    constraints = Constraints(
        requested_inputs={0: QubitType(size=5), 1: QubitType(size=6)},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    result = await OperatorEnricherStrategy(engine).enrich(node, constraints)
    assert_enrichments(result, "minimum_impl", 5, 4)


@pytest.mark.asyncio
async def test_enrich_unknown_node(engine: AsyncEngine) -> None:
    node = FrontendPrepareStateNode(
        id="1", label=None, type="prepare", quantumState="ghz", size=3
    )
    constraints = Constraints(
        requested_inputs={0: FloatType(size=32)},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    result = await OperatorEnricherStrategy(engine).enrich(node, constraints)

    assert result == []


@pytest.mark.asyncio
async def test_enrich_operator_one_inputs(engine: AsyncEngine) -> None:
    node = FrontendOperatorNode(id="1", label=None, type="operator", operator="!=")
    constraints = Constraints(
        requested_inputs={0: QubitType(size=7)},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    with pytest.raises(
        InputCountMismatch,
        match=r"^Node should have 2 inputs\. Got 1\.$",
    ):
        await OperatorEnricherStrategy(engine).enrich(node, constraints)


@pytest.mark.asyncio
async def test_enrich_operator_classical_input(engine: AsyncEngine) -> None:
    node = FrontendOperatorNode(id="1", label=None, type="operator", operator="==")
    constraints = Constraints(
        requested_inputs={0: FloatType(size=32), 1: FloatType(size=32)},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    with pytest.raises(
        InputTypeMismatch,
        match=r"^Expected type 'qubit' for input 0\. Got 'FloatType\(size=32\)'\.$",
    ):
        await OperatorEnricherStrategy(engine).enrich(node, constraints)


@pytest.mark.asyncio
async def test_enrich_operator_node_not_in_db(engine: AsyncEngine) -> None:
    node = FrontendOperatorNode(id="1", label=None, type="operator", operator="&")
    constraints = Constraints(
        requested_inputs={0: QubitType(size=5), 1: QubitType(size=6)},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    assert (await OperatorEnricherStrategy(engine).enrich(node, constraints)) == []
