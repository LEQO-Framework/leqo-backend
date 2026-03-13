import ast
from typing import Any, List, Optional, Union
import openqasm3.ast as qast
from app.openqasm3.universal_transpiler import BaseSDKProvider

class QiskitProvider(BaseSDKProvider):
    """
    Qiskit implementation of the BaseSDKProvider.
    Generates Python AST nodes compatible with Qiskit 1.x and Qiskit Aer.
    """

    def __init__(self):
        self.used_imports = set()
        self.has_measurements = False
        self.has_parameters = False
        self.has_runtime_inputs = False

    def start_program(self) -> List[ast.stmt]:
        self.used_imports.add("from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister, transpile")
        
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
        
        return ast.Expr(value=ast.Constant(value=f"TODO: Unsupported assignment operator {op}"))

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
        self.used_imports.add("import qiskit.circuit.classical.expr as expr")
        self.used_imports.add("from qiskit.circuit.classical import types")
        
        op_funcs = {
            "==": "equal", "!=": "not_equal", "<": "less", "<=": "less_equal",
            ">": "greater", ">=": "greater_equal", "&&": "logic_and", "||": "logic_or",
            "&": "bit_and", "|": "bit_or", "^": "bit_xor"
        }
        
        if op in ["<", "<=", ">", ">=", "==", "!="]:
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
            
        func_name = op_funcs.get(op, f"UNKNOWN_{op}")
        return ast.Call(
            func=ast.Attribute(value=ast.Name(id='expr', ctx=ast.Load()), attr=func_name, ctx=ast.Load()),
            args=[lhs, rhs],
            keywords=[]
        )

    def unary_expression(self, expression: ast.expr, op: str) -> ast.expr:
        self.used_imports.add("import qiskit.circuit.classical.expr as expr")
        op_funcs = {"!": "logic_not", "~": "bit_not"}
        func_name = op_funcs.get(op, f"UNKNOWN_{op}")
        return ast.Call(
            func=ast.Attribute(value=ast.Name(id='expr', ctx=ast.Load()), attr=func_name, ctx=ast.Load()),
            args=[expression],
            keywords=[]
        )

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

        if self.has_parameters:
            boilerplate.extend([
                ast.Expr(value=ast.Constant(value="Note: Parameters detected. Binding placeholders for demonstration.")),
                ast.For(
                    target=ast.Name(id='param', ctx=ast.Store()),
                    iter=ast.Attribute(value=ast.Name(id='compiled_circuit', ctx=ast.Load()), attr='parameters', ctx=ast.Load()),
                    body=[
                        ast.Expr(value=ast.Call(
                            func=ast.Attribute(value=ast.Name(id='compiled_circuit', ctx=ast.Load()), attr='assign_parameters', ctx=ast.Load()),
                            args=[ast.Dict(keys=[ast.Name(id='param', ctx=ast.Load())], values=[ast.Constant(value=0.1)])],
                            keywords=[ast.keyword(arg='inplace', value=ast.Constant(value=True))]
                        ))
                    ],
                    orelse=[]
                )
            ])

        boilerplate.append(ast.Expr(value=ast.Call(func=ast.Name(id='print', ctx=ast.Load()), args=[ast.Name(id='compiled_circuit', ctx=ast.Load())], keywords=[])))

        run_args = [ast.Name(id='compiled_circuit', ctx=ast.Load())]
        run_keywords = [ast.keyword(arg='shots', value=ast.Constant(value=500))]

        if self.has_runtime_inputs:
            boilerplate.extend([
                ast.Expr(value=ast.Constant(value="Note: Classical runtime inputs detected. Defaulting to 0.")),
                ast.Assign(targets=[ast.Name(id='input_map', ctx=ast.Store())], value=ast.Dict(keys=[], values=[])),
                ast.For(
                    target=ast.Name(id='inp', ctx=ast.Store()),
                    iter=ast.Name(id='inputs_list', ctx=ast.Load()),
                    body=[ast.Assign(
                        targets=[ast.Subscript(value=ast.Name(id='input_map', ctx=ast.Load()), slice=ast.Name(id='inp', ctx=ast.Load()), ctx=ast.Store())],
                        value=ast.Constant(value=0)
                    )],
                    orelse=[]
                )
            ])
            run_keywords.append(ast.keyword(arg='inputs', value=ast.Name(id='input_map', ctx=ast.Load())))

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
        
        if isinstance(ast_type, qast.BoolType):
             return ast.Call(func=ast.Attribute(value=ast.Name(id='types', ctx=ast.Load()), attr='Bool', ctx=ast.Load()), args=[], keywords=[])
        
        return ast.Call(
            func=ast.Attribute(value=ast.Name(id='types', ctx=ast.Load()), attr='Uint', ctx=ast.Load()),
            args=[ast.Constant(value=size)],
            keywords=[]
        )

    def get_imports(self) -> List[ast.stmt]:
        import_groups = {
            "from qiskit": [],
            "from qiskit.circuit": [],
            "from qiskit.circuit.classical": [],
            "from qiskit_aer": [],
            "import": []
        }
        
        for imp in self.used_imports:
            if imp.startswith("from qiskit import"):
                import_groups["from qiskit"].append(imp)
            elif imp.startswith("from qiskit.circuit import"):
                import_groups["from qiskit.circuit"].append(imp)
            elif imp.startswith("from qiskit.circuit.classical import"):
                import_groups["from qiskit.circuit.classical"].append(imp)
            elif imp.startswith("from qiskit_aer"):
                import_groups["from qiskit_aer"].append(imp)
            elif imp.startswith("import"):
                import_groups["import"].append(imp)
        
        sorted_imports = []
        for key in ["from qiskit", "from qiskit.circuit", "from qiskit.circuit.classical", "from qiskit_aer", "import"]:
            for imp in sorted(import_groups[key]):
                sorted_imports.append(ast.parse(imp).body[0])
        
        return sorted_imports
