LEQO Backend
============

This project is part of the `LEQO-Framework <https://github.com/LEQO-Framework>`_ .
It primarily desinged to be the backend for the `LEQO low-code-modeler <https://github.com/LEQO-Framework/low-code-modeler>`_.
However, since it provides its services via a simple REST-API, it can also be used as a standalone tool.

Features
--------

- Ability to compose a single program from low-code-model graphs
- Provides portable `OpenQASM 3 <https://openqasm.com/>`_ output
- Output is compatible with `Qiskit <https://github.com/Qiskit/qiskit>`_
- Provides endpoint to retrieve standalone implementations for low-code nodes
- Additional enrich endpoint to retrieve just the implementation
- Handle OpenQASM 2 input via own converter
- Optimize the result by automated reusage of ancilla qubits
- Can handle nested low-code nodes: if-then-else and repeat
- Automated upcasts in the node implementations if the inputs into the node is to to big
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
