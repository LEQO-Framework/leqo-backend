# LEQO Back-End

[![Docker image on ghcr.io](https://img.shields.io/badge/Docker-GitHub%20Container%20Registry-green?style=flat&logo=docker&logoColor=%23fff)](https://github.com/LEQO-Framework/leqo-backend/pkgs/container/leqo-backend)
[![Documentation](https://img.shields.io/badge/docs-live-green?style=flat&logo=read-the-docs&logoColor=white)](https://leqo-framework.github.io/leqo-backend/)

The backend for the [LEQO-Framework](https://github.com/LEQO-Framework) - a low-code platform for developing quantum algorithms.

## 🔧 Features

- Provide a REST-API for the [LEQO frontend](https://github.com/LEQO-Framework/low-code-modeler)
- Retrieve [OpenQASM](https://openqasm.com/) implementations for low-code nodes
- Merge low-code models into a single [OpenQASM](https://openqasm.com/) program compatible with [Qiskit](https://github.com/Qiskit/qiskit)
- Support OpenQASM 2 input via an internal converter
- Optimize circuits by reusing ancilla qubits automatically
- Can handle nested low-code nodes: If-Then-Else and Repeat
- Build to be extensible

The project uses:

- [uv](https://docs.astral.sh/uv/#getting-started) as the Python package manager
- [mypy](https://mypy.readthedocs.io/en/stable/getting_started.html) for static type checking
- [ruff](https://docs.astral.sh/ruff/) for code formatting and linting

## 🚀 Quick Start

Make sure Docker and [Docker Compose](https://docs.docker.com/compose/install/) are installed.

Run the following commands:

```bash
cp .env.template .env
docker compose -f compose-dev.yaml up --build
```

Once started, access the backend at: 

- API: http://localhost:8000  
- Swagger UI: http://localhost:8000/redoc

## 📚 Documentation

Build the docs locally via:

    uv run --no-sync extract-openapi.py
    uv run cyclonedx-py venv -o docs/_static/sbom.json
    uv run sphinx-autobuild --port 8080 ./docs/ ./docs/_build

For architecture, API reference, and developer guides, see our [full documentation site](https://leqo-framework.github.io/leqo-backend/).

## 📑 License

The LEQO-backend is available under the [Apache 2.0 LICENSE](./LICENSE).

## ⚠️ Disclaimer of Warranty

Unless required by applicable law or agreed to in writing, Licensor provides the Work (and each Contributor provides its
Contributions) on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied, including,
without limitation, any warranties or conditions of TITLE, NON-INFRINGEMENT, MERCHANTABILITY, or FITNESS FOR A
PARTICULAR PURPOSE. You are solely responsible for determining the appropriateness of using or redistributing the Work
and assume any risks associated with Your exercise of permissions under this License.

## ⚠️ Haftungsausschluss

Dies ist ein Forschungsprototyp. Die Haftung für entgangenen Gewinn, Produktionsausfall, Betriebsunterbrechung,
entgangene Nutzungen, Verlust von Daten und Informationen, Finanzierungsaufwendungen sowie sonstige Vermögens- und
Folgeschäden ist, außer in Fällen von grober Fahrlässigkeit, Vorsatz und Personenschäden, ausgeschlossen.
