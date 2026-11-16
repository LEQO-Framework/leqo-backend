import ast
from typing import Any, List, Optional, Union

import openqasm3.ast as qast

from app.openqasm3.universal_transpiler import BaseSDKProvider

# Maps the gate names emitted by the merge/postprocess pipeline (Qiskit naming)
# onto the corresponding Amazon Braket ``Circuit`` method names. Gates that share
# a name between the two SDKs are passed through unchanged (see ``_PASSTHROUGH_GATES``).
_GATE_NAME_MAP = {
    "cx": "cnot",
    "ccx": "ccnot",
    "sdg": "si",
    "tdg": "ti",
    "sx": "v",
}

# Braket ``Circuit`` methods that accept the backend's gate name directly.
_PASSTHROUGH_GATES = {
    "h", "x", "y", "z", "s", "t", "i",
    "rx", "ry", "rz",
    "cnot", "cz", "cy", "swap",
    "ccnot", "cswap",
    "phaseshift", "cphaseshift",
    "si", "ti", "v", "vi",
    "xx", "yy", "zz", "iswap",
}

# Name of the runtime helper injected into the generated program. It collapses a
# one-element register slice such as ``[leqo_reg[0]]`` (the shape the merge
# pipeline produces) down to the bare integer index Braket gate methods expect.
_QUBIT_HELPER_NAME = "_leqo_qubit"


