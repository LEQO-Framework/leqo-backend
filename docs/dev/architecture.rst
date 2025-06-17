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
