import ast
import copy
import math
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable
from typing import Any, NoReturn

import openqasm3.ast as qast

from app.openqasm3.ast import CommentStatement

# Python AST a single OpenQASM node translates into (a statement may expand into several).
type VisitResult = ast.expr | ast.stmt | list[ast.stmt] | None


class BaseSDKProvider(ABC):
    """
    Abstract base class for quantum SDK providers.
    Each method should return a Python AST statement (ast.stmt) or expression (ast.expr).
    """

    @abstractmethod
    def start_program(self) -> list[ast.stmt]:
        """Return the initial setup code (e.g., imports, circuit creation)."""

    @abstractmethod
    def declare_qubit(self, name: str, size: int) -> list[ast.stmt]:
        """Declare a quantum register."""

    @abstractmethod
    def declare_bit(self, name: str, size: int) -> list[ast.stmt]:
        """Declare a classical register."""

    @abstractmethod
    def declare_classical_var(
        self,
        name: str,
        ast_type: Any,
        init_expr: ast.expr | None = None,
    ) -> list[ast.stmt]:
        """Declare internal classical state."""

    @abstractmethod
    def gate(self, name: str, qubits: list[ast.expr], args: list[ast.expr]) -> ast.stmt:
        """Apply a quantum gate."""

    @abstractmethod
    def reset(self, qubit: ast.expr) -> ast.stmt:
        """Reset a qubit or quantum register."""

    @abstractmethod
    def measure(self, qubit: ast.expr, clbit: ast.expr | None = None) -> ast.stmt:
        """Measure a qubit."""

    @abstractmethod
    def if_block(
        self,
        condition: ast.expr,
        then_body: list[ast.stmt],
        else_body: list[ast.stmt] | None = None,
    ) -> ast.stmt | list[ast.stmt]:
        """Create a conditional block, as several statements if the SDK needs them."""

    @abstractmethod
    def while_loop(self, condition: ast.expr, body: list[ast.stmt]) -> ast.stmt:
        """Create a while loop."""

    @abstractmethod
    def for_loop(
        self, iterator: str, range_obj: ast.expr, body: list[ast.stmt]
    ) -> ast.stmt:
        """Create a for loop."""

    @abstractmethod
    def alias(self, name: str, value: ast.expr) -> ast.stmt:
        """Create an alias (let)."""

    @abstractmethod
    def classical_assignment(
        self, lvalue: ast.expr, rvalue: ast.expr, op: str
    ) -> ast.stmt:
        """Handle classical assignment (e.g., c = 1, c += 1)."""

    @abstractmethod
    def io_declaration(self, name: str, io_type: str, ast_type: Any) -> list[ast.stmt]:
        """Declare an input or output parameter."""

    @abstractmethod
    def end_program(self) -> list[ast.stmt]:
        """Return final execution boilerplate."""

    @abstractmethod
    def get_imports(self) -> list[ast.stmt]:
        """Return the import statements for everything the generated program uses."""

    @abstractmethod
    def binary_expression(self, lhs: ast.expr, rhs: ast.expr, op: str) -> ast.expr:
        """Map a binary operator to the SDK's classical logic."""

    @abstractmethod
    def unary_expression(self, expression: ast.expr, op: str) -> ast.expr:
        """Map a unary operator to the SDK's classical logic."""

    @abstractmethod
    def cast_expression(self, expression: ast.expr, ast_type: Any) -> ast.expr:
        """Cast an expression into the SDK's supported type representation."""


