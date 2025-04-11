from __future__ import annotations

from io import UnsupportedOperation
from itertools import chain
from typing import override

from openqasm3.ast import (
    AliasStatement,
    ClassicalDeclaration,
    QubitDeclaration,
)

from app.processing.io_info import (
    QubitAnnotationInfo,
    QubitIOInfo,
    RegSingleInputInfo,
    RegSingleOutputInfo,
)
from app.processing.pre.io_parser.abstracts import RegIOInfoBuilder


class QubitIOInfoBuilder(RegIOInfoBuilder[QubitIOInfo]):
    @override
    def handle_declaration(
        self,
        declaration: QubitDeclaration | ClassicalDeclaration,
        input_id: int | None,
        dirty: bool = False,
    ) -> None:
        if not isinstance(declaration, QubitDeclaration):
            msg = (
                f"handle_declaration: expected QubitDeclaration got {type(declaration)}"
            )
            raise TypeError(msg)

        name = declaration.qubit.name
        qubit_ids = self.declaration_size_to_ids(declaration.size)

        for i, qubit_id in enumerate(qubit_ids):
            self.io.id_to_info[qubit_id] = QubitAnnotationInfo(
                input=RegSingleInputInfo(input_id, i) if input_id is not None else None,
                dirty=dirty,
            )
        self.io.declaration_to_ids[name] = qubit_ids

        if input_id is not None:
            self.io.input_to_ids[input_id] = qubit_ids
        elif dirty:
            self.io.dirty_ancillas.extend(qubit_ids)
        else:  # non-input and non-dirty
            self.io.required_ancillas.extend(qubit_ids)

    @override
    def handle_alias(
        self,
        alias: AliasStatement,
        output_id: int | None,
        reusable: bool,
    ) -> None:
        name = alias.target.name

        qubit_ids = self.alias_expr_to_ids(alias.value)
        if qubit_ids is None:
            return
        if len(qubit_ids) == 0:
            msg = f"Unable to resolve IDs of alias {alias}"
            raise RuntimeError(msg)

        self.alias_to_ids[name] = qubit_ids
        if output_id is not None:
            self.io.output_to_ids[output_id] = qubit_ids

        for i, qubit_id in enumerate(qubit_ids):
            current_info = self.io.id_to_info[qubit_id]
            if reusable:
                if current_info.output is not None:
                    msg = f"alias {name} declares output qubit as reusable"
                    raise UnsupportedOperation(msg)
                current_info.reusable = True
                self.io.reusable_ancillas.append(qubit_id)
            elif output_id is not None:
                if current_info.output is not None:
                    msg = f"alias {name} tries to overwrite already declared output"
                    raise UnsupportedOperation(msg)
                if current_info.reusable:
                    msg = f"alias {name} declares output for reusable qubit"
                    raise UnsupportedOperation(msg)
                current_info.output = RegSingleOutputInfo(output_id, i)

    @override
    def finish(self) -> None:
        returned_dirty = set(self.io.id_to_info.keys())
        returned_dirty.difference_update(
            self.io.reusable_ancillas,
            self.io.reusable_after_uncompute,
            set(chain(*self.io.output_to_ids.values())),
        )
        self.io.returned_dirty_ancillas = sorted(returned_dirty)
