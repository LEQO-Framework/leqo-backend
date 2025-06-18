Configuration
=============

Overview
--------

The backend is configured via an `.env` file, which should be placed in the same directory as your `compose.yaml`.
This file defines all environment-specific variables required for the backend to function correctly.

To get started, examine the default values provided in `.env.template`:

.. literalinclude:: ../../.env.template
   :language: sh
   :linenos:

Download this template: :download:`.env.template <../../.env.template>`

Options
-------

The following environment variables are available for configuring the backend:

.. list-table:: Backend Configuration Parameters
   :widths: 25 45 30
   :header-rows: 1

   * - Variable
     - Description
     - Default

   * - ``POSTGRES_USER``
     - The username used to connect to the PostgreSQL database.
     - ``dev``

   * - ``POSTGRES_PASSWORD``
     - Password for the PostgreSQL user.
     - ``dev``

   * - ``POSTGRES_DB``
     - Name of the PostgreSQL database to connect to.
     - ``qasm``

   * - ``POSTGRES_PORT``
     - Port on which the PostgreSQL server is accessible.
     - ``5432``

   * - ``POSTGRES_HOST``
     - Hostname or IP address of the PostgreSQL server. Use ``postgres`` when accessed via docker compose and ``localhost`` for local development.
     - ``postgres``

   * - ``SQLALCHEMY_DRIVER``
     - SQLAlchemy driver string used to construct the database URL.
     - ``postgresql+psycopg``

   * - ``API_BASE_URL``
     - Base URL of the backend API, used to construct absolute URLs internally.
     - ``http://localhost:8000/``

   * - ``CORS_ALLOW_ORIGINS``
     - JSON-formatted list of allowed origins for Cross-Origin Resource Sharing (CORS).
     - ``["*"]`` (allow all origins)

   * - ``CORS_ALLOW_CREDENTIALS``
     - Whether to allow credentials (cookies, authorization headers) in CORS requests.
     - ``TRUE``

   * - ``CORS_ALLOW_METHODS``
     - List of HTTP methods permitted in CORS requests.
     - ``["*"]`` (allow all methods)

   * - ``CORS_ALLOW_HEADERS``
     - list of HTTP headers allowed in CORS requests.
     - ``["*"]`` (allow all headers)