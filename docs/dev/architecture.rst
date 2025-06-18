Architecture
============

A overview of the backend architecture can be seen here:

.. image:: ./images/components.webp

- Processing (:py:mod:`app.processing`) contains the main logic for processing any :class:`app.model.CompileRequest.CompileRequest` (also to the enricher endpoint)
- Enricher (:py:mod:`app.enricher`) retrieves implementations and is extendable via strategies that implement :class:`app.enricher.EnricherStrategy`
- Preprocessing (:py:mod:`app.processing.pre`) contains logic for preprocessing the single nodes without the global graph view
- Optimization (:py:mod:`app.processing.optimize`) reduces the amount of required ancillae qubits be reusing them across nodes
- Merging (:py:mod:`app.processing.merge`) applies the connections from the graph to the code and concatenates the flattened graph
- Postprocessing (:py:mod:`app.processing.post`) removes duplicate imports in the final program
- Repeat (:py:mod:`app.processing.nested.repeat`) unrolls the repeat node to be processed by the pipeline
- If-Then-Else (:py:mod:`app.processing.nested.if_then_else`) merges two subgraphs into one big if-then-else statement by using parts of processing


Following graphic shows how a :class:`app.model.CompileRequest.CompileRequest` is processed by the pipeline:

.. image:: ./images/pipeline.webp

Component Overview
------------------

The following diagram shows the architecture of the backend:

.. image:: ./images/components.webp
   :alt: Backend Component Overview
   :align: center

The backend is composed of the following main components:

- **Processing** (:py:mod:`app.processing`):
  Coordinates the end-to-end handling of :class:`app.model.CompileRequest.CompileRequest`, including compilation and enrichment.

- **Enricher** (:py:mod:`app.enricher`):
  Retrieves implementations and is extendable via strategies that implement :class:`app.enricher.EnricherStrategy`

- **Preprocessing** (:py:mod:`app.processing.pre`):
  Contains logic for individual node transformations that do not require global graph context, such as:

  - :mod:`Converter`: Converts OpenQASM 2 to OpenQASM 3.
  - :mod:`Renaming`: Ensures unique and conflict-free identifiers.
  - :mod:`IO Parser`: Parses input/output annotations.
  - :mod:`Size Casting`: Aligns input register sizes.
  - :mod:`Inlining of Constants`: Replaces aliases with their resolved content.

- **Optimization** (:py:mod:`app.processing.optimize`):
  Attempts to reduce circuit width via ancilla reuse heuristics.

- **Merging** (:py:mod:`app.processing.merge`):
  Applies the graph connections and flattens the node structure into a single, linear OpenQASM program.

- **Postprocessing** (:py:mod:`app.processing.post`):
  Performs cleanup steps such as removing duplicate imports and rendering the final program into OpenQASM 3.1.

- **Nested Structures**:

  - **Repeat** (:py:mod:`app.processing.nested.repeat`):
    Unrolls the repeat node to be processed by the pipeline.

  - **If-Then-Else** (:py:mod:`app.processing.nested.if_then_else`):
    Merges two subgraphs into one big if-then-else statement by using parts of processing

Pipeline Flow
-------------

The following diagram illustrates the pipeline stages for processing a :class:`app.model.CompileRequest.CompileRequest`:

.. image:: ./images/pipeline.webp
   :alt: Compilation Pipeline
   :align: center

Upon receiving a CompileRequest, the backend transforms the input model into an internal graph and processes it through a five-stage pipeline:
node enrichment, syntactic and semantic preprocessing, optional ancilla-optimized circuit optimization, output-input merging, and final AST normalization.
The result is a complete, semantically valid OpenQASM 3 program.

.. TODO add correct URL: For detailed information, refer to the `official LEQO-backend publication <https://www.iaas.uni-stuttgart.de/forschung/veroeffentlichungen/...>`_