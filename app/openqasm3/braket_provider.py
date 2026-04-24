import ast
from typing import Any, List, Optional, Union
import openqasm3.ast as qast
from app.openqasm3.universal_transpiler import BaseSDKProvider

class BraketProvider(BaseSDKProvider):
    """
    AWS Braket implementation of the BaseSDKProvider.
    Generates Python AST nodes for the Amazon Braket SDK (braket.circuits.Circuit).
    """

    def __init__(self):
        self.used_imports = set()
        self.qubit_map = {} # Maps register names to start indices
        self.next_qubit_index = 0
        self.has_measurements = False

    def start_program(self) -> List[ast.stmt]:
        self.used_imports.add("from braket.circuits import Circuit")
        self.used_imports.add("from braket.devices import LocalSimulator")
        
        return [
            ast.Assign(
                targets=[ast.Name(id='c', ctx=ast.Store())],
                value=ast.Call(func=ast.Name(id='Circuit', ctx=ast.Load()), args=[], keywords=[])
            )
        ]

    def declare_qubit(self, name: str, size: int) -> List[ast.stmt]:
        # Braket uses integer indices. We map named registers to contiguous blocks.
        start_idx = self.next_qubit_index
        self.qubit_map[name] = start_idx
        self.next_qubit_index += size
        
        return [
            ast.Expr(value=ast.Constant(value=f"Register {name} mapped to qubits {start_idx} to {start_idx + size - 1}"))
        ]

    def declare_bit(self, name: str, size: int) -> List[ast.stmt]:
        # Braket SDK doesn't have a direct 'ClassicalRegister' equivalent in its Python DSL.
        # We'll use a standard Python list to act as a placeholder for classical bits.
        return [
            ast.Assign(
                targets=[ast.Name(id=name, ctx=ast.Store())],
                value=ast.List(elts=[ast.Constant(value=0)] * size, ctx=ast.Load())
            )
        ]

    def declare_classical_var(self, name: str, ast_type: Any, init_expr: Optional[ast.expr] = None) -> List[ast.stmt]:
        return [
            ast.Assign(
                targets=[ast.Name(id=name, ctx=ast.Store())],
                value=init_expr if init_expr is not None else ast.Constant(value=None),
            )
        ]

    def gate(self, name: str, qubits: List[ast.expr], args: List[ast.expr]) -> ast.stmt:
        # Resolve qubits to their integer indices if possible
        resolved_qubits = []
        for q in qubits:
            # Handle standard Name (e.g., q)
            if isinstance(q, ast.Name) and q.id in self.qubit_map:
                resolved_qubits.append(ast.Constant(value=self.qubit_map[q.id]))
            # Handle Subscript (e.g., q[0])
            elif isinstance(q, ast.Subscript) and isinstance(q.value, ast.Name) and q.value.id in self.qubit_map:
                if isinstance(q.slice, ast.Constant):
                    # Absolute index = register_start + offset
                    absolute_idx = self.qubit_map[q.value.id] + q.slice.value
                    resolved_qubits.append(ast.Constant(value=absolute_idx))
                else:
                    resolved_qubits.append(q) # Fallback
            else:
                resolved_qubits.append(q)
        
        return ast.Expr(value=ast.Call(
            func=ast.Attribute(value=ast.Name(id='c', ctx=ast.Load()), attr=name, ctx=ast.Load()),
            args=resolved_qubits + args,
            keywords=[]
        ))

    def measure(self, qubit: ast.expr, clbit: Optional[ast.expr] = None) -> ast.stmt:
        self.has_measurements = True
        # Braket SDK (Python) doesn't support mid-circuit measurement with feedback in the standard Circuit DSL easily.
        # Usually, you measure everything at the end.
        # We'll emit a comment or a result type addition if it's a specific measurement.
        if clbit:
            # Placeholder for measurement logic: classical_bit[i] = result
            return ast.Expr(value=ast.Constant(value=f"Note: Mid-circuit measurement of {ast.unparse(qubit)} to {ast.unparse(clbit)} requested."))
        
        return ast.Expr(value=ast.Constant(value=f"Note: Measurement of {ast.unparse(qubit)} requested."))

    def if_block(self, condition: ast.expr, then_body: List[ast.stmt], else_body: Optional[List[ast.stmt]] = None) -> ast.stmt:
        # Braket SDK doesn't support if_test in the circuit.
        # We'll fall back to standard Python 'if' which might work if the condition is classical/static.
        return ast.If(test=condition, body=then_body, orelse=else_body or [])

    def while_loop(self, condition: ast.expr, body: List[ast.stmt]) -> ast.stmt:
        return ast.While(test=condition, body=body, orelse=[])

    def for_loop(self, iterator: str, range_obj: ast.expr, body: List[ast.stmt]) -> ast.stmt:
        return ast.For(target=ast.Name(id=iterator, ctx=ast.Store()), iter=range_obj, body=body, orelse=[])

    def alias(self, name: str, value: ast.expr) -> ast.stmt:
        return ast.Assign(targets=[ast.Name(id=name, ctx=ast.Store())], value=value)

    def classical_assignment(self, lvalue: ast.expr, rvalue: ast.expr, op: str) -> ast.stmt:
        # Standard Python assignment
        if op == "=":
            return ast.Assign(targets=[lvalue], value=rvalue)
        
        op_map = {
            "+=": ast.Add(), "-=": ast.Sub(), "*=": ast.Mult(), "/=": ast.Div(),
        }
        if op in op_map:
             return ast.AugAssign(target=lvalue, op=op_map[op], value=rvalue)
        
        return ast.Expr(value=ast.Constant(value=f"TODO: Unsupported assignment {op}"))

    def io_declaration(self, name: str, io_type: str, ast_type: Any) -> List[ast.stmt]:
        # Map to simple Python variables for Braket SDK inputs
        return [ast.Assign(targets=[ast.Name(id=name, ctx=ast.Store())], value=ast.Constant(value=0))]

    def end_program(self) -> List[ast.stmt]:
        return [
            ast.Expr(value=ast.Constant(value=" --- EXECUTION ---")),
            ast.Assign(
                targets=[ast.Name(id='device', ctx=ast.Store())],
                value=ast.Call(func=ast.Name(id='LocalSimulator', ctx=ast.Load()), args=[], keywords=[])
            ),
            ast.Assign(
                targets=[ast.Name(id='result', ctx=ast.Store())],
                value=ast.Call(
                    func=ast.Attribute(value=ast.Name(id='device', ctx=ast.Load()), attr='run', ctx=ast.Load()),
                    args=[ast.Name(id='c', ctx=ast.Load())],
                    keywords=[ast.keyword(arg='shots', value=ast.Constant(value=1000))]
                )
            ),
            ast.Assign(
                targets=[ast.Name(id='counts', ctx=ast.Store())],
                value=ast.Attribute(
                    value=ast.Call(func=ast.Attribute(value=ast.Name(id='result', ctx=ast.Load()), attr='result', ctx=ast.Load()), args=[], keywords=[]),
                    attr='measurement_counts',
                    ctx=ast.Load()
                )
            ),
            ast.Expr(value=ast.Call(func=ast.Name(id='print', ctx=ast.Load()), args=[ast.Name(id='counts', ctx=ast.Load())], keywords=[]))
        ]

    def binary_expression(self, lhs: ast.expr, rhs: ast.expr, op: str) -> ast.expr:
        op_map = {
            "==": ast.Eq(), "!=": ast.NotEq(), "<": ast.Lt(), "<=": ast.LtE(),
            ">": ast.Gt(), ">=": ast.GtE(), "&&": ast.And(), "||": ast.Or(),
            "+": ast.Add(), "-": ast.Sub(), "*": ast.Mult(), "/": ast.Div()
        }
        if op in ["&&", "||"]:
             return ast.BoolOp(op=op_map[op], values=[lhs, rhs])
        return ast.BinOp(left=lhs, op=op_map.get(op, ast.Add()), right=rhs)

    def unary_expression(self, expression: ast.expr, op: str) -> ast.expr:
        op_map = {"!": ast.Not(), "~": ast.Invert(), "-": ast.USub()}
        return ast.UnaryOp(op=op_map.get(op, ast.Not()), operand=expression)

    def cast_expression(self, expression: ast.expr, ast_type: Any) -> ast.expr:
        if isinstance(ast_type, qast.BoolType):
            builtin = "bool"
        elif isinstance(ast_type, (qast.FloatType, qast.AngleType)):
            builtin = "float"
        else:
            builtin = "int"
        return ast.Call(func=ast.Name(id=builtin, ctx=ast.Load()), args=[expression], keywords=[])

    def get_imports(self) -> List[ast.stmt]:
        return [ast.parse(imp).body[0] for imp in sorted(self.used_imports)]

