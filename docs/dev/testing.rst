Testing
=======

This project uses `pytest <https://docs.pytest.org/en/stable/>`_ for testing.

Run Tests
---------

Run all tests using the following command:

.. code-block:: shell

	uv run pytest tests

.. warning::
   The baseline test use docker and requires sudo privileges on unix.

Code Coverage
-------------

To see how much code is covered by test, run the following:

.. code-block:: shell

  uv run --no-sync pytest --cov=app --cov-report=html:.coverage-report tests
  cd .coverage-report
  python3 -m http.server 8000

Static Analysis
---------------

This project uses `ruff <https://docs.astral.sh/ruff/>`_ and `mypy <https://mypy.readthedocs.io/en/stable/getting_started.html>`_ for linting.

Run them via:

.. code-block:: shell

  uv run ruff check .
  uv run mypy --strict .
