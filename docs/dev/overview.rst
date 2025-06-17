Overview
========

Setup for Development
---------------------

This project uses the `uv <https://docs.astral.sh/uv/#getting-started>`_ package manager).

After installing uv, use the following command to install the dependencies:

.. code-block:: shell

	uv sync

Start the postgres database via docker:

.. code-block:: shell

  docker compose up postgres

You will need a `.env` file.
Copy the `.env.template`:

.. code-block:: shell

   cp .env.template .env

And edit it with a text editor of your choice.
You have to ensure that the `POSTGRES_HOST` is set according to your environment (try `localhost`).

Now you can start with backend with:

.. code-block:: shell

  uv run fastapi run app/main.py --port 8000

You can verify it working by opening the `fastapi docs <http://localhost:8000/docs>`_.


Further Information
-------------------

- Architecture overview: :doc:`dev/architecture`
- How to write docs: :doc:`dev/docs`
- How to run the tests: :doc:`dev/testing`
