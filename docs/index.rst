Introduction
============

The LEQO-Backend is a standalone service to provide code-generation for a low-code modeller for quantum-algorithms with a simple REST-Api.

The LEQO-Backend has no vendor lock-in as it produces `OpenQASM 3 <https://openqasm.com/>`_ as output.

.. tip::
    For an existing implementation of a low-code modeller (frontend) have a look at the `low-code-modeler <https://github.com/LEQO-Framework/low-code-modeler>`_ repository.

.. toctree::
    :caption: Introduction
    :hidden:
    :maxdepth: 2

    self
    intro/setup.rst
    intro/getting-started.rst

.. toctree::
    :caption: Usage
    :hidden:
    :maxdepth: 2

    usage/annotations.rst
    usage/rest-api.rst

.. toctree::
    :caption: Development
    :hidden:
    :maxdepth: 2

    dev/overview.rst
    dev/testing.rst
    dev/docs.rst
    dev/openqasm3.rst
