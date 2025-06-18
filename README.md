# LEQO Back-End

[![Docker image on ghcr.io](https://img.shields.io/badge/Docker-GitHub%20Container%20Registry-green?style=flat&logo=docker&logoColor=%23fff)](https://github.com/LEQO-Framework/leqo-backend/pkgs/container/leqo-backend)
[![Documentation](https://img.shields.io/badge/docs-live-green?style=flat&logo=read-the-docs&logoColor=white)](https://leqo-framework.github.io/leqo-backend/)

The backend for low-code, quantum [LEQO-Framework](https://github.com/LEQO-Framework).

## Features

- provide a REST-API for the [LEQO front-end](https://github.com/LEQO-Framework/low-code-modeler)
- retrieve [OpenQASM](https://openqasm.com/) implementations for low-code nodes
- merge low-code model into one [OpenQASM](https://openqasm.com/) program that is compatible with [Qiskit](https://github.com/Qiskit/qiskit)
- handle OpenQASM 2 input via own converter
- optimize the result by automated reusage of ancilla qubits

This project uses the [uv package manager](https://docs.astral.sh/uv/#getting-started), [mypy](https://mypy.readthedocs.io/en/stable/getting_started.html) and [ruff](https://docs.astral.sh/ruff/).

## Deployment

Run the following commands:

```bash
cp .env.template .env
docker compose -f compose-dev.yaml up --build
```

Then you can access the back-end on:  
http://localhost:8000  
http://localhost:8000/docs

## Documentation and Development

Please visit our [Documentation](https://leqo-framework.github.io/leqo-backend/)

## Disclaimer of Warranty

Unless required by applicable law or agreed to in writing, Licensor provides the Work (and each Contributor provides its
Contributions) on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied, including,
without limitation, any warranties or conditions of TITLE, NON-INFRINGEMENT, MERCHANTABILITY, or FITNESS FOR A
PARTICULAR PURPOSE. You are solely responsible for determining the appropriateness of using or redistributing the Work
and assume any risks associated with Your exercise of permissions under this License.

## Haftungsausschluss

Dies ist ein Forschungsprototyp. Die Haftung für entgangenen Gewinn, Produktionsausfall, Betriebsunterbrechung,
entgangene Nutzungen, Verlust von Daten und Informationen, Finanzierungsaufwendungen sowie sonstige Vermögens- und
Folgeschäden ist, außer in Fällen von grober Fahrlässigkeit, Vorsatz und Personenschäden, ausgeschlossen.
