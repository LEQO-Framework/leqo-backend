Overview
========

Quick Start
-----------
#. Install `uv` – see `getting started with uv <https://docs.astral.sh/uv/#getting-started>`_

#. Run:

   .. code-block:: shell

      uv sync --all-groups --all-extras
      cp .env.template .env
      nano .env # update POSTGRES_HOST to your needs (try POSTGRES_HOST=localhost)
      docker compose up postgres
      uv run fastapi run app/main.py --port 8000

#. Open `localhost:8000 <http://localhost:8000/docs>`_ to verify the backend is running

Setup for Development
---------------------

The instructions below are a more detailed version of the Quick Start instructions.

1. Install Dependencies
~~~~~~~~~~~~~~~~~~~~~~~

This project uses the `uv <https://docs.astral.sh/uv/#getting-started>`_ package manager.

After installing uv, use the following command to install the dependencies:

.. code-block:: shell

    uv sync --all-groups --all-extras

2. Set up Environment
~~~~~~~~~~~~~~~~~~~~~

You will need a `.env` file.
Copy the `.env.template`:

.. code-block:: shell

   cp .env.template .env

Edit the file to set `POSTGRES_HOST` according to your environment. In most cases:


.. code-block:: ini

   POSTGRES_HOST=localhost

For more detailed options have a look at :doc:`Configuration <../usage/config>`

3. Start Postgres
~~~~~~~~~~~~~~~~~

Start the postgres database via docker:

.. code-block:: shell

  docker compose up postgres

4. Run the Backend
~~~~~~~~~~~~~~~~~~

Now you can start with backend with:

.. code-block:: shell

  uv run fastapi run app/main.py --port 8000

You can verify it working by opening the `fastapi docs <http://localhost:8000/docs>`_.

Dependencies
------------

The dependencies of this project are configured in `pyproject.toml` and locked via `uv.lock` by uv.

For a license summary have a look at :doc:`Dependencies <sbom>`.

Code Formatting
---------------

We use `ruff <https://docs.astral.sh/ruff/>`_ as our code formatter.

Format the code with:

.. code-block:: shell

  uv run ruff format .

Further Information
-------------------

- Architecture overview: :doc:`Architecture <architecture>`
- How to run the tests: :doc:`Testing <testing>`
- How to write docs: :doc:`Documentation <docs>`
- Some parts of the `openqasm3 python package <https://pypi.org/project/openqasm3/>`_ documentation important for us: :doc:`Openqasm3 <openqasm3>`
- Automated code documentation from embedded docs: :doc:`API Reference <../autoapi/index>`