class UniversalTranspiler:
    """
    SDK-independent transpiler that visits an OpenQASM 3 AST and builds
    a Python AST using a provided SDK provider.
    """

    def __init__(self, provider: BaseSDKProvider):
        self.provider = provider
        self.annotated_inputs: dict[int, ast.expr] = {}
        self.annotated_outputs: dict[int, ast.expr] = {}
        self.gate_definitions: dict[str, qast.QuantumGateDefinition] = {}
        self._identifier_scopes: list[dict[str, ast.expr]] = []

    def visit(self, node: Any) -> VisitResult:
        if node is None:
            return None
        if isinstance(node, list):
            return self._visit_statements(node)

        method_name = f"visit_{type(node).__name__}"
        visitor: Callable[[Any], VisitResult] = getattr(
            self, method_name, self.generic_visit
        )
        return visitor(node)

    def generic_visit(self, node: Any) -> NoReturn:
        raise NotImplementedError(f"Unsupported OpenQASM node: {type(node).__name__}")

    def _visit_statements(self, nodes: Iterable[Any]) -> list[ast.stmt]:
        """Translate OpenQASM statements into one flat list of Python statements."""
        statements: list[ast.stmt] = []
        for node in nodes:
            result = self.visit(node)
            if isinstance(result, list):
                statements.extend(result)
            elif result is not None:
                assert isinstance(result, ast.stmt), (
                    f"{type(node).__name__} must translate into a statement"
                )
                statements.append(result)
        return statements

    def _visit_expression(self, node: Any) -> ast.expr:
        """Translate an OpenQASM expression into a Python expression."""
        result = self.visit(node)
        assert isinstance(result, ast.expr), (
            f"{type(node).__name__} must translate into an expression"
        )
        return result

    def visit_Program(self, node: qast.Program) -> str:
        body = self.provider.start_program()
        body.extend(self._visit_statements(node.statements))
        body.extend(self.provider.end_program())
        body.extend(self._build_program_inputs_mapping())
        body.extend(self._build_program_outputs_mapping())

        # Prepend imports collected during traversal
        final_body = self.provider.get_imports() + body

        module = ast.Module(body=final_body, type_ignores=[])
        ast.fix_missing_locations(module)
        return ast.unparse(module)

    def visit_QubitDeclaration(self, node: qast.QubitDeclaration) -> list[ast.stmt]:
        name = node.qubit.name
        size = int(self.resolve_literal(node.size)) if node.size else 1
        self._register_annotation_inputs(node, ast.Name(id=name, ctx=ast.Load()))
        return self.provider.declare_qubit(name, size)

    def visit_ClassicalDeclaration(
        self, node: qast.ClassicalDeclaration
    ) -> list[ast.stmt]:
        name = node.identifier.name
        size = 1
        if hasattr(node.type, "size") and node.type.size:
            size = int(self.resolve_literal(node.type.size))

        init_expression = getattr(node, "init_expression", None)

        if isinstance(node.type, qast.ArrayType):
            init_expr = (
                self._visit_expression(init_expression)
                if init_expression is not None
                else self._build_default_array_value(node.type.dimensions)
            )
            return [
                ast.Assign(
                    targets=[ast.Name(id=name, ctx=ast.Store())],
                    value=init_expr,
                )
            ]

        if isinstance(node.type, qast.BitType):
            stmts = self.provider.declare_bit(name, size)

            if isinstance(init_expression, qast.QuantumMeasurement):
                qubit_expr = self._visit_expression(init_expression.qubit)
                stmts.append(
                    self.provider.measure(qubit_expr, ast.Name(id=name, ctx=ast.Load()))
                )
                return stmts

            if init_expression is not None:
                init_expr = self._visit_expression(init_expression)
                stmts.append(
                    self.provider.classical_assignment(
                        ast.Name(id=name, ctx=ast.Load()),
                        init_expr,
                        "=",
                    )
                )
            return stmts

        if isinstance(init_expression, qast.QuantumMeasurement):
            raise NotImplementedError(
                "Measurement initializers are only supported for bit declarations."
            )

        return self.provider.declare_classical_var(
            name,
            node.type,
            self._visit_expression(init_expression) if init_expression else None,
        )

    def visit_QuantumGateDefinition(self, node: qast.QuantumGateDefinition) -> None:
        name = node.name.name
        if name in self.gate_definitions:
            raise NotImplementedError(
                f"Duplicate custom gate definition is not supported: {name}"
            )
        self.gate_definitions[name] = node

    def visit_QuantumGate(self, node: qast.QuantumGate) -> ast.stmt | list[ast.stmt]:
        gate_name = node.name.name
        if gate_name in self.gate_definitions:
            return self._expand_gate_definition(self.gate_definitions[gate_name], node)

        args = (
            [self._visit_expression(arg) for arg in node.arguments]
            if node.arguments
            else []
        )
        qubits = [self._visit_expression(q) for q in node.qubits]
        return self.provider.gate(gate_name, qubits, args)

    def visit_QuantumReset(self, node: qast.QuantumReset) -> ast.stmt:
        qubit_expr = self._visit_expression(node.qubits)
        return self.provider.reset(qubit_expr)

    def visit_QuantumMeasurementStatement(
        self, node: qast.QuantumMeasurementStatement
    ) -> ast.stmt:
        qubit_expr = self._visit_expression(node.measure.qubit)
        target_expr = self._visit_expression(node.target) if node.target else None
        return self.provider.measure(qubit_expr, target_expr)

    def visit_BranchingStatement(
        self, node: qast.BranchingStatement
    ) -> ast.stmt | list[ast.stmt]:
        cond = self._visit_expression(node.condition)
        then_body: list[ast.stmt] = (
            self._visit_statements(node.if_block) if node.if_block else [ast.Pass()]
        )
        else_body = self._visit_statements(node.else_block) if node.else_block else None
        return self.provider.if_block(cond, then_body, else_body)

    def visit_WhileLoop(self, node: qast.WhileLoop) -> ast.stmt:
        cond = self._visit_expression(node.while_condition)
        body = self._visit_statements(node.block)
        return self.provider.while_loop(cond, body)

    def visit_ForInLoop(self, node: qast.ForInLoop) -> ast.stmt:
        iterator_name = node.identifier.name

        if isinstance(node.set_declaration, qast.RangeDefinition):
            start = (
                int(self.resolve_literal(node.set_declaration.start))
                if node.set_declaration.start
                else 0
            )
            end = int(self.resolve_literal(node.set_declaration.end))
            step = (
                int(self.resolve_literal(node.set_declaration.step))
                if node.set_declaration.step
                else 1
            )

            # Python range is exclusive, OpenQASM is inclusive
            python_end = end + 1 if step > 0 else end - 1

            range_args: list[ast.expr] = [
                ast.Constant(value=start),
                ast.Constant(value=python_end),
            ]
            if step != 1:
                range_args.append(ast.Constant(value=step))

            range_obj: ast.expr = ast.Call(
                func=ast.Name(id="range", ctx=ast.Load()), args=range_args, keywords=[]
            )

        elif isinstance(node.set_declaration, qast.DiscreteSet):
            elements: list[ast.expr] = [
                ast.Constant(value=int(self.resolve_literal(v)))
                for v in node.set_declaration.values
            ]
            range_obj = ast.List(elts=elements, ctx=ast.Load())
        else:
            raise NotImplementedError(
                "For-in loops are only supported over ranges and discrete sets."
            )

        body = self._visit_statements(node.block)
        return self.provider.for_loop(iterator_name, range_obj, body)

    def visit_AliasStatement(self, node: qast.AliasStatement) -> ast.stmt:
        name = node.target.name
        value = self._visit_expression(node.value)
        self._register_annotation_inputs(node, ast.Name(id=name, ctx=ast.Load()))
        self._register_annotation_outputs(node, ast.Name(id=name, ctx=ast.Load()))
        return self.provider.alias(name, value)

    def visit_IndexExpression(self, node: qast.IndexExpression) -> ast.expr:
        collection = self._visit_expression(node.collection)
        idx = node.index[0] if isinstance(node.index, list) else node.index

        if isinstance(idx, qast.RangeDefinition):
            start = int(self.resolve_literal(idx.start)) if idx.start else 0
            end = int(self.resolve_literal(idx.end)) if idx.end else None
            step = int(self.resolve_literal(idx.step)) if idx.step else None

            slice_obj = ast.Slice(
                lower=ast.Constant(value=start) if start != 0 else None,
                upper=ast.Constant(value=end + 1) if end is not None else None,
                step=ast.Constant(value=step) if step is not None else None,
            )
            return ast.Subscript(value=collection, slice=slice_obj, ctx=ast.Load())

        if isinstance(idx, qast.DiscreteSet):
            # This is complex in Python AST (list of subscripts)
            # Usually handled by the provider if it's SDK specific, but here we return a list comprehension or similar
            elements = [int(self.resolve_literal(v)) for v in idx.values]
            elts: list[ast.expr] = [
                ast.Subscript(
                    value=collection, slice=ast.Constant(value=e), ctx=ast.Load()
                )
                for e in elements
            ]
            return ast.List(elts=elts, ctx=ast.Load())

        index_val = self._visit_expression(idx)
        return ast.Subscript(value=collection, slice=index_val, ctx=ast.Load())

    def visit_BinaryExpression(self, node: qast.BinaryExpression) -> ast.expr:
        lhs = self._visit_expression(node.lhs)
        rhs = self._visit_expression(node.rhs)
        op_str = str(node.op).split(".")[-1]
        return self.provider.binary_expression(lhs, rhs, op_str)

    def visit_UnaryExpression(self, node: qast.UnaryExpression) -> ast.expr:
        inner = self._visit_expression(node.expression)
        op_str = str(node.op).split(".")[-1]
        return self.provider.unary_expression(inner, op_str)

    def visit_Cast(self, node: qast.Cast) -> ast.expr:
        expression = self._visit_expression(node.argument)
        return self.provider.cast_expression(expression, node.type)

    def visit_ClassicalAssignment(self, node: qast.ClassicalAssignment) -> ast.stmt:
        lvalue = self._visit_expression(node.lvalue)
        rvalue = self._visit_expression(node.rvalue)
        op_str = str(node.op).split(".")[-1]
        return self.provider.classical_assignment(lvalue, rvalue, op_str)

    def visit_IODeclaration(self, node: qast.IODeclaration) -> list[ast.stmt]:
        name = node.identifier.name
        io_type = node.io_identifier.name
        if isinstance(node.type, qast.ArrayType):
            raise NotImplementedError(
                "Array inputs and outputs are not part of the supported executable subset."
            )
        return self.provider.io_declaration(name, io_type, node.type)

    def visit_Concatenation(self, node: qast.Concatenation) -> ast.BinOp:
        lhs = self._as_qubit_sequence(self._visit_expression(node.lhs))
        rhs = self._as_qubit_sequence(self._visit_expression(node.rhs))
        return ast.BinOp(left=lhs, op=ast.Add(), right=rhs)

    def _as_qubit_sequence(self, value: ast.expr) -> ast.expr:
        """
        Wrap a concatenation operand so it can be joined with ``+``.

        OpenQASM ``++`` concatenates qubit registers, but Qiskit does not define
        ``QuantumRegister + QuantumRegister``. Wrapping each operand in ``list(...)``
        turns the join into Python list concatenation, yielding a flat, indexable
        qubit sequence. A nested concatenation already produces such a list, so it
        is left untouched to avoid a redundant ``list(list(...))``.
        """
        if isinstance(value, ast.BinOp) and isinstance(value.op, ast.Add):
            return value
        return ast.Call(
            func=ast.Name(id="list", ctx=ast.Load()), args=[value], keywords=[]
        )

    def visit_ArrayLiteral(self, node: qast.ArrayLiteral) -> ast.List:
        return ast.List(
            elts=[self._visit_expression(value) for value in node.values],
            ctx=ast.Load(),
        )

    def visit_Identifier(self, node: qast.Identifier) -> ast.expr:
        replacement = self._lookup_identifier_replacement(node.name)
        if replacement is not None:
            return copy.deepcopy(replacement)
        if node.name == "pi":
            return ast.Constant(value=math.pi)
        return ast.Name(id=node.name, ctx=ast.Load())

    def visit_IndexedIdentifier(self, node: qast.IndexedIdentifier) -> ast.expr:
        """Translate an indexed operand, keeping every qubit of a set or range index."""
        index = node.indices[0]
        if isinstance(index, qast.DiscreteSet) and len(index.values) == 1:
            # A single-element set addresses one qubit, so translate q[{0}] like q[0].
            index = [index.values[0]]
        return self.visit_IndexExpression(
            qast.IndexExpression(collection=node.name, index=index)
        )

    def visit_QuantumMeasurement(self, node: qast.QuantumMeasurement) -> ast.expr:
        raise NotImplementedError(
            "General measurement expressions are not part of the supported executable subset."
        )

    def visit_IntegerLiteral(self, node: qast.IntegerLiteral) -> ast.Constant:
        return ast.Constant(value=int(node.value))

    def visit_FloatLiteral(self, node: qast.FloatLiteral) -> ast.Constant:
        return ast.Constant(value=float(node.value))

    def visit_BooleanLiteral(self, node: qast.BooleanLiteral) -> ast.Constant:
        return ast.Constant(value=bool(node.value))

    def visit_BitstringLiteral(self, node: qast.BitstringLiteral) -> ast.Constant:
        # Convert bitstring "0b11" or "11" -> 3
        val = node.value
        try:
            if isinstance(val, str):
                if not val.startswith("0b"):
                    # Check if it looks like a binary string (only 0s and 1s)
                    if all(c in "01" for c in val):
                        val = "0b" + val
                    else:
                        return ast.Constant(value=int(val))  # Try as decimal
                return ast.Constant(value=int(val, 2))
            return ast.Constant(value=int(val))
        except (ValueError, TypeError):
            return ast.Constant(value=0)  # Fallback

    def visit_Include(self, node: qast.Include) -> None:  # noqa: ARG002
        return None

    def visit_CommentStatement(self, node: CommentStatement) -> ast.stmt:
        return ast.Expr(value=ast.Constant(value=f"# {node.comment}"))

    def resolve_literal(self, node: Any) -> str:
        if isinstance(node, int):
            return str(node)
        if isinstance(node, str):
            return node
        if isinstance(node, qast.UnaryExpression):
            inner = self.resolve_literal(node.expression)
            op_str = str(node.op).split(".")[-1]
            if op_str == "-":
                return str(-int(inner))
            if op_str == "+":
                return str(int(inner))
        # Also covers BitstringLiteral, whose value the parser already stores as an int.
        if hasattr(node, "value"):
            return str(node.value)
        return str(node)

    def _expand_gate_definition(
        self,
        definition: qast.QuantumGateDefinition,
        call: qast.QuantumGate,
    ) -> list[ast.stmt]:
        formal_args = [identifier.name for identifier in (definition.arguments or [])]
        formal_qubits = [identifier.name for identifier in definition.qubits]
        actual_args = (
            [self._visit_expression(arg) for arg in call.arguments]
            if call.arguments
            else []
        )
        actual_qubits = [self._visit_expression(qubit) for qubit in call.qubits]

        if len(formal_args) != len(actual_args):
            raise NotImplementedError(
                f"Custom gate {definition.name.name} expects {len(formal_args)} argument(s), "
                f"got {len(actual_args)}."
            )
        if len(formal_qubits) != len(actual_qubits):
            raise NotImplementedError(
                f"Custom gate {definition.name.name} expects {len(formal_qubits)} qubit(s), "
                f"got {len(actual_qubits)}."
            )

        substitutions = {
            **dict(zip(formal_args, actual_args, strict=True)),
            **dict(zip(formal_qubits, actual_qubits, strict=True)),
        }

        self._identifier_scopes.append(substitutions)
        try:
            return self._visit_statements(definition.body)
        finally:
            self._identifier_scopes.pop()

    def _lookup_identifier_replacement(self, name: str) -> ast.expr | None:
        for scope in reversed(self._identifier_scopes):
            if name in scope:
                return scope[name]
        return None

    def _build_default_array_value(self, dimensions: list[Any]) -> ast.expr:
        resolved_dimensions = [
            int(self.resolve_literal(dimension)) for dimension in dimensions
        ]

        def build(level: int) -> ast.expr:
            if level >= len(resolved_dimensions):
                return ast.Constant(value=None)
            return ast.List(
                elts=[build(level + 1) for _ in range(resolved_dimensions[level])],
                ctx=ast.Load(),
            )

        return build(0)

    def _register_annotation_inputs(self, node: Any, expression: ast.expr) -> None:
        for annotation in getattr(node, "annotations", []) or []:
            if getattr(annotation, "keyword", None) != "leqo.input":
                continue
            command = getattr(annotation, "command", None)
            if command is None:
                continue
            try:
                index = int(command.strip())
            except (ValueError, AttributeError) as exc:
                raise NotImplementedError(
                    f"@leqo.input annotation requires an integer index, got: {command!r}"
                ) from exc
            self.annotated_inputs[index] = expression

    def _register_annotation_outputs(self, node: Any, expression: ast.expr) -> None:
        for annotation in getattr(node, "annotations", []) or []:
            if getattr(annotation, "keyword", None) != "leqo.output":
                continue
            command = getattr(annotation, "command", None)
            if command is None:
                continue
            try:
                index = int(command.strip())
            except (ValueError, AttributeError) as exc:
                raise NotImplementedError(
                    f"@leqo.output annotation requires an integer index, got: {command!r}"
                ) from exc
            self.annotated_outputs[index] = expression

    def _build_program_inputs_mapping(self) -> list[ast.stmt]:
        if not self.annotated_inputs:
            return []

        keys: list[ast.expr | None] = []
        values: list[ast.expr] = []
        for index, expression in sorted(self.annotated_inputs.items()):
            keys.append(ast.Constant(value=index))
            values.append(expression)

        return [
            ast.Assign(
                targets=[ast.Name(id="program_inputs", ctx=ast.Store())],
                value=ast.Dict(keys=keys, values=values),
            )
        ]

    def _build_program_outputs_mapping(self) -> list[ast.stmt]:
        if not self.annotated_outputs:
            return []

        keys: list[ast.expr | None] = []
        values: list[ast.expr] = []
        for index, expression in sorted(self.annotated_outputs.items()):
            keys.append(ast.Constant(value=index))
            values.append(expression)

        return [
            ast.Assign(
                targets=[ast.Name(id="program_outputs", ctx=ast.Store())],
                value=ast.Dict(keys=keys, values=values),
            )
        ]
