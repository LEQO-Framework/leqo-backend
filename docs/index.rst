LEQO Backend
============

This project is part of the `LEQO <https://github.com/LEQO-Framework>`_  -Framework.
Primary build as the backend of the LEQO `low-code-modeler <https://github.com/LEQO-Framework/low-code-modeler>`_, it provides it services via a simple REST-Api can also be used as a standalone tool.

Features
--------

- Ability to compose single program from low-code-model graphs
- Provides portable `OpenQASM 3 <https://openqasm.com/>`_ output
- Output is compatible with `Qiskit <https://github.com/Qiskit/qiskit>`_
- Can handle nested low-code nodes: if-then-else and repeat
- Provides endpoint to retrieve standalone implementations for low-code nodes
- Build to be extensible

Overview
--------

The backend is build to retrieve a :class:`app.model.CompileRequest.CompileRequest` representing the graph modeled by the low-code-modeler.
The :class:`app.enricher.Enricher` then retrieves implementations for the nodes if not explicitly given.
After that, the graph is merged to a single program with the modeled semantic.

.. warning::
   The backend requires special annotations in the implementations of the single nodes.
   If the implementation for a node is written by the user itself, he needs to comply with the specification discussed in :doc:`annotations <usage/annotations>`.

Further information can be found here:

- Instructions on how to use the low-code-modeler with the backend: :doc:`Setup <usage/setup>`
- Endpoints provided by the backend: :doc:`REST Api <usage/rest-api>`
- Annotation specification for custom implementations: :doc:`Annotations <usage/annotations>`.
- Information for further development: :doc:`Development <dev/overview>`

.. toctree::
    :caption: Usage
    :hidden:
    :maxdepth: 2

    usage/setup.rst
    usage/rest-api.rst
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
