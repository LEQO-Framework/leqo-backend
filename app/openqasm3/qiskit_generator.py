import openqasm3
import openqasm3.ast as qast


class QasmToQiskitTranspiler:
    """
    Translates an OpenQASM 3 AST into a string of executable Python/Qiskit code.
    Perfect for backend text generation and workflow engines.
    """

    def __init__(self):
        self.indent_level = 0
        self.code_lines = []

    def emit(self, line):
        """Helper to write a line of Python code with correct indentation."""
        indent = "    " * self.indent_level
        self.code_lines.append(f"{indent}{line}")

    # Start

    def visit(self, node):
        print(f"DEBUG: {self.get_clean_repr(node)}")
        if node is None: return None
        if isinstance(node, list):
            for item in node: self.visit(item)
            return None

        method_name = f"visit_{type(node).__name__}"
        visitor = getattr(self, method_name, self.generic_visit)
        return visitor(node)

    #Fallback if we visit something we dont know, also gives information about the unknown
    def generic_visit(self, node):
        class_name = type(node).__name__
        self.emit(f"# TODO: Implement {class_name}")

        # If the node has attributes (like an AST dataclass)
        if hasattr(node, "__dict__"):
            for key, value in node.__dict__.items():
                # Skip the noise
                if key in ('span', 'annotations'):
                    continue

                # Format the value nicely using your existing helper
                clean_value = self.get_clean_repr(value)

                # If the representation is very long (like a big block of statements),
                # we truncate it slightly or just print it as is.
                if len(clean_value) > 200:
                    clean_value = clean_value[:197] + "..."

                self.emit(f"#  - {key}: {clean_value}")
        else:
            self.emit(f"#  - Value: {repr(node)}")

    # Setup
    def visit_Program(self, node):
        # Write the Python imports and circuit initialization
        self.emit("from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister, transpile")
        self.emit("from qiskit_aer import AerSimulator")
        self.emit("")
        #could be expanded with annotation and parameters for how many qubits?

        self.emit("qc = QuantumCircuit()")
        self.emit("")

        # Visit the rest of the AST
        self.visit(node.statements)

        #Append execution, annotations could be used to decide if we want to execute,
        # annotation which simulator
        self.emit("simulator = AerSimulator()")
        self.emit("compiled_circuit = transpile(qc, simulator)")
        self.emit("print(compiled_circuit)")
        # annotation for shot amount
        self.emit("job = simulator.run(compiled_circuit, shots=500)")
        self.emit("result = job.result()")
        self.emit("counts = result.get_counts(qc)")
        self.emit("print('Simulation Results (500 shots):', counts)")

        # Return the final stitched-together Python script
        return "\n".join(self.code_lines)

    def visit_QubitDeclaration(self, node):
        """Translates `qubit[2] q;` -> `q = QuantumRegister(2, 'q'); qc.add_register(q)`"""
        name = node.qubit.name
        size = int(node.size.value) if node.size else 1

        self.emit(f"{name} = QuantumRegister({size}, '{name}')")
        self.emit(f"qc.add_register({name})")

    def visit_ClassicalDeclaration(self, node):
        """Translates `bit[2] mid;` -> `mid = ClassicalRegister(2, 'mid'); qc.add_register(mid)`"""
        name = node.identifier.name
        size = int(node.type.size.value)

        self.emit(f"{name} = ClassicalRegister({size}, '{name}')")
        self.emit(f"qc.add_register({name})")

    def visit_AliasStatement(self, node):
        """Translates `let alias = q[0:1];` -> `alias = q[0:2]`"""
        target_name = node.target.name
        value_str = self.format_alias_value(node.value)
        self.emit(f"{target_name} = {value_str}")

    # Gates
    def visit_QuantumGate(self, node):
        """Translates `x q[0];` -> `qc.x(q[0])`"""
        gate_name = node.name.name
        qubits_str = ", ".join([self.format_bit(q) for q in node.qubits])
        self.emit(f"qc.{gate_name}({qubits_str})")

    def visit_QuantumMeasurementStatement(self, node):
        """Translates `measure q[0] -> mid[0];` -> `qc.measure(q[0], mid[0])`"""
        qubit_str = self.format_bit(node.measure.qubit)
        if node.target:
            clbit_str = self.format_bit(node.target)
            self.emit(f"qc.measure({qubit_str}, {clbit_str})")

    #Control flow

    def visit_BranchingStatement(self, node):
        """Translates OpenQASM `if` to Python `with qc.if_test(...):`"""
        cond_str = self.visit(node.condition)

        # Write the Python context manager
        self.emit(f"with qc.if_test({cond_str}):")
        self.indent_level += 1
        for stmt in node.if_block:
            self.visit(stmt)
        self.indent_level -= 1

        # Increase indentation for the block contents
        if node.else_block:
            self.emit("else:")
            self.indent_level += 1
            for stmt in node.else_block:
                self.visit(stmt)
            self.indent_level -= 1

    def visit_WhileLoop(self, node):
        """Translates OpenQASM `while` to Python `with qc.while_loop(...):`"""
        cond_str = self.visit(node.while_condition)

        self.emit(f"with qc.while_loop({cond_str}):")
        self.indent_level += 1
        for stmt in node.block:
            self.visit(stmt)
        self.indent_level -= 1

    def visit_ForInLoop(self, node):
        """Translates OpenQASM `for i in [0:10]` to Python `with qc.for_loop(range(0, 11)) as i:`"""
        iterator_name = node.identifier.name

        # OpenQASM 3 For loops usually iterate over a RangeDefinition or a DiscreteSet
        if isinstance(node.set_declaration, qast.RangeDefinition):
            # Resolve start, end, and step. Default start to 0, step to 1 if omitted.
            start = int(self.resolve_value(node.set_declaration.start)) if node.set_declaration.start else 0
            end = int(self.resolve_value(node.set_declaration.end))
            step = int(self.resolve_value(node.set_declaration.step)) if node.set_declaration.step else 1

            # Python range is exclusive, OpenQASM is inclusive
            python_end = end + 1 if step > 0 else end - 1

            # Formatting the range string based on whether step/start are default
            if step == 1 and start == 0:
                range_args = f"{python_end}"
            elif step == 1:
                range_args = f"{start}, {python_end}"
            else:
                range_args = f"{start}, {python_end}, {step}"

            self.emit(f"with qc.for_loop(range({range_args})) as {iterator_name}:")

        elif isinstance(node.set_declaration, qast.DiscreteSet):
            # e.g., for i in {1, 2, 3}
            elements = [self.resolve_value(v) for v in node.set_declaration.values]
            list_elements = ", ".join(elements)
            self.emit(f"with qc.for_loop([{list_elements}]) as {iterator_name}:")

        else:
            self.emit(f"# WARNING: Unsupported ForLoop set declaration type: {type(node.set_declaration)}")
            self.emit(f"with qc.for_loop(range(0)) as {iterator_name}:")

        # Indent and process the block
        self.indent_level += 1
        for stmt in node.block:
            self.visit(stmt)
        self.indent_level -= 1

    def visit_Include(self, node):
        pass

    # Expression and Literal Parsing
    def visit_BinaryExpression(self, node):
        lhs = self.visit(node.lhs)
        rhs = self.visit(node.rhs)

        # OpenQASM 3 Enum names map to string symbols
        op_str = str(node.op).split('.')[-1]

        op_funcs = {
            "==": "expr.equal",
            "!=": "expr.not_equal",
            "<": "expr.less",
            "<=": "expr.less_equal",
            ">": "expr.greater",
            ">=": "expr.greater_equal",
            "&&": "expr.logic_and",
            "||": "expr.logic_or",
            "&": "expr.bit_and",
            "|": "expr.bit_or",
            "^": "expr.bit_xor"
        }

        func = op_funcs.get(op_str, f"UNKNOWN_OP_{op_str}")
        return f"{func}({lhs}, {rhs})"

    def visit_UnaryExpression(self, node):
        inner = self.visit(node.expression)
        op_str = str(node.op).split('.')[-1]

        op_funcs = {
            "!": "expr.logic_not",
            "~": "expr.bit_not",
        }
        func = op_funcs.get(op_str, f"UNKNOWN_OP_{op_str}")
        return f"{func}({inner})"

    def visit_Identifier(self, node):
        return node.name

    def visit_IndexedIdentifier(self, node):
        name = node.name.name
        # Handle simple indexing: q[0]
        idx_node = node.indices[0][0]
        idx = self.visit(idx_node) if hasattr(idx_node, 'value') else self.resolve_value(idx_node)
        return f"{name}[{idx}]"

    def visit_IntegerLiteral(self, node):
        return str(node.value)

    def visit_FloatLiteral(self, node):
        return str(node.value)

    def visit_BooleanLiteral(self, node):
        return str(node.value)

    # Helper
    def format_bit(self, node):
        """Converts `q[0]` AST node to the Python string `'q[0]'`"""
        if isinstance(node, qast.Identifier):
            return node.name
        if isinstance(node, qast.IndexedIdentifier):
            name = node.name.name
            index = int(node.indices[0][0].value)
            return f"{name}[{index}]"

    def resolve_value(self, node):
        """Converts literal AST nodes to integer strings"""
        if isinstance(node, int): return str(node)
        if isinstance(node.value, str): return str(int(node.value, 2))
        return str(node.value)

    def format_alias_value(self, node):
        """Translates the right side of an Alias statement into Python slicing or lists."""
        if isinstance(node, qast.Identifier):
            return node.name

        if isinstance(node, qast.IndexExpression):
            collection = self.format_alias_value(node.collection)

            # The AST sometimes wraps indices in a list
            idx = node.index[0] if isinstance(node.index, list) else node.index

            if isinstance(idx, qast.RangeDefinition):
                # Handle OpenQASM inclusive ranges -> Python exclusive slices
                start = int(self.resolve_value(idx.start)) if idx.start else 0
                end = int(self.resolve_value(idx.end)) if idx.end else None

                start_str = str(start) if start != 0 else ""
                end_str = str(end + 1) if end is not None else ""  # Python is exclusive!
                step_str = f":{self.resolve_value(idx.step)}" if idx.step else ""

                return f"{collection}[{start_str}:{end_str}{step_str}]"

            elif isinstance(idx, qast.DiscreteSet):
                # Handle Sets: q[{0, 1}] -> [q[0], q[1]]
                elements = [self.resolve_value(v) for v in idx.values]
                list_elements = ", ".join([f"{collection}[{e}]" for e in elements])
                return f"[{list_elements}]"

            else:
                # Standard single index
                return f"{collection}[{self.resolve_value(idx)}]"

