import ast
from abc import ABC, abstractmethod
from typing import Any, List, Optional, Union
import openqasm3.ast as qast
from app.openqasm3.ast import CommentStatement

class BaseSDKProvider(ABC):
    """
    Abstract base class for quantum SDK providers.
    Each method should return a Python AST statement (ast.stmt) or expression (ast.expr).
    """

    @abstractmethod
    def start_program(self) -> List[ast.stmt]:
        """Return the initial setup code (e.g., imports, circuit creation)."""
        pass

    @abstractmethod
    def declare_qubit(self, name: str, size: int) -> List[ast.stmt]:
        """Declare a quantum register."""
        pass

    @abstractmethod
    def declare_bit(self, name: str, size: int) -> List[ast.stmt]:
        """Declare a classical register."""
        pass

    @abstractmethod
    def declare_classical_var(
        self,
        name: str,
        ast_type: Any,
        init_expr: Optional[ast.expr] = None,
    ) -> List[ast.stmt]:
        """Declare internal classical state."""
        pass

    @abstractmethod
    def gate(self, name: str, qubits: List[ast.expr], args: List[ast.expr]) -> ast.stmt:
        """Apply a quantum gate."""
        pass

    @abstractmethod
    def measure(self, qubit: ast.expr, clbit: Optional[ast.expr] = None) -> ast.stmt:
        """Measure a qubit."""
        pass

    @abstractmethod
    def if_block(self, condition: ast.expr, then_body: List[ast.stmt], else_body: Optional[List[ast.stmt]] = None) -> ast.stmt:
        """Create a conditional block."""
        pass

    @abstractmethod
    def while_loop(self, condition: ast.expr, body: List[ast.stmt]) -> ast.stmt:
        """Create a while loop."""
        pass

    @abstractmethod
    def for_loop(self, iterator: str, range_obj: ast.expr, body: List[ast.stmt]) -> ast.stmt:
        """Create a for loop."""
        pass

    @abstractmethod
    def alias(self, name: str, value: ast.expr) -> ast.stmt:
        """Create an alias (let)."""
        pass

    @abstractmethod
    def classical_assignment(self, lvalue: ast.expr, rvalue: ast.expr, op: str) -> ast.stmt:
        """Handle classical assignment (e.g., c = 1, c += 1)."""
        pass

    @abstractmethod
    def io_declaration(self, name: str, io_type: str, ast_type: Any) -> List[ast.stmt]:
        """Declare an input or output parameter."""
        pass

    @abstractmethod
    def end_program(self) -> List[ast.stmt]:
        """Return final execution boilerplate."""
        pass

    @abstractmethod
    def binary_expression(self, lhs: ast.expr, rhs: ast.expr, op: str) -> ast.expr:
        """Map a binary operator to the SDK's classical logic."""
        pass

    @abstractmethod
    def unary_expression(self, expression: ast.expr, op: str) -> ast.expr:
        """Map a unary operator to the SDK's classical logic."""
        pass

    @abstractmethod
    def cast_expression(self, expression: ast.expr, ast_type: Any) -> ast.expr:
        """Cast an expression into the SDK's supported type representation."""
        pass


