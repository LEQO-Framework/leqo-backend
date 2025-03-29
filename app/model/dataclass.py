from typing import override


class SingleInputInfo:
    id: int
    position: int

    def __init__(self, input_id: int, position: int) -> None:
        self.id = input_id
        self.position = position

    @override
    def __eq__(self, value: object, /) -> bool:
        if not isinstance(value, SingleInputInfo):
            return False
        return self.id == value.id and self.position == value.position


class SingleOutputInfo:
    id: int
    position: int

    def __init__(self, output_id: int, position: int) -> None:
        self.id = output_id
        self.position = position

    @override
    def __eq__(self, value: object, /) -> bool:
        if not isinstance(value, SingleOutputInfo):
            return False
        return self.id == value.id and self.position == value.position


class SingleIOInfo:
    input: SingleInputInfo | None
    output: SingleOutputInfo | None
    reusable: bool

    def __init__(
        self,
        input: SingleInputInfo | None = None,
        output: SingleOutputInfo | None = None,
        reusable: bool | None = None,
    ) -> None:
        self.input = input
        self.output = output
        self.reusable = reusable or False

    @override
    def __eq__(self, value: object, /) -> bool:
        if not isinstance(value, SingleIOInfo):
            return False
        return (
            self.input == value.input
            and self.output == value.output
            and self.reusable == self.reusable
        )


class SnippetIOInfo:
    declaration_to_id: dict[str, list[int]]
    alias_to_id: dict[str, list[int]]
    id_to_info: dict[int, SingleIOInfo]

    def __init__(
        self,
        declaration_to_id: dict[str, list[int]] | None = None,
        alias_to_id: dict[str, list[int]] | None = None,
        id_to_info: dict[int, SingleIOInfo] | None = None,
    ) -> None:
        self.declaration_to_id = declaration_to_id or {}
        self.alias_to_id = alias_to_id or {}
        self.id_to_info = id_to_info or {}

    @override
    def __eq__(self, value: object, /) -> bool:
        if not isinstance(value, SnippetIOInfo):
            return False
        return (
            self.declaration_to_id == value.declaration_to_id
            and self.id_to_info == value.id_to_info
        )


class IOInfo:
    snippets: list[SnippetIOInfo]

    def __init__(self, snippets: list[SnippetIOInfo] | None = None) -> None:
        self.snippets = snippets or []
