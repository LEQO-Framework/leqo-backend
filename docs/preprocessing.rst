Preprocessing
=============

Each qasm snippet attached to a node in the editor will first be passed through the preprocessing pipeline.
The pipeline consists of multiple :class:`openqasm3.visitor.QASMTransformer` that will transform the abstract syntax tree (AST) of the qasm snippet.

.. automodule:: app.preprocessing
   :members:

In order to prevent collision while merging all the standalone qasm snippets, the preprocessing pipeline needs to know the position of the snippet in the final program.

.. automodule:: app.model.SectionInfo
   :members:

Renaming
--------

.. automodule:: app.preprocessing.renaming
    :members:
    :undoc-members:


