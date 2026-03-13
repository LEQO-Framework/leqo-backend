# LEQO Backend – Context Summary for AI Chat

> **Purpose of this document**: Provide a concise, self-contained overview of the LEQO Backend framework and the changes introduced on the `feature/qiskit-export` branch, so this summary can be pasted as context into another AI chat.

---

## 1. What is LEQO Backend?

LEQO Backend is a **REST API service** (Python / FastAPI) that powers the *LEQO low-code framework* for quantum algorithm development. It bridges a visual, drag-and-drop frontend (graph of nodes) with executable quantum circuit code.

**License**: Apache 2.0  
**Python version**: 3.13+  
**Package manager**: `uv`  
**Database**: PostgreSQL (async SQLAlchemy)

### Core workflow

```
Frontend sends CompileRequest (graph of nodes + edges)
        │
        ▼
[Enrichment] – attach OpenQASM 3 implementations to every node
        │         (from DB, Qiskit synthesis, literals, gates, …)
        ▼
[Preprocessing] – normalise each node's sub-program
        │
        ▼
[Merging] – stitch all nodes into one coherent OpenQASM 3 program
        │         (respects data-flow edges, handles ancilla qubits)
        ▼
[Optimisation] – ancilla-qubit reuse across nodes
        │
        ▼
[Postprocessing] – final clean-up
        │
        ▼
Output:  "qasm"    → raw OpenQASM 3 string
         "workflow" → BPMN XML workflow description
         "qiskit"   → executable Python / Qiskit script  ← NEW on qiskit-export
```

---

## 2. Repository layout

```
leqo-backend/
├── app/
│   ├── main.py                      # FastAPI app, REST endpoints (/compile, /enrich, /status, …)
│   ├── config.py                    # Settings (env vars, Qiskit compat mode)
│   ├── services.py                  # Dependency injection
│   ├── db_migrations.py             # DB initialisation
│   ├── utils.py
│   │
│   ├── model/
│   │   ├── CompileRequest.py        # ALL request/node DTOs (Pydantic)
│   │   ├── data_types.py            # LeqoSupportedType hierarchy
│   │   ├── database_model.py        # SQLAlchemy ORM models
│   │   └── exceptions.py
│   │
│   ├── enricher/                    # Strategy-pattern enrichers
│   │   ├── workflow.py              # Orchestrates enrichment per node
│   │   ├── db_enricher.py
│   │   ├── gates.py
│   │   ├── literals.py
│   │   ├── encode_value.py
│   │   ├── measure.py
│   │   ├── operator.py
│   │   ├── prepare_state.py
│   │   ├── qiskit_prepare.py
│   │   ├── merger.py / splitter.py
│   │   └── models.py
│   │
│   ├── openqasm3/                   # OpenQASM 3 utilities
│   │   ├── ast.py                   # AST extensions (e.g. CommentStatement)
│   │   ├── printer.py               # leqo_dumps() → OpenQASM 3 string
│   │   ├── visitor.py               # Visitor pattern for the AST
│   │   ├── stdgates.py              # Standard gate definitions
│   │   ├── rename.py                # Qubit / variable renaming helpers
│   │   ├── universal_transpiler.py  # NEW – provider-agnostic transpiler
│   │   ├── qiskit_provider.py       # NEW – Qiskit concrete provider
│   │   └── qiskit_generator.py      # NEW – string-based Qiskit code generator
│   │
│   └── transformation_manager/
│       ├── __init__.py              # CommonProcessor, MergingProcessor, EnrichingProcessor, WorkflowProcessor
│       ├── frontend_graph.py        # Parse/validate CompileRequest into a directed graph
│       ├── graph.py                 # ProgramGraph, ProgramNode, IOConnection, …
│       ├── bpmn_builder.py          # BPMN workflow generation
│       ├── merge/
│       │   └── __init__.py          # merge_nodes(), merge_for_nodes(), merge_while_nodes()  (UPDATED)
│       ├── pre/                     # Preprocessing passes
│       ├── post/                    # Postprocessing passes
│       ├── optimize/                # Ancilla qubit reuse
│       └── nested/
│           ├── if_then_else.py
│           ├── repeat.py
│           ├── for_loop.py          # NEW – for-loop enrichment
│           ├── while_loop.py        # NEW – while-loop enrichment
│           └── utils.py
│
├── tests/
│   ├── baselines/
│   │   ├── compile_qiskit/          # NEW – baseline YAML files for Qiskit output
│   │   └── test_main.py             # UPDATED – runs Qiskit baseline tests
│   └── processing/
│       └── nested/
│           ├── test_for_loop.py     # NEW
│           └── test_while_loop.py   # NEW
│
├── scripts/
│   └── generate_qiskit_baselines.py # NEW – helper to regenerate baseline files
│
├── pyproject.toml                   # Dependencies (adds qiskit-aer as optional dep)
└── compose-dev.yaml                 # Minor env var fix
```

