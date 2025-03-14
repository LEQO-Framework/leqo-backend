LEQO-Backend documentation
==========================

Add your content using ``reStructuredText`` syntax. See the
`reStructuredText <https://www.sphinx-doc.org/en/master/usage/restructuredtext/index.html>`_
documentation for details.

.. openapi:: openapi.json

.. toctree::
    :caption: Qasm Pipeline
    :hidden:
    :maxdepth: 2

    preprocessing

.. toctree::
    :caption: Development
    :hidden:
    :maxdepth: 2

    testing
    example-cross-references

.. toctree::
    :caption: OpenQasm3
    :hidden:
    :titlesonly:

    openqasm3/ast
    openqasm3/visitor
