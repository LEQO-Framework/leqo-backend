Configuration
=============

Overview
--------

The backend is configured via an `.env` file that needs to be places next to your `compose.yaml`.
Have a look at the default values in `.env.template`:

.. literalinclude:: ../../.env.template
   :language: sh
   :linenos:

Download this file: :download:`.env.template <../../.env.template>`

Options
-------

The following environment variables are used to configure the backend:

- **POSTGRES_USER**  
  The username used to connect to the PostgreSQL database.  
  *Default: `dev`*

- **POSTGRES_PASSWORD**  
  The password for the PostgreSQL user.  
  *Default: `dev`*

- **POSTGRES_DB**  
  The name of the PostgreSQL database to connect to.  
  *Default: `qasm`*

- **POSTGRES_PORT**  
  The port on which the PostgreSQL server is running.  
  *Default: `5432`*

- **POSTGRES_HOST**  
  The hostname or IP address of the PostgreSQL server.  
  Use `postgres` when accessed via docker compose and `localhost` for local development.
  *Default: `postgres`*

- **SQLALCHEMY_DRIVER**  
  The SQLAlchemy driver string used to construct the database URL.  
  *Default: `postgresql+psycopg`*

- **API_BASE_URL**  
  The base URL of this API, used internally for building absolute URLs.  
  *Default: `http://localhost:8000/`*

- **CORS_ALLOW_ORIGINS**  
  A list of origins allowed for Cross-Origin Resource Sharing (CORS).  
  Should be a JSON-formatted list of strings.  
  *Default: `["*"]` (allow all origins)*

- **CORS_ALLOW_CREDENTIALS**  
  Whether to allow credentials (cookies, authorization headers) in CORS requests.  
  *Default: `TRUE`*

- **CORS_ALLOW_METHODS**  
  A list of HTTP methods allowed for CORS.  
  *Default: `["*"]` (allow all methods)*

- **CORS_ALLOW_HEADERS**  
  A list of HTTP headers allowed in CORS requests.  
  *Default: `["*"]` (allow all headers)*
