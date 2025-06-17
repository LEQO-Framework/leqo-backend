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
