# Scripts README

This directory contains helper scripts for interacting with the LEQO backend.

## `request_helper.py`

A lightweight CLI utility that lets you quickly exercise the API without having to write curl commands.

### Installation

The script uses only the Python standard library. Run it via the interpreter of your virtual environment:

```bash
python scripts/request_helper.py --help
```

### Commands

#### `send`

Send a JSON payload to one of the supported endpoints:

```bash
python scripts/request_helper.py send payload.json /compile
```

Options:

- `--host http://localhost:8000` (default) - base URL for the API.
- `--flag FLAG` - optional diagnostic flag forwarded as a repeated `flags` query parameter (repeatable, e.g. `--flag is_debug --flag include_traceback`).
- `--show-stacktrace` - when the request fails, pretty-print the error payload and any embedded stack trace.

For long-running endpoints (`/compile`, `/enrich`) the script polls `/status`, prints the result, and follows the `Link` header to show the stored request payload.

Example payloads:

- `compile_request.json` - small sanity check with a custom implementation.
- `encode_value_basis_request.json` - uses the basis encoder with a 3-bit integer input and measures the resulting register.
- `encode_value_basis_parameter_request.json` - parameterized basis-encoding request (bit size, value, bounds, and measurement indices).
- `encode_value_basis_negative_request.json` - drives the basis encoder with a negative integer to inspect the two's-complement bit pattern.
- `encode_value_basis_array_request.json` - feeds the basis encoder with an array literal and reads every qubit.
- `encode_value_basis_list_request.json` - illustrates encoding multiple integers in the basis, concatenating the registers, and reading all outputs at once.
- `encode_value_basis_request_bitsize.json` - demonstrates overriding the `elementBitSize` for basis encoding.
- `encode_value_basis_request_measure_indices.json` - measures only a subset of the encoded basis register.
- `encode_value_bool_request.json` - runs the basis encoder with a boolean literal to toggle a single qubit.
- `basis_addition_request.json` - encodes two integers in the basis, sums them via an `operator` node, and measures the summed register.
- `basis_signed_addition_request.json` - encodes a negative and positive integer, exercises the signed-aware addition, and measures the two's-complement sum.
- `encode_value_angle_request.json` - uses the angle encoder with a floating-point literal and measures the encoded qubit.
- `encode_value_angle_array_request.json` - processes an array literal (with integers) with the angle encoder.
- `enrich_operator_plus_request.json` - targets a `+` operator where the lhs register is wider to showcase the flexible fallback.
- `enrich_operator_plus_valid_request.json` - hits the `+` operator with inputs that match the seeded database entry and returns the stored implementation.
- `uncompute_ancilla_request.json` - demonstrates ancilla qubit reuse via `@leqo.uncompute` and width optimization.
- `uncompute_ancilla_no_opt_request.json` - same model as above but without width optimization, for side-by-side comparison.
- `addition_insert.json` - ready-made payload for inserting the fallback addition circuit into the database.

To inspect the enrichment result directly without polling, run:

```bash
python scripts/request_helper.py send scripts/enrich_operator_plus_request.json /debug/enrich
```

#### `result`

Fetch result information:

- Overview of all requests:

  ```bash
  python scripts/request_helper.py result
  ```

- Specific result by UUID:

  ```bash
  python scripts/request_helper.py result --uuid 123e4567-e89b-12d3-a456-426614174000
  ```

Options:

- `--host` - base URL for the API (default: `http://localhost:8000`).

When a result is returned, the script also prints any `Link` header pointing to the stored request payload.

#### `request`

Retrieve the original compile request payload:

```bash
python scripts/request_helper.py request 123e4567-e89b-12d3-a456-426614174000
```

Options:

- `--host` - base URL for the API (default: `http://localhost:8000`).

The response is printed as pretty JSON for inspection.

## Qiskit Enrichment Scenarios

The `scripts/qiskit-enrichment` folder contains ready-made payloads for exercising the Qiskit-backed state preparation strategy (`QiskitPrepareStateEnricherStrategy`) along with a requirements file for setting up the simulator stack locally.

### Install Qiskit prerequisites

When running locally, install the required Qiskit packages into the active virtual environment:

```bash
pip install -r scripts/qiskit-enrichment/qiskit_requirements.txt
```

This pulls in the main `qiskit` bundle and the Aer simulator backend, which the enricher relies on when synthesizing circuits.

