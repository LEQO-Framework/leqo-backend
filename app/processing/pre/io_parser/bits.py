from __future__ import annotations

from io import UnsupportedOperation
from typing import override

from openqasm3.ast import (
    AliasStatement,
    BitType,
    ClassicalDeclaration,
    QubitDeclaration,
)

from app.processing.io_info import (
    BitIOInfo,
    RegAnnotationInfo,
    RegSingleInputInfo,
    RegSingleOutputInfo,
)
from app.processing.pre.io_parser.abstracts import RegIOInfoBuilder


class BitIOInfoBuilder(RegIOInfoBuilder[BitIOInfo]):
    @override
    def handle_declaration(
        self,
        declaration: QubitDeclaration | ClassicalDeclaration,
        input_id: int | None,
        dirty: bool = False,
    ) -> None:
        if not isinstance(declaration, ClassicalDeclaration) or not isinstance(
            declaration.type,
            BitType,
        ):
            msg = f"handle_declaration: expected bit declaration got {declaration}"
            raise RuntimeError(msg)

        name = declaration.identifier.name
        bit_ids = self.declaration_size_to_ids(declaration.type.size)

        for i, bit_id in enumerate(bit_ids):
            self.io.id_to_info[bit_id] = RegAnnotationInfo(
                input=RegSingleInputInfo(input_id, i) if input_id is not None else None,
            )
        self.io.declaration_to_ids[name] = bit_ids

        if input_id is not None:
            self.io.input_to_ids[input_id] = bit_ids

    @override
    def handle_alias(
        self,
        alias: AliasStatement,
        output_id: int | None,
        reusable: bool,
    ) -> None:
        name = alias.target.name

        if reusable:
            msg = (
                f"Unsupported: reusable annotation over alias {name} referring to bits"
            )
            raise UnsupportedOperation(msg)

        bit_ids = self.alias_to_ids(alias)

        if output_id is not None:
            self.io.output_to_ids[output_id] = bit_ids

        for i, bit_id in enumerate(bit_ids):
            current_info = self.io.id_to_info[bit_id]
            if output_id is not None:
                if current_info.output is not None:
                    msg = f"alias {name} tries to overwrite already declared output"
                    raise UnsupportedOperation(msg)
                current_info.output = RegSingleOutputInfo(output_id, i)

    @override
    def finish(self) -> None:
        pass
