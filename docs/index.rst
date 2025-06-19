LEQO Backend
============

This `project <https://github.com/LEQO-Framework/leqo-backend>`_ is part of the `LEQO-Framework <https://github.com/LEQO-Framework>`_ .
It primarily desinged to be the backend for the `LEQO low-code-modeler <https://github.com/LEQO-Framework/low-code-modeler>`_.
However, since it provides its services via a simple REST-API, it can also be used as a standalone tool.

Features
--------

- Provide a REST-API for the `LEQO frontend <https://github.com/LEQO-Framework/low-code-modeler>`_
- Retrieve `OpenQASM <https://openqasm.com/>`_ implementations for low-code nodes
- Merge low-code models into a single `OpenQASM <https://openqasm.com/>`_ program compatible with `Qiskit <https://github.com/Qiskit/qiskit>`_
- Support OpenQASM 2 input via an internal converter
- Optimize circuits by reusing ancilla qubits automatically
- Can handle nested low-code nodes: If-Then-Else and Repeat
- Build to be extensible

Overview
--------

The backend is build to retrieve a :class:`app.model.CompileRequest.CompileRequest` representing a graph modeled by the low-code-modeler.
The :class:`app.enricher.Enricher` then retrieves implementations for the nodes if not explicitly given.
After that, :class:`app.processing.MergingProcessor` merges the graph to a single program with the modeled semantic.

.. warning::
   The backend requires special annotations in the implementations of the single nodes.
   If the implementation for a node is written by the user itself, he needs to comply with the specification discussed in :doc:`annotations <usage/annotations>`.

Further Information
-------------------

- Instructions on how to use the low-code-modeler with the backend: :doc:`Setup <usage/setup>`
- Endpoints provided by the backend: :doc:`REST Api <usage/rest-api>`
- Information on the configuration options of the backend: :doc:`Configuration <usage/config>`
- Annotation specification for custom implementations: :doc:`Annotations <usage/annotations>`.
- Information for further development: :doc:`Development <dev/overview>`

.. toctree::
    :caption: Usage
    :hidden:
    :maxdepth: 2

    usage/setup.rst
    usage/rest-api.rst
    usage/config.rst
    usage/annotations.rst

.. toctree::
    :caption: Development
    :hidden:
    :maxdepth: 2

    dev/overview.rst
    dev/architecture.rst
    dev/testing.rst
    dev/docs.rst
    dev/sbom.rst
    dev/openqasm3
