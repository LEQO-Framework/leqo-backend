"""
Utilities for adapting the merged program to Qiskit compatibility expectations.
"""

from __future__ import annotations

from collections.abc import Iterable

from openqasm3.ast import Program

from app.openqasm3.ast import CommentStatement


def apply_qiskit_compatibility(
    program: Program,
    literal_nodes: Iterable[str],
    literal_nodes_with_consumers: Iterable[str],
) -> Program:
    """
    Remove literal node implementations from the program and optionally add a warning.
    """

    literal_set = set(literal_nodes)
    if not literal_set:
        return program

    start_to_id = {f"Start node {node_id}": node_id for node_id in literal_set}
    end_by_id = {node_id: f"End node {node_id}" for node_id in literal_set}

    new_statements = []
    statements = program.statements
    index = 0
    while index < len(statements):
        statement = statements[index]
        if isinstance(statement, CommentStatement):
            node_id = start_to_id.get(statement.comment)
            if node_id is not None:
                end_comment = end_by_id[node_id]
                index += 1
                while index < len(statements):
                    maybe_end = statements[index]
                    if (
                        isinstance(maybe_end, CommentStatement)
                        and maybe_end.comment == end_comment
                    ):
                        index += 1
                        break
                    index += 1
                continue
        new_statements.append(statement)
        index += 1

    warnings = set(literal_nodes_with_consumers)
    if warnings:
        node_list = ", ".join(sorted(warnings))
        warning = (
            "Qiskit compatibility warning: literal outputs from "
            f"{node_list} feed other nodes; resulting circuit may be incompatible."
        )
        new_statements.insert(0, CommentStatement(warning))

    return Program(new_statements, version=program.version)
