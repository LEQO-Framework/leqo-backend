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

- `--host http://localhost:8000` (default) – base URL for the API.

For long-running endpoints (`/compile`, `/enrich`) the script polls `/status`, prints the result, and follows the `Link` header to show the stored request payload.

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

- `--host` – base URL for the API (default: `http://localhost:8000`).

When a result is returned, the script also prints any `Link` header pointing to the stored request payload.

#### `request`

Retrieve the original compile request payload:

```bash
python scripts/request_helper.py request 123e4567-e89b-12d3-a456-426614174000
```

Options:

- `--host` – base URL for the API (default: `http://localhost:8000`).

The response is printed as pretty JSON for inspection.