class BraketProvider(BaseSDKProvider):
    """
    Amazon Braket implementation of the :class:`BaseSDKProvider`.

    Generates Python AST nodes for the Amazon Braket SDK
    (``braket.circuits.Circuit`` executed on ``braket.devices.LocalSimulator``).

    The merged OpenQASM program declares a single global qubit register
    ``leqo_reg`` and threads every gate or measurement operand through a subscript
    into it. Emitting ``leqo_reg = list(range(N))`` as a real runtime object makes
    ``leqo_reg[i]`` evaluate to the integer ``i``, which Braket accepts directly as
    a qubit index. This removes any separate qubit bookkeeping and lets operands
    flow through exactly as the Qiskit provider threads ``leqo_reg[i]``.
    """

    def __init__(self) -> None:
        self.used_imports: set[str] = set()
        self.has_measurements = False
        self.has_parameters = False
        self.has_runtime_inputs = False
        self._needs_qubit_helper = False

    def start_program(self) -> List[ast.stmt]:
        self.used_imports.add("from braket.circuits import Circuit")
        self.used_imports.add("from braket.devices import LocalSimulator")

        return [
            ast.Assign(
                targets=[ast.Name(id="c", ctx=ast.Store())],
                value=ast.Call(func=ast.Name(id="Circuit", ctx=ast.Load()), args=[], keywords=[]),
            )
        ]

    def declare_qubit(self, name: str, size: int) -> List[ast.stmt]:
        # Keystone: realise the global register as a concrete list of indices, so
        # ``name[i]`` evaluates to the integer ``i`` and Braket gates accept it.
        return [
            ast.Assign(
                targets=[ast.Name(id=name, ctx=ast.Store())],
                value=ast.Call(
                    func=ast.Name(id="list", ctx=ast.Load()),
                    args=[
                        ast.Call(
                            func=ast.Name(id="range", ctx=ast.Load()),
                            args=[ast.Constant(value=size)],
                            keywords=[],
                        )
                    ],
                    keywords=[],
                ),
            )
        ]

    def declare_bit(self, name: str, size: int) -> List[ast.stmt]:
        # Braket has no classical register. The measurement-result bits declared by
        # the pipeline are kept as a plain Python list of host-static integers so the
        # generated program stays a real, runnable object; Braket reports measurement
        # outcomes through ``measurement_counts`` rather than into these bits.
        return [
            ast.Assign(
                targets=[ast.Name(id=name, ctx=ast.Store())],
                value=ast.List(elts=[ast.Constant(value=0) for _ in range(size)], ctx=ast.Load()),
            )
        ]

    def declare_classical_var(
        self,
        name: str,
        ast_type: Any,
        init_expr: Optional[ast.expr] = None,
    ) -> List[ast.stmt]:
        raise NotImplementedError(
            "Braket Circuit has no typed classical variable state; "
            f"cannot declare classical variable {name!r}."
        )

    def _normalize_operand(self, operand: ast.expr) -> ast.expr:
        """
        Normalise a single qubit operand to a bare Braket index expression.

        A one-element ``ast.List`` (``[leqo_reg[i]]``) is collapsed at build time to
        its sole element. A subscript such as ``leqo_reg[i]`` already evaluates to the
        integer index and is passed through unchanged. Anything else (typically a
        ``Name`` bound to a one-element list by the merge pipeline) is wrapped in the
        runtime ``_leqo_qubit`` helper, which flattens such slices at execution time.
        """
        if isinstance(operand, ast.List):
            if len(operand.elts) == 1:
                return operand.elts[0]
            return operand
        if isinstance(operand, ast.Subscript):
            return operand
        self._needs_qubit_helper = True
        return ast.Call(
            func=ast.Name(id=_QUBIT_HELPER_NAME, ctx=ast.Load()),
            args=[operand],
            keywords=[],
        )

    def _resolve_gate_name(self, name: str) -> str:
        if name in _GATE_NAME_MAP:
            return _GATE_NAME_MAP[name]
        if name in _PASSTHROUGH_GATES:
            return name
        raise NotImplementedError(
            f"Gate {name!r} has no known Amazon Braket Circuit equivalent."
        )

    def gate(self, name: str, qubits: List[ast.expr], args: List[ast.expr]) -> ast.stmt:
        braket_name = self._resolve_gate_name(name)
        resolved_qubits = [self._normalize_operand(q) for q in qubits]
        # Braket gate methods take (qubits..., angle), the reverse of Qiskit's
        # (angle, qubits...). Track free parameters so execution can be suppressed.
        for arg in args:
            if isinstance(arg, ast.Call) and isinstance(arg.func, ast.Name) and arg.func.id == "FreeParameter":
                self.has_parameters = True
        return ast.Expr(value=ast.Call(
            func=ast.Attribute(value=ast.Name(id="c", ctx=ast.Load()), attr=braket_name, ctx=ast.Load()),
            args=resolved_qubits + args,
            keywords=[],
        ))

    def reset(self, qubit: ast.expr) -> ast.stmt:
        raise NotImplementedError(
            "Amazon Braket Circuit has no in-circuit reset operation."
        )

    def measure(self, qubit: ast.expr, clbit: Optional[ast.expr] = None) -> ast.stmt:
        self.has_measurements = True
        # Braket measures into its own result distribution; the classical-bit target
        # carried by the pipeline has no Braket equivalent and is intentionally dropped.
        target = self._normalize_operand(qubit)
        return ast.Expr(value=ast.Call(
            func=ast.Attribute(value=ast.Name(id="c", ctx=ast.Load()), attr="measure", ctx=ast.Load()),
            args=[target],
            keywords=[],
        ))

    def if_block(
        self,
        condition: ast.expr,
        then_body: List[ast.stmt],
        else_body: Optional[List[ast.stmt]] = None,
    ) -> Union[ast.stmt, List[ast.stmt]]:
        raise NotImplementedError(
            "Amazon Braket Circuit has no in-circuit classical branching (if_block)."
        )

    def while_loop(self, condition: ast.expr, body: List[ast.stmt]) -> ast.stmt:
        raise NotImplementedError(
            "Amazon Braket Circuit has no in-circuit classical looping (while_loop)."
        )

    def for_loop(self, iterator: str, range_obj: ast.expr, body: List[ast.stmt]) -> ast.stmt:
        # A statically bounded for-loop is kept as a host-side Python ``for`` that
        # unrolls at build time by appending gates to the circuit. This is legitimate
        # for Braket: the loop runs while the program is constructed, not on device.
        return ast.For(
            target=ast.Name(id=iterator, ctx=ast.Store()),
            iter=range_obj,
            body=body,
            orelse=[],
        )

    def alias(self, name: str, value: ast.expr) -> ast.stmt:
        return ast.Assign(targets=[ast.Name(id=name, ctx=ast.Store())], value=value)

    def classical_assignment(self, lvalue: ast.expr, rvalue: ast.expr, op: str) -> ast.stmt:
        raise NotImplementedError(
            f"Amazon Braket Circuit has no in-circuit classical assignment (operator {op!r})."
        )

    def io_declaration(self, name: str, io_type: str, ast_type: Any) -> List[ast.stmt]:
        if io_type == "input" and isinstance(ast_type, (qast.AngleType, qast.FloatType)):
            self.has_parameters = True
            self.used_imports.add("from braket.circuits import FreeParameter")
            return [
                ast.Assign(
                    targets=[ast.Name(id=name, ctx=ast.Store())],
                    value=ast.Call(
                        func=ast.Name(id="FreeParameter", ctx=ast.Load()),
                        args=[ast.Constant(value=name)],
                        keywords=[],
                    ),
                )
            ]
        if io_type == "input":
            raise NotImplementedError(
                "Amazon Braket only supports angle/float inputs as free parameters; "
                f"input {name!r} has an unsupported type."
            )
        raise NotImplementedError(
            f"Amazon Braket Circuit has no equivalent for {io_type} declaration {name!r}."
        )

    def binary_expression(self, lhs: ast.expr, rhs: ast.expr, op: str) -> ast.expr:
        # Host-static arithmetic on parameter/angle expressions lowers to plain Python
        # operators, mirroring how FreeParameter expressions compose in Braket.
        op_map = {
            "+": ast.Add(), "-": ast.Sub(), "*": ast.Mult(), "/": ast.Div(),
        }
        if op in op_map:
            return ast.BinOp(left=lhs, op=op_map[op], right=rhs)
        raise NotImplementedError(
            f"Amazon Braket export does not support the binary operator {op!r}."
        )

    def unary_expression(self, expression: ast.expr, op: str) -> ast.expr:
        op_map = {"-": ast.USub(), "+": ast.UAdd()}
        if op in op_map:
            return ast.UnaryOp(op=op_map[op], operand=expression)
        raise NotImplementedError(
            f"Amazon Braket export does not support the unary operator {op!r}."
        )

    def cast_expression(self, expression: ast.expr, ast_type: Any) -> ast.expr:
        if isinstance(ast_type, (qast.FloatType, qast.AngleType)):
            return ast.Call(func=ast.Name(id="float", ctx=ast.Load()), args=[expression], keywords=[])
        if isinstance(ast_type, qast.IntType):
            raise NotImplementedError(
                "Signed OpenQASM int casts have no Amazon Braket equivalent."
            )
        if isinstance(ast_type, qast.UintType):
            return ast.Call(func=ast.Name(id="int", ctx=ast.Load()), args=[expression], keywords=[])
        raise NotImplementedError(
            f"Amazon Braket export does not support casting to {type(ast_type).__name__}."
        )

    def end_program(self) -> List[ast.stmt]:
        # Execution boilerplate is only meaningful when the program measures. A circuit
        # with unbound free parameters cannot run until values are supplied, so emit the
        # circuit and a note instead of an unrunnable device call (mirrors the Qiskit
        # provider's "provide values before execution" behaviour).
        if not self.has_measurements:
            return []

        boilerplate: List[ast.stmt] = [
            ast.Expr(value=ast.Constant(value=" --- EXECUTION ---")),
            ast.Assign(
                targets=[ast.Name(id="device", ctx=ast.Store())],
                value=ast.Call(func=ast.Name(id="LocalSimulator", ctx=ast.Load()), args=[], keywords=[]),
            ),
        ]

        if self.has_parameters or self.has_runtime_inputs:
            boilerplate.append(ast.Expr(value=ast.Constant(
                value="Note: External free parameters detected. Provide explicit values before execution."
            )))
            return boilerplate

        boilerplate.extend([
            ast.Assign(
                targets=[ast.Name(id="task", ctx=ast.Store())],
                value=ast.Call(
                    func=ast.Attribute(value=ast.Name(id="device", ctx=ast.Load()), attr="run", ctx=ast.Load()),
                    args=[ast.Name(id="c", ctx=ast.Load())],
                    keywords=[ast.keyword(arg="shots", value=ast.Constant(value=500))],
                ),
            ),
            ast.Assign(
                targets=[ast.Name(id="counts", ctx=ast.Store())],
                value=ast.Attribute(
                    value=ast.Call(
                        func=ast.Attribute(value=ast.Name(id="task", ctx=ast.Load()), attr="result", ctx=ast.Load()),
                        args=[],
                        keywords=[],
                    ),
                    attr="measurement_counts",
                    ctx=ast.Load(),
                ),
            ),
            ast.Expr(value=ast.Call(
                func=ast.Name(id="print", ctx=ast.Load()),
                args=[ast.Constant(value="Simulation Results (500 shots):"), ast.Name(id="counts", ctx=ast.Load())],
                keywords=[],
            )),
        ])

        return boilerplate

    def _build_qubit_helper(self) -> ast.stmt:
        """Define the ``_leqo_qubit`` runtime flattener prepended to the program."""
        operand = ast.Name(id="operand", ctx=ast.Load())
        is_one_element_list = ast.BoolOp(
            op=ast.And(),
            values=[
                ast.Call(
                    func=ast.Name(id="isinstance", ctx=ast.Load()),
                    args=[
                        operand,
                        ast.Tuple(
                            elts=[ast.Name(id="list", ctx=ast.Load()), ast.Name(id="tuple", ctx=ast.Load())],
                            ctx=ast.Load(),
                        ),
                    ],
                    keywords=[],
                ),
                ast.Compare(
                    left=ast.Call(func=ast.Name(id="len", ctx=ast.Load()), args=[operand], keywords=[]),
                    ops=[ast.Eq()],
                    comparators=[ast.Constant(value=1)],
                ),
            ],
        )
        return ast.FunctionDef(
            name=_QUBIT_HELPER_NAME,
            args=ast.arguments(
                posonlyargs=[],
                args=[ast.arg(arg="operand")],
                vararg=None,
                kwonlyargs=[],
                kw_defaults=[],
                kwarg=None,
                defaults=[],
            ),
            body=[
                ast.If(
                    test=is_one_element_list,
                    body=[ast.Return(value=ast.Subscript(
                        value=ast.Name(id="operand", ctx=ast.Load()),
                        slice=ast.Constant(value=0),
                        ctx=ast.Load(),
                    ))],
                    orelse=[],
                ),
                ast.Return(value=ast.Name(id="operand", ctx=ast.Load())),
            ],
            decorator_list=[],
        )

    def get_imports(self) -> List[ast.stmt]:
        from_imports: dict[str, set[str]] = {
            "braket.circuits": set(),
            "braket.devices": set(),
        }
        plain_imports: list[str] = []

        for imp in self.used_imports:
            if imp.startswith("from ") and " import " in imp:
                prefix, names = imp.split(" import ", 1)
                module = prefix.removeprefix("from ")
                if module in from_imports:
                    from_imports[module].update(name.strip() for name in names.split(","))
                    continue
            if imp.startswith("import"):
                plain_imports.append(imp)

        ordered_modules = ["braket.circuits", "braket.devices"]

        preamble: List[ast.stmt] = []
        for module in ordered_modules:
            names = sorted(from_imports[module])
            if names:
                preamble.append(
                    ast.ImportFrom(
                        module=module,
                        names=[ast.alias(name=name) for name in names],
                        level=0,
                    )
                )

        for imp in sorted(plain_imports):
            preamble.append(ast.parse(imp).body[0])

        if self._needs_qubit_helper:
            preamble.append(self._build_qubit_helper())

        return preamble
