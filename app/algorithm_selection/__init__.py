"""
Workflow that selects the quantum algorithm for a QUBO problem.

It generates the circuit of every algorithm of this project that can solve a QUBO
(:mod:`app.algorithm_selection.qasm_service`), lets the NISQ Analyzer rank QPUs for each
(:mod:`app.algorithm_selection.nisq_client`), consults past selections
(:mod:`app.algorithm_selection.repository`) and decides
(:mod:`app.algorithm_selection.decision_engine`).
"""
