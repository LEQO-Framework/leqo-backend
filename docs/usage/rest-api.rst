REST API
========

.. openapi:: ../openapi.json

QUBO Algorithm Selection
------------------------

``POST /qubo/algorithm-selection`` selects the quantum algorithm and circuit depth for a QUBO
(body: ``{"matrix": [[...]], "variables": [...], "offset": 0}``).
The candidates are QAOA and VQE at the configured depths (by default QAOA p=1, p=2 and VQE L=1, L=2).
The backend generates the circuit of every candidate with the enricher strategies and lets the
NISQ Analyzer select and rank QPUs for each circuit.
Candidates without a QPU or whose top-ranked QPU has an error chance above the configured maximum are removed.
Among the rest, it combines the best mean solution quality on similar QUBOs from the history and a problem
structure rule: VQE up to 14 variables, QAOA from 18 variables on, and from 16 variables on QAOA for QUBOs with
weak local fields (mean |field| / mean |coupling| of the Ising form at most 0.78) and a density of at most 0.625.
The rule only votes for QAOA if a feasible QAOA circuit has an error chance of at most 0.4.
Without a clear result it selects the shallowest feasible VQE.
Every selection is stored and returned with its reasoning.

* ``GET /qubo/algorithm-selection/{id}`` returns a stored selection.
* ``GET /qubo/algorithm-selection/history?limit=50`` lists recent selections.
* ``PUT /qubo/algorithm-selection/{id}/outcome`` (body: ``{"succeeded": true, "quality": 0.93}``) reports whether
  solving the QUBO with the selected candidate succeeded and, optionally, the solution quality in ``[0, 1]``
  (e.g. the approximation ratio; without it a success counts as 1, a failure as 0).
  Only selections with a reported outcome are used as history.
