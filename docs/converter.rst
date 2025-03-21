QASM Converter
==============

Introduction
------------

The **QASM Converter** is a Python-based tool designed to convert **OpenQASM 2.x** code
into **OpenQASM 3.0**, ensuring compatibility with modern quantum computing frameworks.
This conversion process includes handling unsupported gates, transforming obsolete syntax,
and integrating necessary gate definitions from external libraries.

.. warning::

   **Comment Removal:** All single-line (`//`)
   and multi-line (`/* */`) comments will be **permanently removed** during the conversion process.
   Ensure that important notes or documentation within the QASM code are backed up separately.

Key Features
------------

- **Automated QASM Conversion**: Seamlessly converts QASM 2.x code into a valid QASM 3.0 format.
- **Unsupported Gate Management**: Detects and provides definitions for gates not natively supported in QASM 3.0.
- **Library Integration**: Incorporates additional QASM gate definitions from external files.
- **Syntax Adjustments**: Ensures compatibility by modifying QASM 2.x elements like ``opaque`` statements and library inclusions.

Key Methods
-----------

.. autoclass:: app.converter.qasm_converter.QASMConverter
   :members:
   :special-members: __init__
   :member-order: bysource

Utils
-----

.. automodule:: app.converter.qasm_converter
   :members: remove_comments
   :member-order: bysource