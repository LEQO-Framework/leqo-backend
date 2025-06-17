Documentation
=============

Syntax
------

This documentation is build with `Sphinx <https://www.sphinx-doc.org/en/master/index.html>`_.
Content has to be in the ``reStructuredText`` syntax.
See the
`reStructuredText <https://www.sphinx-doc.org/en/master/usage/restructuredtext/index.html>`_
documentation for details.

Local Build
-----------

Build the docs locally via:

.. code-block:: shell

    uv run --no-sync extract-openapi.py
    uv run sphinx-autobuild ./docs/ ./docs/_build/html