---

## 3. Key classes / concepts

### CompileRequest (app/model/CompileRequest.py)

* **Node types** (discriminated union on `type` field):
  * `ImplementationNode` – user-provided or DB-stored OpenQASM 3 snippet
  * `GateNode`, `LiteralNode`, `EncodeValueNode`, `MeasureNode`, … – built-in operations
  * `IfThenElseNode` – classical if/else control flow
  * `RepeatNode` – loop that unrolls N times
  * `WhileNode` (**NEW**) – classical while loop
  * `ForNode` (**NEW**) – classical for loop with range and optional step
* **`compilation_target`** field: `"qasm"` (default) | `"workflow"` | `"qiskit"` (**NEW**)

### EnricherStrategy interface (app/enricher/)

Abstract pattern: each strategy receives a node + optional constraints and returns a `ParsedImplementationNode` containing an OpenQASM 3 AST.

### Transformation Manager (app/transformation_manager/)

* `CommonProcessor` – shared graph-traversal + enrichment logic; holds `target` field.
* `MergingProcessor` – extends `CommonProcessor`; calls `merge_nodes()` then runs postprocessing. If `target == "qiskit"`, runs the **Universal Transpiler** instead of `leqo_dumps()`.
* `EnrichingProcessor` – extends `CommonProcessor`; returns per-node enrichments.
* `WorkflowProcessor` – extends `CommonProcessor`; returns BPMN XML.

### Merge layer (app/transformation_manager/merge/)

Takes a `ProgramGraph` of enriched nodes and combines their OpenQASM 3 ASTs:
* Wire qubits/classical bits along data-flow edges.
* Insert `let` aliases for qubit sharing between nodes.
* Handle ancilla tracking.

Now also exports:
* `merge_for_nodes()` – wraps the body graph in `for int <it> in [start:end:step] { … }`.
* `merge_while_nodes()` – wraps the body graph in `while(<condition>) { … }`.

---

## 4. Changes on `feature/qiskit-export` branch

Four commits on top of `main` (commit `ecdab06`):

| Commit | Summary |
|--------|---------|
| `dc7cf53` | Prototype for Qiskit export – `QasmToQiskitTranspiler` string-based generator |
| `b2a8ec6` | Added I/O support, expression support, various fixes |
| `314169d` | Basic test suite for Qiskit export (baseline YAML files + tests) |
| `0e5a506` | Generic `UniversalTranspiler` with Qiskit SDK as example; updated test suite; added while/for loop support |

### 4.1 New compilation target: `"qiskit"`

`CompileRequest.compilation_target` now accepts `"qiskit"`.  
When selected, `MergingProcessor` passes the merged OpenQASM 3 AST through the **Universal Transpiler** (with `QiskitProvider`) instead of the text printer, producing a ready-to-run Python script.

```python
# Example: request
{
  "compilation_target": "qiskit",
  ...
}
# Result: Python string like:
# from qiskit import QuantumCircuit, ...
# qc = QuantumCircuit()
# q = QuantumRegister(2, 'q')
# qc.add_register(q)
# qc.h(q[0])
# qc.cx(q[0], q[1])
# ...
```

### 4.2 `QasmToQiskitTranspiler` (app/openqasm3/qiskit_generator.py) – String-based approach

* Visitor over the OpenQASM 3 AST; emits indented Python/Qiskit code as strings.
* Pre-scans the AST to determine required imports (Parameters, classical types, Aer simulator).
* Handles: qubit/bit declarations, gate applications, measurements, if/else (via `qc.if_test()`), while loops (via `qc.while_loop()`), for loops (via `qc.for_loop()`), I/O declarations (`input angle` → `Parameter`, `input int` → `qc.add_input()`, `output` → `expr.Var.new()`), classical assignments, binary/unary expressions, aliases (`let`).
* Emits execution boilerplate (AerSimulator, transpile, run) only when measurements are present.

### 4.3 `UniversalTranspiler` + `BaseSDKProvider` (app/openqasm3/universal_transpiler.py) – AST-based approach

Refactored, provider-agnostic design:

* `BaseSDKProvider` (ABC) defines the contract:
  `start_program`, `declare_qubit`, `declare_bit`, `gate`, `measure`, `if_block`, `while_loop`, `for_loop`, `alias`, `classical_assignment`, `io_declaration`, `end_program`, `binary_expression`, `unary_expression`.
