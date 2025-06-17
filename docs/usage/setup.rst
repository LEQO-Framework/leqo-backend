Setup
=====

The LEQO-Backend is provided as a docker-image to allow for a simple setup.

To get started install `Docker Compose <https://docs.docker.com/compose/install/>`_ and follow the instructions below.

Standalone
----------

Use this for just hosting the backend without frontend (or separate from it).
Run the following commands:

.. code-block:: shell

    cp .env.template .env
    docker compose -f compose-dev.yaml up --build

In Combination
--------------

You can host both the frontend and the backend with docker compose.

#. Create a directory for your project
    .. code-block:: shell

        mkdir leqo
        cd leqo

#. Create a `compose.yml` file
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

#. Pull project
    .. code-block:: shell

        docker compose pull

#. Start project
    .. code-block:: shell

        docker compose up -d

#. Open frontend in the browser
    `localhost:80 <http://localhost:80>`_

#. Configure the backend port in the frontend
    - open **Configuration**
    - write in **Low-Code Backend Endpoint**: `http://localhost:8000`

