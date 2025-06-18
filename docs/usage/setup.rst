Setup
=====

The LEQO-Backend is provided as a docker-image and can be run:

- **Standalone**: for backend-only use
- **In combination with frontend**: for full-stack development

You’ll need:

- Docker + Docker Compose installed
- Basic terminal access

To get started install `Docker Compose <https://docs.docker.com/compose/install/>`_ and follow the instructions below.

Standalone
----------

Use this for just hosting the backend without frontend (or separate from it).
Run the following commands:

.. code-block:: shell

    cp .env.template .env
    docker compose -f compose-dev.yaml up --build

With Frontend
-------------

You can host both the frontend and backend together with docker compose.

**Step 1:** Create a project directory
    .. code-block:: shell

        mkdir leqo
        cd leqo

**Step 2:** Create a `compose.yml` file with the following contents:
    .. code-block:: yaml

        name: LEQO
        services:
            backend-db:
                image: postgres:latest
                environment:
                    POSTGRES_USER: leqo
                    POSTGRES_PASSWORD: secure_password
                    POSTGRES_DB: qasm
            backend:
                image: ghcr.io/leqo-framework/leqo-backend:main
                environment:
                    POSTGRES_USER: leqo
                    POSTGRES_PASSWORD: secure_password
                    POSTGRES_DB: qasm
                    POSTGRES_PORT: 5432
                    POSTGRES_HOST: backend-db
                    SQLALCHEMY_DRIVER: postgresql+psycopg
                ports:
                    - 127.0.0.1:8000:80
            frontend:
                image: ghcr.io/leqo-framework/low-code-modeler:main
                ports:
                    - 127.0.0.1:80:4242

**Step 3:** Pull container images
    .. code-block:: shell

        docker compose pull

**Step 4:** Start the application
    .. code-block:: shell

        docker compose up -d

**Step 5:** Open the frontend
    Navigate to: `localhost:80 <http://localhost:80>`_

**Step 6:** Configure the backend port in the frontend

    - Go to **Configuration**
    - Set the **Low-Code Backend Endpoint** to: `http://localhost:8000`