Check qiskit installation. Qiskit is now installed via uv.
Check the versioning with the command:

```bash
uv pip list
```

### Sample payloads

- `prepare_bell_state_request.json` – prepares a ϕ⁺ Bell state and measures both qubits.
- `prepare_ghz_state_request.json` – synthesizes a three-qubit GHZ state with measurements on every output.
- `prepare_uniform_state_request.json` – builds a four-qubit uniform superposition and reads out all qubits.
- `prepare_w_state_request.json` – generates a three-qubit W state and measures each qubit. IMPORTANT NOTE: The resulting circuit need to be transpiled even when using the Aer-Simlator, as QASM 3 custom gates are not directly compatible. 

### Running the scenarios

Use the `request_helper.py` CLI to submit a payload to the `/debug/enrich` endpoint (or `/compile` if you want the full pipeline):

```bash
python scripts/request_helper.py send scripts/qiskit-enrichment/prepare_bell_state_request.json /debug/enrich
```

If Qiskit is installed, the backend will generate an implementation via the Qiskit enricher. When Qiskit is absent, the enrichment falls back to database-only strategies and these payloads will return an empty result, so verifying the enriched response confirms the Qiskit integration is active.

## Ancillae And Uncompute

This section documents how ancilla handling works in the backend pipeline.

### Where ancillae live in the model

Ancillae are interpreted at multiple layers:

- **Node-local qubits in OpenQASM snippets**: plain `qubit` declarations that are not `@leqo.input`.
- **Ports**: only `@leqo.input <i>` and `@leqo.output <i>` define model ports.
- **Edges**: user-provided edges connect output port indices to input port indices; during optimization, the backend may add internal ancilla-reuse edges (`AncillaConnection`) between nodes.

So for practical compilation flow, ancillae are primarily a **node-implementation concern**, and ancilla reuse is represented as **graph edges generated by the optimizer**.

### How uncompute is parsed and applied

For each snippet, annotation parsing classifies qubits into buckets:

- `clean_ids`: regular declared qubits (clean workspace requirement).
- `dirty_ids`: qubits declared with `@leqo.dirty`.
- `reusable_ids`: qubits marked with `@leqo.reusable` outside uncompute.
- `uncomputable_ids`: qubits marked `@leqo.reusable` inside `@leqo.uncompute if (false) { ... }`.
- `entangled_ids`: remaining qubits not declared as output/reusable.

Uncompute block constraints:

- Must be `@leqo.uncompute` directly over `if (false) { ... }`.
- No `else`, no nesting, and no `@leqo.output` declarations inside.

During width optimization, the optimizer decides per node whether uncompute should run:

- `False`: uncompute block is removed.
- `True`: the `if (false)` wrapper is removed and only the block body is inlined into the final snippet.

Uncomputable qubits are promoted to reusable only when this is needed to satisfy clean-qubit demand in downstream nodes.

### Important note on `type: "ancilla"` nodes

The request schema includes an `ancilla` node type, but current runtime behavior is driven by snippet annotations plus optimizer-added ancilla edges. The optimizer's `is_ancilla_node` flag exists internally and in tests, while normal compile processing currently constructs internal nodes without setting that flag.

### Example request using ancillae + uncompute

Use `scripts/uncompute_ancilla_request.json`:

```bash
python scripts/request_helper.py send scripts/uncompute_ancilla_request.json /compile
```

What this model demonstrates:

- `producer` allocates ancilla qubits and declares an explicit uncompute block.
- `consumer` needs clean workspace qubits.
- With `metadata.optimizeWidth` enabled, the optimizer can enable `producer` uncompute and connect those qubits into `consumer` via internal ancilla edges.

### A/B comparison: with and without width optimization

Run both requests:

```bash
python scripts/request_helper.py send scripts/uncompute_ancilla_request.json /compile
python scripts/request_helper.py send scripts/uncompute_ancilla_no_opt_request.json /compile
```

Expected high-level differences in the generated QASM:

- `uncompute_ancilla_request.json` (`optimizeWidth: 1`)
  - global register shrinks to `qubit[3] leqo_reg;`
  - uncompute wrapper is not present (`if (false)` removed and block body applied)
- `uncompute_ancilla_no_opt_request.json` (no `optimizeWidth`)
  - global register remains `qubit[5] leqo_reg;`
  - uncompute block remains disabled as `if (false) { ... }`
