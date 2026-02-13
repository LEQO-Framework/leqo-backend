# Scripts README

This directory contains helper scripts for interacting with the LEQO backend.

## Music Feature Extractor

The `extract_music_features.py` script runs the backend feature extractor locally without
calling the API. It reads MusicXML (or base64-encoded binary formats like MXL/MIDI), parses
score metadata, and outputs a JSON payload that matches the `music_features` schema stored
by the backend.

### Usage

```bash
python scripts/extract_music_features.py tests/music/simple.musicxml --format musicxml
```

Optional output file:

```bash
python scripts/extract_music_features.py path/to/score.mxl --format mxl --output features.json
```

### API Mode (Batch)

You can also call the running backend API to extract features in bulk:

```bash
python scripts/extract_music_features.py music-files/mxl-files \
  --format mxl \
  --api \
  --output-dir music-files/mxl-features \
  --batch-size 10 \
  --overwrite
```

Notes:
- `--output-dir` is required for directory inputs in API mode.
- The default endpoint is `/debug/enrich`; override with `--endpoint` if needed.

### Behavior

- The script expects UTF-8 MusicXML for `musicxml`/`xml` formats.
- For `mxl` or `midi`, it base64-encodes the file and passes it to the extractor.
- The extractor reads per-part metadata (key/time/clef/tempo/dynamics/directions),
  computes ambitus and pitch-class distribution, and returns a stable JSON schema.
- If `music21` is installed, it is used as a fallback to compute ambitus when XML
  pitch data is missing, and to derive pitch-class distributions from MIDI files.
- The output includes a feature vector (`feature_vector`) and its schema
  (`feature_vector_schema`) for downstream clustering.

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

For long-running endpoints (`/compile`, `/enrich`) the script polls `/status`, prints the result, and follows the `Link` header to show the stored request payload.

Example payloads:

- `compile_request.json` - small sanity check with a custom implementation.
- `encode_value_basis_request.json` - uses the basis encoder with a 3-bit integer input and measures the resulting register.
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
