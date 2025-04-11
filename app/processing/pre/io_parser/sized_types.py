from __future__ import annotations

from io import UnsupportedOperation
from typing import TypeVar, override

from openqasm3.ast import (
    AliasStatement,
    BoolType,
    ClassicalDeclaration,
    ClassicalType,
    FloatType,
    IntType,
    QubitDeclaration,
)

from app.processing.io_info import (
    BoolIOInfo,
    FloatIOInfo,
    IntIOInfo,
    SizedAnnotationInfo,
    SizedIOInfo,
    SizedSingleInputInfo,
    SizedSingleOutputInfo,
)
from app.processing.pre.io_parser.abstracts import SizedIOInfoBuilder

IT = TypeVar("IT", bound=SizedIOInfo)


class SizedIOInfoBuilderImplementation(SizedIOInfoBuilder[IT]):
    type: type[ClassicalType]

    @override
    def handle_declaration(
        self,
        declaration: QubitDeclaration | ClassicalDeclaration,
        input_id: int | None,
        dirty: bool = False,
    ) -> None:
        if not isinstance(declaration, ClassicalDeclaration) or not isinstance(
            declaration.type,
            self.type,
        ):
            msg = f"handle_declaration: got declaration of wrong type {declaration}"
            raise RuntimeError(msg)

        name = declaration.identifier.name
        int_id = self.declaration_next_id()
        size = self.declaration_to_size(declaration)

        self.io.id_to_info[int_id] = SizedAnnotationInfo(
            input=SizedSingleInputInfo(input_id) if input_id is not None else None,
            size=size,
        )
        self.io.declaration_to_id[name] = int_id

        if input_id is not None:
            self.io.input_to_id[input_id] = int_id

    @override
    def handle_alias(
        self,
        alias: AliasStatement,
        output_id: int | None,
        reusable: bool,
    ) -> None:
        name = alias.target.name

        if reusable:
            msg = f"Unsupported: reusable annotation over alias {name} referring to classical"
            raise UnsupportedOperation(msg)

        int_id = self.alias_to_id(alias)

        if output_id is not None:
            self.io.output_to_id[output_id] = int_id

        current_info = self.io.id_to_info[int_id]
        if output_id is not None:
            if current_info.output is not None:
                msg = f"alias {name} tries to overwrite already declared output"
                raise UnsupportedOperation(msg)
            current_info.output = SizedSingleOutputInfo(output_id)

    @override
    def finish(self) -> None:
        pass


class IntIOInfoBuilder(SizedIOInfoBuilderImplementation[IntIOInfo]):
    type = IntType


class FloatIOInfoBuilder(SizedIOInfoBuilderImplementation[FloatIOInfo]):
    type = FloatType


class BoolIOInfoBuilder(SizedIOInfoBuilderImplementation[BoolIOInfo]):
    type = BoolType
