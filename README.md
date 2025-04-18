# LEQO Back-End

[![Docker image on ghcr.io](https://img.shields.io/badge/Docker-GitHub%20Container%20Registry-green?style=flat&logo=docker&logoColor=%23fff)](https://github.com/LEQO-Framework/leqo-backend/pkgs/container/leqo-backend)

The back-end for the QASM low-code platform LEQO.
It does:

- provide a REST-API for the LEQO front-end
- enrich QASM programs via ID-based imports
- merge multiple QASM programs into one

This project uses the [uv package manager](https://docs.astral.sh/uv/#getting-started).

## Deployment

Run the following command:

```bash
docker compose -f compose-dev.yaml up --build
```

Then you can access the back-end on:  
http://localhost:8000  
http://localhost:8000/docs

## Development

Run the following command:

```bash
docker compose up postgres
uv run fastapi dev
```

Now you have to change the host in your `.env` to the
IP address of the postgres database docker container. 
For docker you get the IP with:

Unix:
```bash
docker inspect <container id> | grep "IPAddress"
```
Windows:
```bash
docker inspect <container id> | findstr "IPAddress"
```

Then you can access the back-end on:  
http://localhost:8000  
http://localhost:8000/docs

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