#AST printing

    def get_clean_repr(self, node):
        """Recursively formats an AST node to be readable, removing spans and empty fields."""
        if node is None:
            return "None"

        # If it's a list, clean every item inside it
        if isinstance(node, list):
            return "[" + ", ".join(self.get_clean_repr(item) for item in node) + "]"

        # If it is an OpenQASM AST Node, reconstruct its string representation cleanly
        if isinstance(node, qast.QASMNode):
            class_name = type(node).__name__
            fields = []

            for key, value in node.__dict__.items():
                # SKIP the noise!
                if key in ('span', 'annotations'):
                    continue
                # Optional: skip fields that are None to make it even shorter
                if value is None:
                    continue

                # Recursively clean the value
                clean_value = self.get_clean_repr(value)
                fields.append(f"{key}={clean_value}")

            return f"{class_name}({', '.join(fields)})"

        # For primitive types (ints, strings) or Enums (like BinaryOperator.==)
        return str(node) if hasattr(node, "name") and "Operator" in str(type(node)) else repr(node)

# Test
if __name__ == "__main__":
    source = """
        OPENQASM 3.0;

        qubit[2] q;
        bit[2] mid;

        // 1. Initial measurement (q starts at 0, so mid becomes "00")
        measure q[0] -> mid[0];
        measure q[1] -> mid[1];

        // 2. TRIGGER THE WHILE LOOP
        // mid is "00", so we enter the loop!
        while (mid == "00") {
            x q[0];
            x q[1];
            measure q[0] -> mid[0];
            measure q[1] -> mid[1];
            // Now mid is "11", so the loop will break on the next check.
        }

        // 3. TRIGGER THE IF STATEMENT
        // mid is now "11", so we enter the if-block!
        if (mid == "11") {
            x q[0]; // Flip q[0] back to 0
        }

        // 4. Final measurement to see the results
        measure q[0] -> mid[0];
        measure q[1] -> mid[1];
        """
    source2="""
        OPENQASM 3.1;
        @leqo.input 0
        qubit[1] leqo_af4ab0884f0d5aa3a87cdf116e20543e_pass_node_declaration_0;
        let leqo_af4ab0884f0d5aa3a87cdf116e20543e_pass_node_alias_0 = leqo_af4ab0884f0d5aa3a87cdf116e20543e_pass_node_declaration_0;
        let leqo_af4ab0884f0d5aa3a87cdf116e20543e_loop_reg = leqo_af4ab0884f0d5aa3a87cdf116e20543e_pass_node_declaration_0;
        for int i in [0:10] {
          let leqo_0f22e31da1be57ea8479533ced7f8788_q = leqo_af4ab0884f0d5aa3a87cdf116e20543e_loop_reg[{0}];
          h leqo_0f22e31da1be57ea8479533ced7f8788_q;
          let leqo_0f22e31da1be57ea8479533ced7f8788__out = leqo_0f22e31da1be57ea8479533ced7f8788_q;
        }
        let leqo_7fa32f00e76450ae8a3f1fca36e8517a_pass_node_declaration_0 = leqo_af4ab0884f0d5aa3a87cdf116e20543e_loop_reg[{0}];
        @leqo.output 0
        let leqo_7fa32f00e76450ae8a3f1fca36e8517a_pass_node_alias_0 = leqo_7fa32f00e76450ae8a3f1fca36e8517a_pass_node_declaration_0;
        """
    source3="""
        OPENQASM 3.1;
        @leqo.input 0
        int[32] leqo_0f993612d9615486a55a1cd3d4158b45_pass_node_declaration_0;
        let leqo_0f993612d9615486a55a1cd3d4158b45_pass_node_alias_0 = leqo_0f993612d9615486a55a1cd3d4158b45_pass_node_declaration_0;
        @leqo.input 1
        qubit[1] leqo_0f993612d9615486a55a1cd3d4158b45_pass_node_declaration_1;
        let leqo_0f993612d9615486a55a1cd3d4158b45_pass_node_alias_1 = leqo_0f993612d9615486a55a1cd3d4158b45_pass_node_declaration_1;
        let leqo_0f993612d9615486a55a1cd3d4158b45_loop_reg = leqo_0f993612d9615486a55a1cd3d4158b45_pass_node_declaration_1;
        while (leqo_0f993612d9615486a55a1cd3d4158b45_pass_node_declaration_0 < 5) {
          let leqo_40da8ad6eead5c82b58a503771301f03_q = leqo_0f993612d9615486a55a1cd3d4158b45_loop_reg[{0}];
          x leqo_40da8ad6eead5c82b58a503771301f03_q;
          let leqo_40da8ad6eead5c82b58a503771301f03__out = leqo_40da8ad6eead5c82b58a503771301f03_q;
        }
        int[32] leqo_e8d241f16cf659c4a39a85d20102754b_pass_node_declaration_0;
        @leqo.output 0
        let leqo_e8d241f16cf659c4a39a85d20102754b_pass_node_alias_0 = leqo_e8d241f16cf659c4a39a85d20102754b_pass_node_declaration_0;
        let leqo_e8d241f16cf659c4a39a85d20102754b_pass_node_declaration_1 = leqo_0f993612d9615486a55a1cd3d4158b45_loop_reg[{0}];
        @leqo.output 1
        let leqo_e8d241f16cf659c4a39a85d20102754b_pass_node_alias_1 = leqo_e8d241f16cf659c4a39a85d20102754b_pass_node_declaration_1;
        """
    source4="""
        OPENQASM 3.1;
        @leqo.input 0
        bit[1] leqo_0d7d0680d06d59c09b9b91da17539e91_pass_node_declaration_0;
        let leqo_0d7d0680d06d59c09b9b91da17539e91_pass_node_alias_0 = leqo_0d7d0680d06d59c09b9b91da17539e91_pass_node_declaration_0;
        @leqo.input 1
        qubit[1] leqo_0d7d0680d06d59c09b9b91da17539e91_pass_node_declaration_1;
        let leqo_0d7d0680d06d59c09b9b91da17539e91_pass_node_alias_1 = leqo_0d7d0680d06d59c09b9b91da17539e91_pass_node_declaration_1;
        let leqo_0d7d0680d06d59c09b9b91da17539e91_if_reg = leqo_0d7d0680d06d59c09b9b91da17539e91_pass_node_declaration_1;
        if (leqo_0d7d0680d06d59c09b9b91da17539e91_pass_node_declaration_0 == 3) {
          let leqo_0f22e31da1be57ea8479533ced7f8788_q = leqo_0d7d0680d06d59c09b9b91da17539e91_if_reg[{0}];
          h leqo_0f22e31da1be57ea8479533ced7f8788_q;
          let leqo_0f22e31da1be57ea8479533ced7f8788__out = leqo_0f22e31da1be57ea8479533ced7f8788_q;
        } else {
          let leqo_40da8ad6eead5c82b58a503771301f03_q = leqo_0d7d0680d06d59c09b9b91da17539e91_if_reg[{0}];
          x leqo_40da8ad6eead5c82b58a503771301f03_q;
          let leqo_40da8ad6eead5c82b58a503771301f03__out = leqo_40da8ad6eead5c82b58a503771301f03_q;
        }
        bit[1] leqo_7dae0626857c5efa9c4298cb0eac4124_pass_node_declaration_0;
        @leqo.output 0
        let leqo_7dae0626857c5efa9c4298cb0eac4124_pass_node_alias_0 = leqo_7dae0626857c5efa9c4298cb0eac4124_pass_node_declaration_0;
        let leqo_7dae0626857c5efa9c4298cb0eac4124_pass_node_declaration_1 = leqo_0d7d0680d06d59c09b9b91da17539e91_if_reg[{0}];
        @leqo.output 1
        let leqo_7dae0626857c5efa9c4298cb0eac4124_pass_node_alias_1 = leqo_7dae0626857c5efa9c4298cb0eac4124_pass_node_declaration_1;
        """

    source5="""
    OPENQASM 3.1;
    qubit[2] q;
    
    // A simple for loop from 0 to 10 (inclusive)
    for int i in [0:10] {
        h q[0];
        cx q[0], q[1];
    }
    """

    source6="""
    OPENQASM 3.1;
    qubit[1] q;
    bit[2] a;
    bit[2] b;
    bit[2] c;

    // Test a deeply nested logical condition
    if (a == 1 && (b < 1 || b >= 10) && c != 0) {
        x q[0];
    }
    """

    ast_node = openqasm3.parse(source6)
    transpiler = QasmToQiskitTranspiler()
    python_script = transpiler.visit(ast_node)

    print("--- GENERATED PYTHON SCRIPT ---")
    print(python_script)