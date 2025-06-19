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

.. tip::
   The commands above use the default configuration that can be changed as described in :doc:`Configuration <config>`

With Frontend
-------------

You can host both the frontend and backend together with docker compose.

**Step 1:** Create a project directory
    .. code-block:: shell

        mkdir leqo
        cd leqo

**Step 2:** Create a `compose.yml` file with the following contents:
  .. literalinclude:: downloads/compose.yaml
     :language: yaml
     :linenos:

  Download this file: :download:`compose.yml <downloads/compose.yaml>`

  If you don't need configuration, you can use this file: :download:`compose.simple.yml <downloads/compose.simple.yaml>` and skip Step 3.

**Step 3:** Create the `.env` file according to the instructions in :doc:`Configuration <config>`.

**Step 4:** Start the application
    .. code-block:: shell

        docker compose up -d

**Step 5:** Open the frontend
    Navigate to: `localhost:80 <http://localhost:80>`_

**Step 6:** Configure the backend port in the frontend

    - Go to **Configuration**
    - Set the **Low-Code Backend Endpoint** to: `http://localhost:8000`

Insert Implementations into the Database
----------------------------------------

The backend provides the `/insert` endpoint for inserting Implementations into the database.
An simple example of an insert request can be seen here:

.. literalinclude:: ../../scripts/addition_insert.json
   :language: json
   :linenos:

Download this file: :download:`addition_insert.yml <../../scripts/addition_insert.json>`

For sending this request, you have two options:

**Use Python:** Run the following command in the project directory:
    .. code-block:: shell

        ./scripts/insert_helper.py ./scripts/addition_insert.json

**Use curl:** Run the following command next to the json file:
    .. code-block:: shell

        curl -X POST -H "Content-Type: application/json" --data @./addition_insert.json http://localhost:8000/insert
