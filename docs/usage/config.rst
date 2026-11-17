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

   * - ``QISKIT_COMPAT_MODE``
     - Enables Qiskit compatibility tweaks (e.g. removing literal nodes from the emitted QASM).
     - ``FALSE``

   * - ``NISQ_ANALYZER_URL``
     - Base URL of the NISQ Analyzer used by the QUBO algorithm selection (``/qubo/algorithm-selection``).
       Use ``http://host.docker.internal:5010/nisq-analyzer/`` when the backend runs in docker.
     - ``http://localhost:5010/nisq-analyzer/``

   * - ``NISQ_ANALYZER_MCDA_METHOD``
     - MCDA method that ranks the compiled circuits: ``topsis``, ``promethee-II`` or ``electre-III``.
     - ``topsis``

   * - ``NISQ_ANALYZER_ALLOWED_PROVIDERS`` / ``NISQ_ANALYZER_COMPILERS``
     - JSON lists of the providers and compilers the NISQ Analyzer considers.
     - ``["ibmq"]`` / ``["qiskit"]``

   * - ``NISQ_ANALYZER_TOKENS``
     - JSON map of provider tokens forwarded to the compiler services, e.g. ``{"ibmq": {"ibmq": "<token>"}}``.
     - ``{"ibmq": {"ibmq": ""}}``

   * - ``NISQ_ANALYZER_POLL_INTERVAL_SECONDS`` / ``NISQ_ANALYZER_TIMEOUT_SECONDS``
     - Polling interval and maximum waiting time per NISQ Analyzer job.
     - ``3`` / ``600``

   * - ``ALGORITHM_SELECTION_QAOA_LAYERS`` / ``ALGORITHM_SELECTION_VQE_LAYERS``
     - JSON lists of QAOA depths (p) and hardware-efficient VQE depths (L); each depth is a candidate of the selection.
     - ``[1, 2]`` / ``[1, 2]``

   * - ``ALGORITHM_SELECTION_MAX_ERROR_CHANCE``
     - A candidate whose top-ranked QPU has a higher error chance is not feasible and removed.
     - ``0.5``

   * - ``ALGORITHM_SELECTION_HISTORY_VARIABLE_TOLERANCE`` / ``ALGORITHM_SELECTION_HISTORY_DENSITY_TOLERANCE``
     - Relative difference in variable count and absolute difference in coupling density of records the history considers.
     - ``0.2`` / ``1.0``

   * - ``ALGORITHM_SELECTION_HISTORY_SIZE_SCALE`` / ``ALGORITHM_SELECTION_HISTORY_DENSITY_SCALE`` / ``ALGORITHM_SELECTION_HISTORY_FIELD_SCALE``
     - Scales of the relative size difference, the density difference and the difference of
       ``log(1 + field/coupling ratio)`` in the distance of two QUBOs (similarity ``exp(-distance²)``); 0 ignores a feature.
     - ``0.2`` / ``0.1`` / ``0.5``

   * - ``ALGORITHM_SELECTION_HISTORY_LIMIT``
     - Number of nearest records the history uses.
     - ``50``

   * - ``ALGORITHM_SELECTION_HISTORY_MARGIN``
     - The history only votes if its best candidate leads the second best by at least this mean solution quality.
     - ``0.005``

   * - ``ALGORITHM_SELECTION_VQE_MAX_VARIABLES`` / ``ALGORITHM_SELECTION_QAOA_MIN_VARIABLES`` / ``ALGORITHM_SELECTION_QAOA_ALWAYS_VARIABLES``
     - The problem structure rule prefers VQE up to the first number of variables, does not vote below the second,
       prefers QAOA from the second on for weak-field, not dense QUBOs and from the third on for every QUBO.
     - ``14`` / ``16`` / ``18``

   * - ``ALGORITHM_SELECTION_MAX_FIELD_COUPLING_RATIO`` / ``ALGORITHM_SELECTION_MAX_DENSITY``
     - Limits of a weak-field, not dense QUBO: mean |local field| / mean |coupling| of the Ising form and coupling density.
     - ``0.78`` / ``0.625``

   * - ``ALGORITHM_SELECTION_QAOA_MAX_ERROR_CHANCE``
     - The structure rule only votes for QAOA if a feasible QAOA candidate has at most this error chance.
     - ``0.4``

   * - ``ALGORITHM_SELECTION_WEIGHT_HISTORY`` / ``ALGORITHM_SELECTION_WEIGHT_PROBLEM_STRUCTURE``
     - Weights of the history and problem structure rule votes.
     - ``0.6`` / ``0.4``