* `UniversalTranspiler` walks the OpenQASM 3 AST and calls the provider's methods, collecting Python `ast` nodes.
* Providers return proper Python `ast.stmt` / `ast.expr` objects (not strings), then `ast.unparse()` / `ast.fix_missing_locations` produces the final script.
* New SDKs (e.g., Cirq, PennyLane) can be added by implementing `BaseSDKProvider`.

### 4.4 `QiskitProvider` (app/openqasm3/qiskit_provider.py)

Concrete `BaseSDKProvider` for Qiskit 2.x:

| OpenQASM 3 concept | Qiskit equivalent |
|--------------------|------------------|
| `qubit[n] q` | `QuantumRegister(n, 'q')` + `qc.add_register(q)` |
| `bit[n] c` | `ClassicalRegister(n, 'c')` + `qc.add_register(c)` |
| `h q[0]` | `qc.h(q[0])` |
| `measure q[0] -> c[0]` | `qc.measure(q[0], c[0])` |
| `if (cond) { … } else { … }` | `with qc.if_test(cond) as _else:` / `with _else:` |
| `while (cond) { … }` | `with qc.while_loop(cond):` |
| `for int i in [0:10] { … }` | `with qc.for_loop(range(0, 11)):` |
| `input angle theta` | `theta = Parameter('theta')` |
| `input int[32] x` | `x = qc.add_input('x', types.Uint(32))` |
| `output int[32] y` | `y = expr.Var.new('y', types.Uint(32)); qc.add_uninitialized_var(y)` |
| Classical assignment `c = n` | `qc.store(c, n)` |
| Binary expr `a == b` | `expr.equal(a, b)` |

### 4.5 New `WhileNode` and `ForNode` models

```python
class WhileNode(BaseNode):
    type: Literal["while"] = "while"
    condition: str          # e.g. "loop_counter < 5"
    block: NestedBlock      # sub-graph of nodes + edges

class ForNode(BaseNode):
    type: Literal["for"] = "for"
    iterator: str           # e.g. "i"
    range_start: int
    range_end: int
    step: int = 1
    block: NestedBlock
```

Both are added to `ControlFlowNode = IfThenElseNode | RepeatNode | WhileNode | ForNode`.

### 4.6 Nested enrichment: `enrich_while_loop` / `enrich_for_loop`

Follow the same pattern as the existing `enrich_if_then_else`:
1. Create synthetic `while`/`endwhile` (or `for`/`endfor`) pass-nodes.
2. Re-wire block edges to use those pass-nodes as boundary.
3. Build the inner graph recursively.
4. Call `merge_while_nodes()` / `merge_for_nodes()` to wrap the merged body in the correct OpenQASM 3 loop statement.
5. Return a `ParsedImplementationNode` for the parent node.

### 4.7 Tests

* **`tests/processing/nested/test_while_loop.py`** – unit tests covering: basic while loop, while loop with integer classical input, while loop with qubit input, integration with compile endpoint.
* **`tests/processing/nested/test_for_loop.py`** – unit tests covering: basic for loop, for loop with step, nested for loops, integration with compile endpoint.
* **`tests/baselines/compile_qiskit/`** – YAML baseline files (`basic_gates.yml`, `for_loop.yml`, `if_else.yml`, `parameterized_gates.yml`, `qaoa_2qubit.yml`, `while_loop.yml`) for snapshot-testing Qiskit output.
* **`scripts/generate_qiskit_baselines.py`** – script to regenerate baseline files when expected output changes.

### 4.8 Minor changes

* `compose-dev.yaml`: fixed an environment variable for the dev setup.
* `tests/baselines/test_main.py`: added test runner for the new `compile_qiskit` baselines.

---

## 5. Technology stack summary

| Category | Technology |
|----------|-----------|
| Language | Python 3.13+ |
| Web framework | FastAPI 0.115+ |
| Validation | Pydantic v2 |
| ORM | SQLAlchemy 2 (async) |
| Database | PostgreSQL (psycopg3) |
| Quantum IR | OpenQASM 3 (openqasm3 library) |
| Quantum SDK | Qiskit 2.x (+ qiskit-aer for simulation) |
| Graph algorithms | NetworkX |
| Type checking | mypy |
| Linting/formatting | ruff |
| Testing | pytest + pytest-asyncio + testcontainers |
| Docs | Sphinx + ReadTheDocs theme |
| Container | Docker + Docker Compose |

---

## 6. How to run locally

```bash
# Install dependencies
uv sync --all-extras

# Start DB
docker compose -f compose-dev.yaml up -d db

# Run the API
uv run uvicorn app.main:app --reload

# Run tests
uv run pytest

# Lint / type-check
uv run ruff check .
uv run mypy .
```

---

*Generated from repository `LEQO-Framework/leqo-backend`, branch `feature/qiskit-export` (commit `0e5a506`), base `main` (commit `ecdab06`).*