class UniversalTranspiler:
    """
    SDK-independent transpiler that visits an OpenQASM 3 AST and builds
    a Python AST using a provided SDK provider.
    """

    def __init__(self, provider: BaseSDKProvider):
        self.provider = provider
        self.annotated_outputs: dict[int, ast.expr] = {}

    def visit(self, node: Any) -> Union[ast.expr, ast.stmt, List[ast.stmt], None]:
        if node is None:
            return None
        if isinstance(node, list):
            results = []
            for item in node:
                res = self.visit(item)
                if isinstance(res, list):
                    results.extend(res)
                elif res is not None:
                    results.append(res)
            return results

        method_name = f"visit_{type(node).__name__}"
        visitor = getattr(self, method_name, self.generic_visit)
        return visitor(node)

    def generic_visit(self, node: Any):
        raise NotImplementedError(f"Unsupported OpenQASM node: {type(node).__name__}")

    def visit_Program(self, node: qast.Program) -> str:
        body = self.provider.start_program()
        
        # Traverse statements
        for stmt in node.statements:
            res = self.visit(stmt)
            if isinstance(res, list):
                body.extend(res)
            elif res is not None:
                body.append(res)

        body.extend(self.provider.end_program())
        body.extend(self._build_program_outputs_mapping())
        
        # Prepend imports collected during traversal
        final_body = self.provider.get_imports() + body
        
        module = ast.Module(body=final_body, type_ignores=[])
        ast.fix_missing_locations(module)
        return ast.unparse(module)

    def visit_QubitDeclaration(self, node: qast.QubitDeclaration) -> List[ast.stmt]:
        name = node.qubit.name
        size = int(node.size.value) if node.size else 1
        return self.provider.declare_qubit(name, size)

    def visit_ClassicalDeclaration(self, node: qast.ClassicalDeclaration) -> List[ast.stmt]:
        name = node.identifier.name
        size = 1
        if hasattr(node.type, "size") and node.type.size:
            size = int(self.resolve_literal(node.type.size))

        init_expression = getattr(node, "init_expression", None)

        if isinstance(node.type, qast.ArrayType):
            init_expr = self.visit(init_expression) if init_expression is not None else self._build_default_array_value(node.type.dimensions)
            return [
                ast.Assign(
                    targets=[ast.Name(id=name, ctx=ast.Store())],
                    value=init_expr,
                )
            ]

        if isinstance(node.type, qast.BitType):
            stmts = self.provider.declare_bit(name, size)

            if isinstance(init_expression, qast.QuantumMeasurement):
                qubit_expr = self.visit(init_expression.qubit)
                stmts.append(self.provider.measure(qubit_expr, ast.Name(id=name, ctx=ast.Load())))
                return stmts

            if init_expression is not None:
                init_expr = self.visit(init_expression)
                stmts.append(
                    self.provider.classical_assignment(
                        ast.Name(id=name, ctx=ast.Load()),
                        init_expr,
                        "=",
                    )
                )
            return stmts

        if isinstance(init_expression, qast.QuantumMeasurement):
            raise NotImplementedError("Measurement initializers are only supported for bit declarations.")

        init_expr = self.visit(init_expression) if init_expression else None
        return self.provider.declare_classical_var(name, node.type, init_expr)

    def visit_QuantumGate(self, node: qast.QuantumGate) -> ast.stmt:
        gate_name = node.name.name
        args = [self.visit(arg) for arg in node.arguments] if node.arguments else []
        qubits = [self.visit(q) for q in node.qubits]
        return self.provider.gate(gate_name, qubits, args)

    def visit_QuantumMeasurementStatement(self, node: qast.QuantumMeasurementStatement) -> ast.stmt:
        qubit_expr = self.visit(node.measure.qubit)
        target_expr = self.visit(node.target) if node.target else None
        return self.provider.measure(qubit_expr, target_expr)

    def visit_BranchingStatement(self, node: qast.BranchingStatement) -> ast.stmt:
        cond = self.visit(node.condition)
        then_body = self.visit(node.if_block) if node.if_block else [ast.Pass()]
        else_body = self.visit(node.else_block) if node.else_block else None
        
        # Ensure body is a list of statements
        if not isinstance(then_body, list): then_body = [then_body]
        if else_body and not isinstance(else_body, list): else_body = [else_body]
            
        return self.provider.if_block(cond, then_body, else_body)

    def visit_WhileLoop(self, node: qast.WhileLoop) -> ast.stmt:
        cond = self.visit(node.while_condition)
        body = self.visit(node.block)
        if not isinstance(body, list): body = [body]
        return self.provider.while_loop(cond, body)

    def visit_ForInLoop(self, node: qast.ForInLoop) -> ast.stmt:
        iterator_name = node.identifier.name
        
        if isinstance(node.set_declaration, qast.RangeDefinition):
            start = int(self.resolve_literal(node.set_declaration.start)) if node.set_declaration.start else 0
            end = int(self.resolve_literal(node.set_declaration.end))
            step = int(self.resolve_literal(node.set_declaration.step)) if node.set_declaration.step else 1
            
            # Python range is exclusive, OpenQASM is inclusive
            python_end = end + 1 if step > 0 else end - 1
            
            range_args = [ast.Constant(value=start), ast.Constant(value=python_end)]
            if step != 1:
                range_args.append(ast.Constant(value=step))
            
            range_obj = ast.Call(func=ast.Name(id='range', ctx=ast.Load()), args=range_args, keywords=[])
        
        elif isinstance(node.set_declaration, qast.DiscreteSet):
            elements = [ast.Constant(value=int(self.resolve_literal(v))) for v in node.set_declaration.values]
            range_obj = ast.List(elts=elements, ctx=ast.Load())
        else:
            raise NotImplementedError("For-in loops are only supported over ranges and discrete sets.")

        body = self.visit(node.block)
        if not isinstance(body, list): body = [body]
        return self.provider.for_loop(iterator_name, range_obj, body)

    def visit_AliasStatement(self, node: qast.AliasStatement) -> ast.stmt:
        name = node.target.name
        value = self.visit(node.value)
        self._register_annotation_outputs(node, ast.Name(id=name, ctx=ast.Load()))
        return self.provider.alias(name, value)

    def visit_IndexExpression(self, node: qast.IndexExpression) -> ast.expr:
        collection = self.visit(node.collection)
        idx = node.index[0] if isinstance(node.index, list) else node.index

        if isinstance(idx, qast.RangeDefinition):
            start = int(self.resolve_literal(idx.start)) if idx.start else 0
            end = int(self.resolve_literal(idx.end)) if idx.end else None
            step = int(self.resolve_literal(idx.step)) if idx.step else None
            
            slice_obj = ast.Slice(
                lower=ast.Constant(value=start) if start != 0 else None,
                upper=ast.Constant(value=end + 1) if end is not None else None,
                step=ast.Constant(value=step) if step is not None else None
            )
            return ast.Subscript(value=collection, slice=slice_obj, ctx=ast.Load())

        elif isinstance(idx, qast.DiscreteSet):
            # This is complex in Python AST (list of subscripts)
            # Usually handled by the provider if it's SDK specific, but here we return a list comprehension or similar
            elements = [int(self.resolve_literal(v)) for v in idx.values]
            elts = [ast.Subscript(value=collection, slice=ast.Constant(value=e), ctx=ast.Load()) for e in elements]
            return ast.List(elts=elts, ctx=ast.Load())

        else:
            index_val = self.visit(idx)
            return ast.Subscript(value=collection, slice=index_val, ctx=ast.Load())

    def visit_BinaryExpression(self, node: qast.BinaryExpression) -> ast.expr:
        lhs = self.visit(node.lhs)
        rhs = self.visit(node.rhs)
        op_str = str(node.op).split('.')[-1]
        return self.provider.binary_expression(lhs, rhs, op_str)

    def visit_UnaryExpression(self, node: qast.UnaryExpression) -> ast.expr:
        inner = self.visit(node.expression)
        op_str = str(node.op).split('.')[-1]
        return self.provider.unary_expression(inner, op_str)

    def visit_Cast(self, node: qast.Cast) -> ast.expr:
        expression = self.visit(node.argument)
        return self.provider.cast_expression(expression, node.type)

    def visit_ClassicalAssignment(self, node: qast.ClassicalAssignment) -> ast.stmt:
        lvalue = self.visit(node.lvalue)
        rvalue = self.visit(node.rvalue)
        op_str = str(node.op).split('.')[-1]
        return self.provider.classical_assignment(lvalue, rvalue, op_str)

    def visit_IODeclaration(self, node: qast.IODeclaration) -> List[ast.stmt]:
        name = node.identifier.name
        io_type = node.io_identifier.name
        if isinstance(node.type, qast.ArrayType):
            raise NotImplementedError("Array inputs and outputs are not part of the supported executable subset.")
        return self.provider.io_declaration(name, io_type, node.type)

    def visit_Concatenation(self, node: qast.Concatenation) -> ast.BinOp:
        lhs = self.visit(node.lhs)
        rhs = self.visit(node.rhs)
        return ast.BinOp(left=lhs, op=ast.Add(), right=rhs)

    def visit_ArrayLiteral(self, node: qast.ArrayLiteral) -> ast.List:
        return ast.List(elts=[self.visit(value) for value in node.values], ctx=ast.Load())

    def visit_Identifier(self, node: qast.Identifier) -> ast.expr:
        return ast.Name(id=node.name, ctx=ast.Load())

    def visit_IndexedIdentifier(self, node: qast.IndexedIdentifier) -> ast.expr:
        name_node = ast.Name(id=node.name.name, ctx=ast.Load())
        idx_element = node.indices[0]
        
        if isinstance(idx_element, qast.DiscreteSet):
            idx_node = idx_element.values[0]
        else:
            idx_node = idx_element[0]
            
        index_val = self.visit(idx_node)
        return ast.Subscript(value=name_node, slice=index_val, ctx=ast.Load())

    def visit_QuantumMeasurement(self, node: qast.QuantumMeasurement) -> ast.expr:
        raise NotImplementedError("General measurement expressions are not part of the supported executable subset.")

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
                if not val.startswith('0b'):
                    # Check if it looks like a binary string (only 0s and 1s)
                    if all(c in '01' for c in val):
                        val = '0b' + val
                    else:
                        return ast.Constant(value=int(val)) # Try as decimal
                return ast.Constant(value=int(val, 2))
            return ast.Constant(value=int(val))
        except (ValueError, TypeError):
            return ast.Constant(value=0) # Fallback

    def visit_Include(self, node: qast.Include) -> None:
        return None

    def visit_CommentStatement(self, node: CommentStatement) -> ast.stmt:
        return ast.Expr(value=ast.Constant(value=f"# {node.comment}"))

    def resolve_literal(self, node: Any) -> str:
        if isinstance(node, int): return str(node)
        if isinstance(node, str): return node
        if isinstance(node, qast.UnaryExpression):
            inner = self.resolve_literal(node.expression)
            op_str = str(node.op).split('.')[-1]
            if op_str == '-':
                return str(-int(inner))
            if op_str == '+':
                return str(int(inner))
        if isinstance(node, qast.BitstringLiteral):
            val = node.value
            try:
                # Try as decimal first
                return str(int(val))
            except ValueError:
                # Try as binary (OpenQASM bitstrings can be "00", "11", or "0b11")
                if not val.startswith('0b'):
                    val = '0b' + val
                return str(int(val, 2))
        if hasattr(node, 'value'):
            return str(node.value)
        return str(node)

    def _build_default_array_value(self, dimensions: List[Any]) -> ast.expr:
        resolved_dimensions = [int(self.resolve_literal(dimension)) for dimension in dimensions]

        def build(level: int) -> ast.expr:
            if level >= len(resolved_dimensions):
                return ast.Constant(value=None)
            return ast.List(
                elts=[build(level + 1) for _ in range(resolved_dimensions[level])],
                ctx=ast.Load(),
            )

        return build(0)

    def _register_annotation_outputs(self, node: Any, expression: ast.expr) -> None:
        for annotation in getattr(node, "annotations", []) or []:
            if getattr(annotation, "keyword", None) != "leqo.output":
                continue
            command = getattr(annotation, "command", None)
            if command is None:
                continue
            self.annotated_outputs[int(command.strip())] = expression

    def _build_program_outputs_mapping(self) -> List[ast.stmt]:
        if not self.annotated_outputs:
            return []

        keys = []
        values = []
        for index, expression in sorted(self.annotated_outputs.items()):
            keys.append(ast.Constant(value=index))
            values.append(expression)

        return [
            ast.Assign(
                targets=[ast.Name(id='program_outputs', ctx=ast.Store())],
                value=ast.Dict(keys=keys, values=values),
            )
        ]


