import openqasm3
import openqasm3.ast as qast


class QasmToQiskitTranspiler:
    """
    Translates an OpenQASM 3 AST into a string of executable Python/Qiskit code.
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
        #print(f"DEBUG: {self.get_clean_repr(node)}")
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
        # Pre-scan the AST to determine necessary imports and execution flags
        uses_parameters = False
        uses_classical_vars = False
        uses_expr_logic = False

        # Safely scan only AST nodes
        def scan(n):
            nonlocal uses_parameters, uses_classical_vars, uses_expr_logic

            if isinstance(n, list):
                for item in n:
                    scan(item)
            elif isinstance(n, qast.QASMNode):
                # CHECK 1: IO Declarations
                if isinstance(n, qast.IODeclaration):
                    if isinstance(n.type, (qast.AngleType, qast.FloatType)) and n.io_identifier.name == "input":
                        uses_parameters = True
                    elif isinstance(n.type, (qast.IntType, qast.UintType, qast.BitType, qast.BoolType)):
                        uses_classical_vars = True

                # CHECK 2: Standard Classical Declarations
                # This ensures "bit[2] b" triggers the import of "types"
                if isinstance(n, qast.ClassicalDeclaration):
                    uses_classical_vars = True

                # CHECK 3: Expression Logic
                if isinstance(n, (qast.BinaryExpression, qast.UnaryExpression, qast.ClassicalAssignment)):
                    uses_expr_logic = True

                # Recurse
                for key, value in n.__dict__.items():
                    if key not in ('span', 'annotations'):
                        if isinstance(value, (qast.QASMNode, list)):
                            scan(value)

        scan(node.statements)

        # --- EMIT IMPORTS ---
        self.emit("from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister, transpile")
        if uses_parameters:
            self.emit("from qiskit.circuit import Parameter")
        if uses_classical_vars:
            self.emit("from qiskit.circuit.classical import types")
        if uses_expr_logic or uses_classical_vars:
            self.emit("import qiskit.circuit.classical.expr as expr")

        #TODO: add option to decide if and which simulator or completely split qiskit code and execution
        self.emit("from qiskit_aer import AerSimulator")
        self.emit("")

        # --- CIRCUIT INIT ---
        self.emit("qc = QuantumCircuit()")
        self.emit("inputs_list = []")  # <--- NEW: Track inputs explicitly
        self.emit("")

        # --- VISIT BODY ---
        self.visit(node.statements)

        # --- EXECUTION BLOCK ---
        self.emit("")
        self.emit("# --- EXECUTION ---")
        self.emit("simulator = AerSimulator()")
        self.emit("compiled_circuit = transpile(qc, simulator)")

        # Parameter binding
        if uses_parameters:
            self.emit("# NOTE: Parameters detected. Binding placeholders for demonstration.")
            self.emit("for param in compiled_circuit.parameters:")
            self.emit("    compiled_circuit.assign_parameters({param: 0.1}, inplace=True)")

        self.emit("print(compiled_circuit)")

        # Smart run command
        run_args = "compiled_circuit, shots=500"
        if uses_classical_vars:
            self.emit("# NOTE: Classical inputs detected. Defaulting inputs to 10.")
            self.emit("input_map = {}")
            self.emit("for inp in inputs_list:")  # <--- CHANGED: Use our tracked list
            self.emit("    input_map[inp] = 10  # Default value")
            run_args += ", inputs=input_map"

        self.emit(f"job = simulator.run({run_args})")
        self.emit("result_data = job.result()")
        self.emit("counts = result_data.get_counts(qc)")
        self.emit("print('Simulation Results (500 shots):', counts)")

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
        """Translates `rx(theta) q[0];` -> `qc.rx(theta, q[0])`"""
        gate_name = node.name.name

        # Resolve arguments (e.g., theta, phi, 3.14)
        args_str = ""
        if node.arguments:
            # Recursively visit arguments to handle Expressions or Identifiers
            processed_args = [self.visit(arg) for arg in node.arguments]
            args_str = ", ".join(processed_args)

        qubits_str = ", ".join([self.format_bit(q) for q in node.qubits])

        # Qiskit syntax: qc.gate(params..., qubits...)
        if args_str:
            self.emit(f"qc.{gate_name}({args_str}, {qubits_str})")
        else:
            self.emit(f"qc.{gate_name}({qubits_str})")

    def visit_QuantumMeasurementStatement(self, node):
        """Translates `measure q[0] -> mid[0];` -> `qc.measure(q[0], mid[0])`"""
        qubit_str = self.format_bit(node.measure.qubit)
        if node.target:
            clbit_str = self.format_bit(node.target)
            self.emit(f"qc.measure({qubit_str}, {clbit_str})")

    #Control flow

    def visit_BranchingStatement(self, node):
        """Translates OpenQASM `if/else` to Qiskit `with qc.if_test() as _else:`"""
        cond_str = self.visit(node.condition)

        # If there is an else block, we must capture the context manager
        if node.else_block:
            self.emit(f"with qc.if_test({cond_str}) as _else:")
        else:
            self.emit(f"with qc.if_test({cond_str}):")

        self.indent_level += 1
        for stmt in node.if_block:
            self.visit(stmt)
        self.indent_level -= 1

        # Write the else block using the captured context manager
        if node.else_block:
            self.emit("with _else:")
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

        # --- Integer Promotion ---
        # Include == and != so bit[1] == 3 doesn't crash Qiskit!
        comparison_ops = ["<", "<=", ">", ">=", "==", "!="]

        if op_str in comparison_ops:
            lhs = f"expr.cast({lhs}, types.Uint(32))"
            rhs = f"expr.cast({rhs}, types.Uint(32))"

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

    def visit_BitstringLiteral(self, node):
        """Translates Bitstring literals like "11" into their integer value (3)"""
        return str(node.value)

    def visit_ClassicalAssignment(self, node):
        """Translates `result = n;` -> `qc.store(result, n)`"""
        # Resolve the left and right sides
        lvalue = self.visit(node.lvalue)
        rvalue = self.visit(node.rvalue)

        op_str = str(node.op).split('.')[-1]

        if op_str == "=":
            self.emit(f"qc.store({lvalue}, {rvalue})")
        else:
            # Map compound assignments to Qiskit expr operations
            op_map = {
                "+=": "expr.add",
                "-=": "expr.sub",
                "*=": "expr.mul",
                "/=": "expr.div",
                "&=": "expr.bit_and",
                "|=": "expr.bit_or",
                "^=": "expr.bit_xor",
            }
            func = op_map.get(op_str)
            if func:
                self.emit(f"qc.store({lvalue}, {func}({lvalue}, {rvalue}))")
            else:
                self.emit(f"# WARNING: Unsupported assignment operator {op_str}")
                self.emit(f"qc.store({lvalue}, {rvalue})")

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

    def map_classical_type(self, ast_type):
        """Maps OpenQASM AST types to Qiskit classical types."""
        # Qiskit's classical type system currently only implements `Uint` and `Bool`.
        # Signed `Int` and `Float` variables are not yet supported in Qiskit,
        # so we map all integer/bit types to unsigned integers (Uint).

        if isinstance(ast_type, qast.BoolType):
            return "types.Bool()"

        # For Int, Uint, and Bit, extract the size and fallback to Uint
        size = 32
        if hasattr(ast_type, "size") and ast_type.size is not None:
            size = int(self.resolve_value(ast_type.size))

        return f"types.Uint({size})"

    def visit_IODeclaration(self, node):
        """
        Translates:
          input angle theta -> theta = Parameter('theta')
          input int x       -> x = qc.add_input('x', types.Uint(32))
          output int y      -> y = expr.Var.new('y', types.Uint(32))
                               qc.add_uninitialized_var(y)
        """
        name = node.identifier.name
        io_mode = node.io_identifier.name

        if io_mode == "input":
            if isinstance(node.type, (qast.AngleType, qast.FloatType)):
                self.emit(f"{name} = Parameter('{name}')")
            else:
                q_type = self.map_classical_type(node.type)
                self.emit(f"{name} = qc.add_input('{name}', {q_type})")
                self.emit(f"inputs_list.append({name})")  # <--- NEW

        elif io_mode == "output":
            q_type = self.map_classical_type(node.type)
            # Create variable first, then add as uninitialized
            self.emit(f"{name} = expr.Var.new('{name}', {q_type})")
            self.emit(f"qc.add_uninitialized_var({name})")

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
    source1 = """
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
        /* --- INPUTS --- */
        @leqo.input 0
        qubit[1] q_main;
        let q_main_alias = q_main;
        
        /* --- LOGIC --- */
        // Create a reference to the qubit for the loop block
        let q_ptr = q_main;
        
        // Loop 10 times (i = 0, 1, ..., 9)
        for int i in [0:10] {
          // Apply Hadamard gate to the qubit inside the loop
          let q_inner = q_ptr[{0}];
          h q_inner;
          let q_inner_out = q_inner;
        }
        
        /* --- OUTPUTS --- */
        // Assign the final state of the qubit to the output variable
        let q_out = q_ptr[{0}];
        
        @leqo.output 0
        let q_out_alias = q_out;
        """
    source3="""
        OPENQASM 3.1;
        /* --- INPUTS --- */
        @leqo.input 0
        int[32] loop_counter;
        let loop_counter_alias = loop_counter;
        
        @leqo.input 1
        qubit[1] q_main;
        let q_main_alias = q_main;
        
        /* --- LOGIC --- */
        // Create a reference to the qubit for the loop block
        let loop_reg = q_main;
        
        // Check if the integer input is less than 5
        while (loop_counter < 5) {
          // Apply Pauli-X to the qubit inside the loop
          let q_inner = loop_reg[{0}];
          x q_inner;
          let q_inner_out = q_inner;
        }
        
        /* --- OUTPUTS --- */
        int[32] c_out;
        
        @leqo.output 0
        let c_out_alias = c_out;
        
        // Assign the final state of the qubit to the output variable
        let q_out = loop_reg[{0}];
        
        @leqo.output 1
        let q_out_alias = q_out;
        """
    source4="""
        OPENQASM 3.1;
        /* --- INPUTS --- */
        @leqo.input 0
        bit[1] c_in;
        let c_in_alias = c_in;
        
        @leqo.input 1
        qubit[1] q_main;
        let q_main_alias = q_main;
        
        /* --- LOGIC --- */
        // Create a reference to the qubit for the logic block
        let q_ptr = q_main;
        
        // Check if input bit equals 3 (Note: 1 bit can only be 0 or 1)
        if (c_in == 3) {
          // True Branch: Apply Hadamard
          let q_true = q_ptr[{0}];
          h q_true;
          let q_true_out = q_true;
        } else {
          // False Branch: Apply Pauli-X
          let q_false = q_ptr[{0}];
          x q_false;
          let q_false_out = q_false;
        }
        
        /* --- OUTPUTS --- */
        bit[1] c_out;
        
        @leqo.output 0
        let c_out_alias = c_out;
        
        // Assign the final state of the qubit to the output variable
        let q_out = q_ptr[{0}];
        
        @leqo.output 1
        let q_out_alias = q_out;
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

    source7="""
    OPENQASM 3.1;
    
    // Variational parameter (compile-time)
    input angle[32] theta;
    
    // Logic parameter (runtime)
    input int[32] n;
    
    // Result container
    output int[32] result;
    
    qubit[1] q;
    bit[1] c;
    
    // Use Parameter in gate
    rx(theta) q[0];
    
    c[0] = measure q[0];
    
    // Use Input Variable in logic
    if (n > 5) {
        x q[0];
    }
    
    // Write to Output (Mock assignment for demonstration)
    result = n;
    """

    ast_node = openqasm3.parse(source1)
    transpiler = QasmToQiskitTranspiler()
    python_script = transpiler.visit(ast_node)

    print("--- GENERATED PYTHON SCRIPT ---")
    print(python_script)