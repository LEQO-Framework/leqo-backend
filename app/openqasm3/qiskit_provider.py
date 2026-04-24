import ast
from typing import Any, List, Optional, Union
import openqasm3.ast as qast
from app.openqasm3.universal_transpiler import BaseSDKProvider

class QiskitProvider(BaseSDKProvider):
    """
    Qiskit implementation of the BaseSDKProvider.
    Generates Python AST nodes compatible with Qiskit 2.x and Qiskit Aer.
    """

    def __init__(self):
        self.used_imports = set()
        self.has_measurements = False
        self.has_parameters = False
        self.has_runtime_inputs = False
        self.classical_expr_names = set()
        self.bool_names = set()

    def start_program(self) -> List[ast.stmt]:
        self.used_imports.add("from qiskit import QuantumCircuit, QuantumRegister, transpile")
        
        return [
            ast.Assign(
                targets=[ast.Name(id='qc', ctx=ast.Store())],
                value=ast.Call(func=ast.Name(id='QuantumCircuit', ctx=ast.Load()), args=[], keywords=[])
            ),
            ast.Assign(
                targets=[ast.Name(id='inputs_list', ctx=ast.Store())],
                value=ast.List(elts=[], ctx=ast.Load())
            )
        ]

    def declare_qubit(self, name: str, size: int) -> List[ast.stmt]:
        return [
            ast.Assign(
                targets=[ast.Name(id=name, ctx=ast.Store())],
                value=ast.Call(
                    func=ast.Name(id='QuantumRegister', ctx=ast.Load()),
                    args=[ast.Constant(value=size), ast.Constant(value=name)],
                    keywords=[]
                )
            ),
            ast.Expr(value=ast.Call(
                func=ast.Attribute(value=ast.Name(id='qc', ctx=ast.Load()), attr='add_register', ctx=ast.Load()),
                args=[ast.Name(id=name, ctx=ast.Load())],
                keywords=[]
            ))
        ]

    def declare_bit(self, name: str, size: int) -> List[ast.stmt]:
        self.used_imports.add("from qiskit import ClassicalRegister")
        return [
            ast.Assign(
                targets=[ast.Name(id=name, ctx=ast.Store())],
                value=ast.Call(
                    func=ast.Name(id='ClassicalRegister', ctx=ast.Load()),
                    args=[ast.Constant(value=size), ast.Constant(value=name)],
                    keywords=[]
                )
            ),
            ast.Expr(value=ast.Call(
                func=ast.Attribute(value=ast.Name(id='qc', ctx=ast.Load()), attr='add_register', ctx=ast.Load()),
                args=[ast.Name(id=name, ctx=ast.Load())],
                keywords=[]
            ))
        ]

    def declare_classical_var(self, name: str, ast_type: Any, init_expr: Optional[ast.expr] = None) -> List[ast.stmt]:
        self.used_imports.add("from qiskit.circuit.classical import types")
        self.used_imports.add("import qiskit.circuit.classical.expr as expr")
        self.classical_expr_names.add(name)
        if isinstance(ast_type, qast.BoolType):
            self.bool_names.add(name)
        q_type = self._map_classical_type(ast_type)
        typed_var = ast.Call(
            func=ast.Attribute(
                value=ast.Attribute(value=ast.Name(id='expr', ctx=ast.Load()), attr='Var', ctx=ast.Load()),
                attr='new',
                ctx=ast.Load(),
            ),
            args=[ast.Constant(value=name), q_type],
            keywords=[],
        )

        if init_expr is None:
            return [
                ast.Assign(
                    targets=[ast.Name(id=name, ctx=ast.Store())],
                    value=typed_var,
                ),
                ast.Expr(value=ast.Call(
                    func=ast.Attribute(value=ast.Name(id='qc', ctx=ast.Load()), attr='add_uninitialized_var', ctx=ast.Load()),
                    args=[ast.Name(id=name, ctx=ast.Load())],
                    keywords=[],
                )),
            ]

        return [
            ast.Assign(
                targets=[ast.Name(id=name, ctx=ast.Store())],
                value=ast.Call(
                    func=ast.Attribute(value=ast.Name(id='qc', ctx=ast.Load()), attr='add_var', ctx=ast.Load()),
                    args=[typed_var, init_expr],
                    keywords=[],
                ),
            )
        ]

    def gate(self, name: str, qubits: List[ast.expr], args: List[ast.expr]) -> ast.stmt:
        call_args = args + qubits
        return ast.Expr(value=ast.Call(
            func=ast.Attribute(value=ast.Name(id='qc', ctx=ast.Load()), attr=name, ctx=ast.Load()),
            args=call_args,
            keywords=[]
        ))

    def measure(self, qubit: ast.expr, clbit: Optional[ast.expr] = None) -> ast.stmt:
        self.has_measurements = True
        args = [qubit]
        if clbit:
            args.append(clbit)
        
        return ast.Expr(value=ast.Call(
            func=ast.Attribute(value=ast.Name(id='qc', ctx=ast.Load()), attr='measure', ctx=ast.Load()),
            args=args,
            keywords=[]
        ))

    def if_block(self, condition: ast.expr, then_body: List[ast.stmt], else_body: Optional[List[ast.stmt]] = None) -> Union[ast.stmt, List[ast.stmt]]:
        self.used_imports.add("import qiskit.circuit.classical.expr as expr")
        
        with_item = ast.withitem(
            context_expr=ast.Call(
                func=ast.Attribute(value=ast.Name(id='qc', ctx=ast.Load()), attr='if_test', ctx=ast.Load()),
                args=[condition],
                keywords=[]
            ),
            optional_vars=ast.Name(id='_else', ctx=ast.Store()) if else_body else None
        )
        
        main_if = ast.With(items=[with_item], body=then_body)
        
        if else_body:
            else_with = ast.With(
                items=[ast.withitem(context_expr=ast.Name(id='_else', ctx=ast.Load()))],
                body=else_body
            )
            return [main_if, else_with]

        return main_if

    def while_loop(self, condition: ast.expr, body: List[ast.stmt]) -> ast.stmt:
        with_item = ast.withitem(
            context_expr=ast.Call(
                func=ast.Attribute(value=ast.Name(id='qc', ctx=ast.Load()), attr='while_loop', ctx=ast.Load()),
                args=[condition],
                keywords=[]
            )
        )
        return ast.With(items=[with_item], body=body)

    def for_loop(self, iterator: str, range_obj: ast.expr, body: List[ast.stmt]) -> ast.stmt:
        with_item = ast.withitem(
            context_expr=ast.Call(
                func=ast.Attribute(value=ast.Name(id='qc', ctx=ast.Load()), attr='for_loop', ctx=ast.Load()),
                args=[range_obj],
                keywords=[]
            ),
            optional_vars=ast.Name(id=iterator, ctx=ast.Store())
        )
        return ast.With(items=[with_item], body=body)

    def alias(self, name: str, value: ast.expr) -> ast.stmt:
        return ast.Assign(
            targets=[ast.Name(id=name, ctx=ast.Store())],
            value=value
        )

    def classical_assignment(self, lvalue: ast.expr, rvalue: ast.expr, op: str) -> ast.stmt:
        self.used_imports.add("import qiskit.circuit.classical.expr as expr")
        if op == "=":
            return ast.Expr(value=ast.Call(
                func=ast.Attribute(value=ast.Name(id='qc', ctx=ast.Load()), attr='store', ctx=ast.Load()),
                args=[lvalue, rvalue],
                keywords=[]
            ))
        
        op_map = {
            "+=": "add", "-=": "sub", "*=": "mul", "/=": "div",
            "&=": "bit_and", "|=": "bit_or", "^=": "bit_xor",
        }
        func_name = op_map.get(op)
        if func_name:
            calc = ast.Call(
                func=ast.Attribute(value=ast.Name(id='expr', ctx=ast.Load()), attr=func_name, ctx=ast.Load()),
                args=[lvalue, rvalue],
                keywords=[]
            )
            return ast.Expr(value=ast.Call(
                func=ast.Attribute(value=ast.Name(id='qc', ctx=ast.Load()), attr='store', ctx=ast.Load()),
                args=[lvalue, calc],
                keywords=[]
            ))

        raise NotImplementedError(f"Unsupported classical assignment operator: {op}")

    def io_declaration(self, name: str, io_type: str, ast_type: Any) -> List[ast.stmt]:
        if io_type == "input":
            if isinstance(ast_type, (qast.AngleType, qast.FloatType)):
                self.has_parameters = True
                self.used_imports.add("from qiskit.circuit import Parameter")
                return [ast.Assign(
                    targets=[ast.Name(id=name, ctx=ast.Store())],
                    value=ast.Call(func=ast.Name(id='Parameter', ctx=ast.Load()), args=[ast.Constant(value=name)], keywords=[])
                )]
            else:
                self.has_runtime_inputs = True
                self.classical_expr_names.add(name)
                if isinstance(ast_type, qast.BoolType):
                    self.bool_names.add(name)
                self.used_imports.add("from qiskit.circuit.classical import types")
                q_type = self._map_classical_type(ast_type)
                return [
                    ast.Assign(
                        targets=[ast.Name(id=name, ctx=ast.Store())],
                        value=ast.Call(
                            func=ast.Attribute(value=ast.Name(id='qc', ctx=ast.Load()), attr='add_input', ctx=ast.Load()),
                            args=[ast.Constant(value=name), q_type],
                            keywords=[]
                        )
                    ),
                    ast.Expr(value=ast.Call(
                        func=ast.Attribute(value=ast.Name(id='inputs_list', ctx=ast.Load()), attr='append', ctx=ast.Load()),
                        args=[ast.Name(id=name, ctx=ast.Load())],
                        keywords=[]
                    ))
                ]
        elif io_type == "output":
            self.classical_expr_names.add(name)
            if isinstance(ast_type, qast.BoolType):
                self.bool_names.add(name)
            self.used_imports.add("from qiskit.circuit.classical import types")
            self.used_imports.add("import qiskit.circuit.classical.expr as expr")
            q_type = self._map_classical_type(ast_type)
            return [
                ast.Assign(
                    targets=[ast.Name(id=name, ctx=ast.Store())],
                    value=ast.Call(
                        func=ast.Attribute(value=ast.Attribute(value=ast.Name(id='expr', ctx=ast.Load()), attr='Var', ctx=ast.Load()), attr='new', ctx=ast.Load()),
                        args=[ast.Constant(value=name), q_type],
                        keywords=[]
                    )
                ),
                ast.Expr(value=ast.Call(
                    func=ast.Attribute(value=ast.Name(id='qc', ctx=ast.Load()), attr='add_uninitialized_var', ctx=ast.Load()),
                    args=[ast.Name(id=name, ctx=ast.Load())],
                    keywords=[]
                ))
            ]
        return []

    def binary_expression(self, lhs: ast.expr, rhs: ast.expr, op: str) -> ast.expr:
        arithmetic_ops = {
            "+": ("add", ast.Add()),
            "-": ("sub", ast.Sub()),
            "*": ("mul", ast.Mult()),
            "/": ("div", ast.Div()),
        }
        if op in arithmetic_ops:
            if self._expression_uses_classical_expr(lhs) or self._expression_uses_classical_expr(rhs):
                self.used_imports.add("import qiskit.circuit.classical.expr as expr")
                func_name, _ = arithmetic_ops[op]
                return ast.Call(
                    func=ast.Attribute(value=ast.Name(id='expr', ctx=ast.Load()), attr=func_name, ctx=ast.Load()),
                    args=[lhs, rhs],
                    keywords=[],
                )
            _, python_op = arithmetic_ops[op]
            return ast.BinOp(left=lhs, op=python_op, right=rhs)

        self.used_imports.add("import qiskit.circuit.classical.expr as expr")
        self.used_imports.add("from qiskit.circuit.classical import types")

        op_funcs = {
            "==": "equal", "!=": "not_equal", "<": "less", "<=": "less_equal",
            ">": "greater", ">=": "greater_equal", "&&": "logic_and", "||": "logic_or",
            "&": "bit_and", "|": "bit_or", "^": "bit_xor"
        }

        if op in ["<", "<=", ">", ">=", "==", "!="]:
            is_boolean_comparison = self._expression_is_boolean(lhs) or self._expression_is_boolean(rhs)
            if not is_boolean_comparison:
                if not (isinstance(lhs, ast.Call) and getattr(lhs.func, 'attr', '') == 'cast'):
                    lhs = ast.Call(
                        func=ast.Attribute(value=ast.Name(id='expr', ctx=ast.Load()), attr='cast', ctx=ast.Load()),
                        args=[lhs, ast.Call(func=ast.Attribute(value=ast.Name(id='types', ctx=ast.Load()), attr='Uint', ctx=ast.Load()), args=[ast.Constant(value=32)], keywords=[])],
                        keywords=[]
                    )
                if not (isinstance(rhs, ast.Call) and getattr(rhs.func, 'attr', '') == 'cast'):
                    rhs = ast.Call(
                        func=ast.Attribute(value=ast.Name(id='expr', ctx=ast.Load()), attr='cast', ctx=ast.Load()),
                        args=[rhs, ast.Call(func=ast.Attribute(value=ast.Name(id='types', ctx=ast.Load()), attr='Uint', ctx=ast.Load()), args=[ast.Constant(value=32)], keywords=[])],
                        keywords=[]
                    )
            
        func_name = op_funcs.get(op)
        if func_name is None:
            raise NotImplementedError(f"Unsupported binary operator: {op}")
        return ast.Call(
            func=ast.Attribute(value=ast.Name(id='expr', ctx=ast.Load()), attr=func_name, ctx=ast.Load()),
            args=[lhs, rhs],
            keywords=[]
        )

    def unary_expression(self, expression: ast.expr, op: str) -> ast.expr:
        if op in {"-", "+"}:
            if self._expression_uses_classical_expr(expression):
                self.used_imports.add("import qiskit.circuit.classical.expr as expr")
                if op == "+":
                    return expression
                return ast.Call(
                    func=ast.Attribute(value=ast.Name(id='expr', ctx=ast.Load()), attr='mul', ctx=ast.Load()),
                    args=[ast.Constant(value=-1), expression],
                    keywords=[],
                )
            unary_ops = {"-": ast.USub(), "+": ast.UAdd()}
            return ast.UnaryOp(op=unary_ops[op], operand=expression)

        self.used_imports.add("import qiskit.circuit.classical.expr as expr")
        op_funcs = {"!": "logic_not", "~": "bit_not"}
        func_name = op_funcs.get(op)
        if func_name is None:
            raise NotImplementedError(f"Unsupported unary operator: {op}")
        return ast.Call(
            func=ast.Attribute(value=ast.Name(id='expr', ctx=ast.Load()), attr=func_name, ctx=ast.Load()),
            args=[expression],
            keywords=[]
        )

    def cast_expression(self, expression: ast.expr, ast_type: Any) -> ast.expr:
        if isinstance(ast_type, qast.IntType):
            raise NotImplementedError("Signed OpenQASM int is not supported by the Qiskit classical type system target.")

        if self._expression_uses_classical_expr(expression):
            self.used_imports.add("import qiskit.circuit.classical.expr as expr")
            self.used_imports.add("from qiskit.circuit.classical import types")
            return ast.Call(
                func=ast.Attribute(value=ast.Name(id='expr', ctx=ast.Load()), attr='cast', ctx=ast.Load()),
                args=[expression, self._map_classical_type(ast_type)],
                keywords=[],
            )

        if isinstance(ast_type, qast.BoolType):
            builtin = "bool"
        elif isinstance(ast_type, (qast.FloatType, qast.AngleType)):
            builtin = "float"
        else:
            builtin = "int"
        return ast.Call(func=ast.Name(id=builtin, ctx=ast.Load()), args=[expression], keywords=[])

    def end_program(self) -> List[ast.stmt]:
        if not self.has_measurements:
            return []

        self.used_imports.add("from qiskit_aer import AerSimulator")
        
        boilerplate = [
            ast.Expr(value=ast.Constant(value=" --- EXECUTION ---")),
            ast.Assign(
                targets=[ast.Name(id='simulator', ctx=ast.Store())],
                value=ast.Call(func=ast.Name(id='AerSimulator', ctx=ast.Load()), args=[], keywords=[])
            ),
            ast.Assign(
                targets=[ast.Name(id='compiled_circuit', ctx=ast.Store())],
                value=ast.Call(
                    func=ast.Name(id='transpile', ctx=ast.Load()),
                    args=[ast.Name(id='qc', ctx=ast.Load()), ast.Name(id='simulator', ctx=ast.Load())],
                    keywords=[]
                )
            )
        ]

        boilerplate.append(ast.Expr(value=ast.Call(func=ast.Name(id='print', ctx=ast.Load()), args=[ast.Name(id='compiled_circuit', ctx=ast.Load())], keywords=[])))

        if self.has_parameters or self.has_runtime_inputs:
            missing_values = []
            if self.has_parameters:
                missing_values.append("parameter bindings")
            if self.has_runtime_inputs:
                missing_values.append("runtime inputs")
            boilerplate.append(ast.Expr(value=ast.Constant(value=f"Note: External {' and '.join(missing_values)} detected. Provide explicit values before execution.")))
            return boilerplate

        run_args = [ast.Name(id='compiled_circuit', ctx=ast.Load())]
        run_keywords = [ast.keyword(arg='shots', value=ast.Constant(value=500))]

        boilerplate.extend([
            ast.Assign(
                targets=[ast.Name(id='job', ctx=ast.Store())],
                value=ast.Call(
                    func=ast.Attribute(value=ast.Name(id='simulator', ctx=ast.Load()), attr='run', ctx=ast.Load()),
                    args=run_args,
                    keywords=run_keywords
                )
            ),
            ast.Assign(
                targets=[ast.Name(id='result_data', ctx=ast.Store())],
                value=ast.Call(func=ast.Attribute(value=ast.Name(id='job', ctx=ast.Load()), attr='result', ctx=ast.Load()), args=[], keywords=[])
            ),
            ast.Assign(
                targets=[ast.Name(id='counts', ctx=ast.Store())],
                value=ast.Call(
                    func=ast.Attribute(value=ast.Name(id='result_data', ctx=ast.Load()), attr='get_counts', ctx=ast.Load()),
                    args=[ast.Name(id='qc', ctx=ast.Load())],
                    keywords=[]
                )
            ),
            ast.Expr(value=ast.Call(
                func=ast.Name(id='print', ctx=ast.Load()),
                args=[ast.Constant(value='Simulation Results (500 shots):'), ast.Name(id='counts', ctx=ast.Load())],
                keywords=[]
            ))
        ])

        return boilerplate

    def _map_classical_type(self, ast_type: Any) -> ast.expr:
        size = 32
        if hasattr(ast_type, "size") and ast_type.size is not None:
            size = int(ast_type.size.value if hasattr(ast_type.size, 'value') else ast_type.size)

        if isinstance(ast_type, qast.IntType):
            raise NotImplementedError("Signed OpenQASM int is not supported by the Qiskit classical type system target.")

        if isinstance(ast_type, qast.BoolType):
            return ast.Call(func=ast.Attribute(value=ast.Name(id='types', ctx=ast.Load()), attr='Bool', ctx=ast.Load()), args=[], keywords=[])

        if isinstance(ast_type, qast.BitType):
            bit_size = 1 if getattr(ast_type, "size", None) is None else size
            return ast.Call(
                func=ast.Attribute(value=ast.Name(id='types', ctx=ast.Load()), attr='Uint', ctx=ast.Load()),
                args=[ast.Constant(value=bit_size)],
                keywords=[]
            )

        if isinstance(ast_type, (qast.FloatType, qast.AngleType)):
            return ast.Call(
                func=ast.Attribute(value=ast.Name(id='types', ctx=ast.Load()), attr='Float', ctx=ast.Load()),
                args=[],
                keywords=[]
            )

        return ast.Call(
            func=ast.Attribute(value=ast.Name(id='types', ctx=ast.Load()), attr='Uint', ctx=ast.Load()),
            args=[ast.Constant(value=size)],
            keywords=[]
        )

    def get_imports(self) -> List[ast.stmt]:
        from_imports = {
            "qiskit": set(),
            "qiskit.circuit": set(),
            "qiskit.circuit.classical": set(),
            "qiskit_aer": set(),
        }
        plain_imports = []

        for imp in self.used_imports:
            if imp.startswith("from ") and " import " in imp:
                prefix, names = imp.split(" import ", 1)
                module = prefix.removeprefix("from ")
                if module in from_imports:
                    from_imports[module].update(name.strip() for name in names.split(","))
                    continue
            if imp.startswith("import"):
                plain_imports.append(imp)

        ordered_modules = [
            "qiskit",
            "qiskit.circuit",
            "qiskit.circuit.classical",
            "qiskit_aer",
        ]

        sorted_imports = []
        for module in ordered_modules:
            names = sorted(from_imports[module])
            if names:
                sorted_imports.append(
                    ast.ImportFrom(
                        module=module,
                        names=[ast.alias(name=name) for name in names],
                        level=0,
                    )
                )

        for imp in sorted(plain_imports):
            sorted_imports.append(ast.parse(imp).body[0])

        return sorted_imports

    def _expression_uses_classical_expr(self, node: ast.AST) -> bool:
        if isinstance(node, ast.Name):
            return node.id in self.classical_expr_names
        if isinstance(node, ast.Subscript):
            return self._expression_uses_classical_expr(node.value)
        if isinstance(node, ast.BinOp):
            return self._expression_uses_classical_expr(node.left) or self._expression_uses_classical_expr(node.right)
        if isinstance(node, ast.UnaryOp):
            return self._expression_uses_classical_expr(node.operand)
        if isinstance(node, ast.Call):
            return any(self._expression_uses_classical_expr(arg) for arg in node.args)
        if isinstance(node, ast.Attribute):
            return self._expression_uses_classical_expr(node.value)
        if isinstance(node, ast.List):
            return any(self._expression_uses_classical_expr(element) for element in node.elts)
        return False

    def _expression_is_boolean(self, node: ast.AST) -> bool:
        if isinstance(node, ast.Constant) and isinstance(node.value, bool):
            return True
        if isinstance(node, ast.Name):
            return node.id in self.bool_names
        if isinstance(node, ast.Subscript):
            return self._expression_is_boolean(node.value)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            return node.func.attr in {
                "equal", "not_equal", "less", "less_equal", "greater", "greater_equal",
                "logic_and", "logic_or", "logic_not",
            }
        return False





