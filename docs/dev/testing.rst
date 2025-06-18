Testing
=======

This project uses `pytest <https://docs.pytest.org/en/stable/>`_ for testing, complemented by static analysis tools for type and style checking.

Run Tests
---------

To execute the full test suite, run:

.. code-block:: shell

	uv run pytest tests

.. warning::
   The baseline test use docker and requires sudo privileges on unix.

Code Coverage
-------------

To measure and visualize test coverage, use the following command:

.. code-block:: shell

  uv run --no-sync pytest --cov=app --cov-report=html:.coverage-report tests
  cd .coverage-report
  python3 -m http.server 8000

Then open `localhost:8000 <http://localhost:8000>`_ in your browser to inspect the interactive HTML coverage report.

Static Analysis
---------------

The project enforces code quality and type safety through:

- `ruff <https://docs.astral.sh/ruff/>`_ for linting and formatting
- `mypy <https://mypy.readthedocs.io/en/stable/getting_started.html>`_ for static type checking

Run both tools with:

.. code-block:: shell

  uv run ruff check .
  uv run mypy --strict .
